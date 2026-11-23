# Despliegue en Azure (RESCATE360)

## Arquitectura

- API, Celery worker, Celery beat y Redis corren en **un solo Container App**.
- PostgreSQL Flexible Server `B1ms` con PostGIS.
- Fotos y videos en Azure Blob Storage.
- Panel web en Azure Static Web Apps; app Flutter compilada con la URL pública de la API.

El contenedor incluye Redis local para no pagar Azure Cache for Redis (no tiene plan gratis). En producción real conviene mover Redis a un servicio managed y separar worker/beat.

## Antes de empezar

1. Activar Azure for Students y verificar que la región `eastus` (o la que elijas) tenga available PostgreSQL Flexible `B1ms`.
2. Instalar Azure CLI y ejecutar `az login`.
3. Desde `rescate360-be`, ejecutar:

```powershell
.\deploy\azure\provision.ps1
```

Ese script crea resource group, ACR, PostgreSQL, Blob Storage y el entorno de Container Apps. Escribe los secretos en `rescate360-be/.env.azure`, que está ignorado por Git. Si necesitas conectar desde tu PC para migrationes, añade tu IP:

```powershell
az postgres flexible-server firewall-rule create -g rg-rescate360 -s psql-rescate360 -n AllowMiIP --start-ip-address <TU_IP> --end-ip-address <TU_IP>
```

4. Desplegar la API:

```powershell
.\deploy\azure\deploy.ps1
```

El script construye la imagen con Docker en local, la sube al ACR, aplica migraciones al arrancar el contenedor y muestra la URL `https://...azurecontainerapps.io`. El YAML usa el digest `sha256` devuelto por el push para forzar una revisión nueva aunque el tag `latest` no cambie. Necesitas Docker Desktop iniciado. Azure for Students tiene ACR Tasks pausado, por eso no se usa `az acr build`. El entorno Express no admite init containers. El ACR se crea y se asegura en cada deploy con el usuario administrador habilitado para que Container Apps pueda descargar la imagen.

Si ya desplegaste, vuelve a ejecutar `deploy.ps1` después de cada cambio del backend. Para cambiar solo secretos, edita `.env.azure` y vuelve a ejecutarlo.

## Verificación

```powershell
$fqdn = az containerapp show -n rescate360-api -g rg-rescate360 --query properties.configuration.ingress.fqdn -o tsv
Invoke-RestMethod "https://$fqdn/health"
Invoke-RestMethod "https://$fqdn/health/ready"
```

`/health/ready` debe devolver `status: ok`, la versión de PostGIS y `redis: ok`.

## Archivos subidos antes del cambio

Si ya había fotos en `uploads/`, súbelas al contenedor Blob con:

```powershell
python scripts/azure/migrar_uploads.py
```

No hay que actualizar la base: las rutas relativas siguen iguales y `storage_client.url_publica` genera la URL del blob.

## Frontend

En `rescate360-fe`:

1. Reemplaza `config/demo.json` y `.env` con la URL real de la API: `https://rescate360-api.agreeabletree-830cccf5.westus2.azurecontainerapps.io`.
2. Recompila el APK; la URL va dentro del binario:

```powershell
.\scripts\compilar-apk.ps1
```

3. Para el panel web define las variables antes de compilar (no crear `.env.local`, no está ignorado en `rescate360-fe`):

```powershell
$env:VITE_API_URL = 'https://rescate360-api.agreeabletree-830cccf5.westus2.azurecontainerapps.io'
$env:VITE_USE_MOCK = 'false'
```

4. Ejecuta `npm run build` y publica `rescate360-web/dist` en Azure Static Web Apps. El archivo `public/staticwebapp.config.json` ya reescribe las rutas SPA a `/index.html`.
5. Copia la URL de Static Web Apps y vuelve a desplegar el backend con:

