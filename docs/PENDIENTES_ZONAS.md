# Zonas peligrosas — pendientes

Documento de seguimiento del módulo `zonas_peligrosas`. Recoge lo que **no** se implementó en
la tarea de mapa y las correcciones que todavía necesitan las migraciones y el panel web.

## 1. Migraciones

La cadena de esta rama no se puede ejecutar todavía:

- `migrations/versions/0012_reportes_clasificacion_ia.py` declara `revision = "0011"`, el mismo
  id que `0011_actualizar_centros_ayuda.py`.
- `migrations/versions/0015_zonas_peligrosas_donaciones.py` declara `down_revision = "0014"`,
  pero en esta rama no existen archivos `0013` ni `0014`.

`0013` y `0014` existen en otra rama. **No renumerar `0015` a ciegas.** Al integrar esa rama:

1. Confirmar que la cadena quede lineal y con un solo head:

   ```bash
   docker compose exec api alembic heads
   ```

2. Corregir `0012` para que su revisión sea `0012` y su `down_revision` sea `0011`.
3. Dejar `0015` apuntando al head real que resulte después de integrar `0013` y `0014`
   (muy probablemente `0014`).
4. Probar ambos sentidos:

   ```bash
   docker compose exec api alembic upgrade head
   docker compose exec api alembic downgrade -1
   docker compose exec api alembic upgrade head
   ```

5. Actualizar el docstring de `0015`, que todavía dice `Revision ID: 0008` y
   `Revises: 0007`.

Mientras la cadena siga rota, `tests/conftest.py` no podrá migrar la base de pruebas y las
pruebas de integración fallarán antes de ejecutar el primer test.

## 2. Panel web de zonas

El backend ya devuelve el contrato definitivo. El panel todavía usa un contrato plano y
desalineado.

### 2.1 Listado

`rescate360-web/src/services/zonas.service.ts` hace:

```ts
return api<Zona[]>('/zonas-peligrosas')
```

Pero el backend devuelve una página:

```json
{
  "items": [
    {
      "id": "...",
      "nombre": "Ribera del río",
      "tipo_riesgo": "inundacion",
      "nivel": "alto",
      "descripcion": "...",
      "estado": "activa",
      "zona": { "lat": 10.4631, "lng": -73.2532, "radio_m": 800 },
      "actualizado_en": "2026-10-28T10:00:00-05:00",
      "propia": true,
      "distancia_m": null
    }
  ],
  "total": 1,
  "pagina": 1,
  "por_pagina": 20
}
```

Cambios necesarios:

- Leer `respuesta.items`, no el arreglo raíz.
- Mapear `tipo_riesgo` → `tipoRiesgo`.
- Mapear `zona.lat` / `zona.lng` → `lat` / `lng`.
- Mapear `zona.radio_m` → `radio`.
- Mantener `nivel`, `estado`, `descripcion` y `actualizado_en`.
- Ya **no** llegan `organizacion_id` ni `gestionado_por`.

### 2.2 Crear y editar

`ZonasPage.tsx` envía hoy:

```json
{
  "nombre": "...",
  "tipoRiesgo": "inundacion",
  "nivel": "alto",
  "estado": "activa",
  "descripcion": "...",
  "lat": 10.4631,
  "lng": -73.2532,
  "radio": 800
}
```

El backend espera:

```json
{
  "nombre": "...",
  "tipo_riesgo": "inundacion",
  "nivel": "alto",
  "estado": "activa",
  "descripcion": "...",
  "zona": { "lat": 10.4631, "lng": -73.2532, "radio_m": 800 }
}
```

El `PATCH` parcial usa el mismo formato anidado para `zona`; si se envía `zona`, deben ir
`lat`, `lng` y `radio_m` juntos. Sin ese cambio, el backend responde `422 DATOS_INVALIDOS`.

### 2.3 Estados

El backend ahora devuelve **todos los estados por defecto** para `administrador` y
`super_admin`, incluidas las zonas `inactiva`. El panel ya tiene filtros y la acción de
activar/desactivar, así que no necesita pedir `?estado=inactiva` por separado.

Para `ciudadano` y `voluntario`, el listado por defecto sigue mostrando solo `activa` y
`en_monitoreo`.

### 2.4 Archivos del panel a modificar

- `rescate360-fe/rescate360-web/src/services/zonas.service.ts`
- `rescate360-fe/rescate360-web/src/types/zona.ts`
- `rescate360-fe/rescate360-web/src/pages/admin/ZonasPage.tsx`

## 3. Endurecimiento pendiente

### 3.1 Restricción de radio en base de datos

Pydantic valida `0 < radio_m <= 100000`, pero la base de datos no. Agregar una migración con:

```sql
ALTER TABLE zonas_peligrosas
  ADD CONSTRAINT chk_zonas_peligrosas_radio
  CHECK (radio_m > 0 AND radio_m <= 100000);
```

### 3.2 Índice para el mapa y el polling

El mapa consulta por `estado` y ordena/filtra por `actualizado_en`. Evaluar:

```sql
CREATE INDEX ix_zonas_peligrosas_estado_actualizado
  ON zonas_peligrosas (estado, actualizado_en DESC);
```

### 3.3 Uso del índice GIST con `cerca_de`

`cerca_de()` castea la geometría a `geography` para medir en metros. El índice GIST de
`zonas_peligrosas.area` está sobre `geometry`. Verificar el plan de ejecución:

```sql
EXPLAIN ANALYZE
SELECT *
FROM zonas_peligrosas
WHERE ST_DWithin(area::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radio_m);
```

Si el cast impide usar el índice, evaluar un índice funcional sobre `(area::geography)` o
una consulta con `ST_Expand` + `ST_DWithin` sobre geometría.

### 3.4 Polling con zonas que se mueven

En el polling con `desde` y centro, la consulta filtra por cercanía usando el área nueva. Si
una zona se mueve fuera del radio consultado, no se devuelve y el cliente podría dejarla
dibujada. Es un caso borde; si aparece en producción, revisar el contrato del polling o
devolver también los ids que salieron de la vista.

### 3.5 `docs/AGENTS.md`

El documento está desactualizado en varios puntos de zonas:

- `estado_zona` aparece como `activa, resuelta`; el valor actual es `inactiva`, más
  `en_monitoreo`.
- La tabla `zonas_peligrosas` no menciona `nombre`, `nivel`, `descripcion`, `centro` ni
  `radio_m`.
- La cadena de migraciones del documento no refleja los archivos actuales.

Actualizarlo después de integrar las migraciones de la otra rama.

## 4. Implementado en esta tarea

- Capa `zonas` en `GET /mapa` (`mapa_repository.listar_zonas` y `mapa_service._punto_zona`).
- Zonas inactivas visibles por defecto para `administrador` y `super_admin` en
  `GET /zonas-peligrosas`.
- `organizacion_id` y `gestionado_por` eliminados de `ZonaPeligrosaOut`.
- `es_propia()` ahora significa “puedo editarla”: solo administrador de la organización o
  super_admin.
- El mapa sigue mostrando solo zonas vigentes; las inactivas llegan por polling como
  `activo=false` para que el cliente las quite.
