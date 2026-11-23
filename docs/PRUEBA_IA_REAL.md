# Validación del API y la clasificación real — 2026-10-27

## Corrección

El worker cargaba `app.core.celery_app`, pero el API resolvía `shared_task` contra
la aplicación predeterminada de Celery y trataba de publicar por AMQP. Redis
estaba sano, aunque los casos quedaban pendientes. Los dos jobs ahora usan
`@celery_app.task`, tanto desde Uvicorn como desde sus hilos.

Gemini recibe la clave mediante `x-goog-api-key`, evitando incluirla en las URLs
que pueden aparecer en logs. La clave y el resto del `.env` no se versionan.

## Prueba real completada

Se ejecutó el API por HTTPS público mediante un túnel temporal, con PostgreSQL,
Redis, Celery y Gemini reales. Resultado de `scripts/probar_ia_real.py`:

- Registro, login y consulta de `/usuarios/me`: correctos.
- Solicitud `1c72755e-736b-481d-8ffd-2660e909b94a`: crítica, fuente
  `gemini:gemini-3.5-flash-lite`, organización asignada.
- Reporte `1a591447-a60a-4f07-907f-164bd993e9f6`: crítico, fuente
  `gemini:gemini-3.5-flash-lite`, organización asignada.
- SOS `15d7df63-345a-466e-9cbd-7f4edea698f0`: crítico por reglas y enrutado.
- Los tres casos aparecen en los listados administrativos y en `/mapa`.
- Repetir los jobs conserva la clasificación; la prioridad manual del reporte
  se guarda sin borrar la sugerencia de la IA.

Los casos son sintéticos y están marcados con `PRUEBA IA 789154010d21`. No
constituyen emergencias reales. La prueba deja los registros para revisarlos.

También pasaron las 9 pruebas específicas del broker/clasificación, la revisión
de dependencias y la comprobación de Alembic en `0011`. La suite completa se
interrumpió por solicitud del usuario; había mostrado un fallo y no se declara
como aprobada. No se repitieron pruebas después de esa instrucción.

## Repetir en un entorno local de pruebas

Requiere superadministrador existente y `GEMINI_API_KEY` configurada:

```bash
docker compose up -d --force-recreate api worker beat
docker compose exec -T api python -m scripts.probar_ia_real
# Para comprobar también la API desplegada:
docker compose exec -T api python -m scripts.probar_ia_real --url https://<fqdn>.azurecontainerapps.io
```

El script crea una cuenta sintética y casos nuevos; requiere `APP_ENV=local`.
No imprime tokens ni claves. Falla si solicitudes/reportes usan el respaldo por
reglas en lugar de Gemini, o si el worker no entrega resultados.

El APK del frontend usa `config/demo.json`, que ya trae el FQDN de Azure; recompila
con `scripts/compilar-apk.ps1`. La guía completa está en
[deploy/azure/README.md](../deploy/azure/README.md).