```powershell
$env:CORS_ORIGINS = '["https://gray-coast-0f93d421e.5.azurestaticapps.net","http://localhost:5173","http://127.0.0.1:5173","http://localhost:3000","http://127.0.0.1:3000"]'
.\deploy\azure\deploy.ps1
```

Despliegue actual verificado:

- API: `https://rescate360-api.agreeabletree-830cccf5.westus2.azurecontainerapps.io`
- Panel (Static Web Apps `rescate360-web-830cccf5`): `https://gray-coast-0f93d421e.5.azurestaticapps.net`
- APKs por arquitectura: `rescate360-fe/build/app/outputs/flutter-apk/app-*-release.apk` (símbolos en `build/symbols`)

Si `/health/ready` devuelve 503 y los logs muestran `could not open certificate file "/root/.postgresql/postgresql.crt"`, la imagen ya fija `HOME=/home/appuser`; reconstruye y vuelve a desplegar con `deploy.ps1`.

Si los logs muestran `SIGTERM` unos 20 segundos después del arranque mientras corren las migraciones, el liveness probe estaba matando la réplica antes de que `uvicorn` empezara a escuchar; la plantilla ya usa `initialDelaySeconds: 60` y `failureThreshold: 10`.

Si `alembic` falla con `extension "unaccent" is not allow-listed for users in Azure Database for PostgreSQL`, `provision.ps1` ya configura `azure.extensions=POSTGIS,UNACCENT`. Para una base ya creada:
```powershell
az postgres flexible-server parameter set -g rg-rescate360 -s psql-rescate360-sa1-northcentralus --name azure.extensions --value POSTGIS,UNACCENT -o none
```

## Costos

Con el patrón de uso previsto (demos de 4-5 h/día, no todos los días) y este despliegue, el consumo esperado es **$0** mientras la suscripción de Azure for Students siga activa y no se excedan los límites mensuales.

| Servicio | Límite gratis | Uso de este demo |
| --- | --- | --- |
| Container Apps | 180,000 vCPU-s, 360,000 GiB-s y 2M requests/mes | `0.25 vCPU` + `0.5 GiB` => 200 h reales/mes de margen; 5 h × 20 días usa ~90,000 vCPU-s |
| PostgreSQL Flexible `B1ms` | 750 h/mes, 32 GB + 32 GB backup, 12 meses | 24/7 son 720-744 h, dentro del límite |
| ACR Standard | gratis 12 meses | 1 imagen |
| Blob Storage | 5 GB LRS hot, 20k lecturas y 10k escrituras/mes | fotos/videos del demo |
| Static Web Apps | 100 GB bandwidth, 0.5 GB storage, 2 dominios | panel web |
| Redis | incluido en la imagen | no se contrata Azure Cache for Redis |

La API nace con `minReplicas: 0` en `deploy/azure/containerapp.yaml.tpl`. Eso significa que no factura compute cuando está inactiva; la primera petición después de un rato puede tardar unos segundos en despertar. PostgreSQL sigue encendido, pero sus 750 h/mes gratis cubren el mes completo.

Antes de la demo, si quieres evitar el cold start:

```powershell
.\deploy\azure\encender.ps1
```

Después de la demo:

```powershell
.\deploy\azure\apagar.ps1
```

Equivalente manual:

```powershell
az containerapp update -n rescate360-api -g rg-rescate360 --min-replicas 1
az containerapp update -n rescate360-api -g rg-rescate360 --min-replicas 0
```

El crédito de Azure for Students es de $100 total durante 12 meses, no mensual: es solo red de seguridad. Revisa Portal > Cost Management > Cost analysis con el scope en `rg-rescate360`.

## Seguridad

- `.env.azure` y `.deploy/containerapp.yaml` contienen secretos y están ignorados por Git.
- El contenedor Blob se crea con acceso público de lectura para que la app pueda mostrar fotos. Si las evidencias deben ser privadas, cambia a SAS o CDN con identidad administrada.
- Firebase push queda desactivado si no configuras `FIREBASE_CREDENTIALS_PATH`; el resto de la API funciona igual.
