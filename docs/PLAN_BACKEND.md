# RESCATE360 — Plan de trabajo del backend (2 desarrolladores)

Este documento divide el desarrollo del backend entre **Dev A (Libardo)** y **Dev B (compañero)**. Para cada tarea dice qué se hace, qué archivos toca y para qué sirve dentro del proyecto.

Los permisos siguen el documento **"RESCATE360 — Vistas y funcionalidades por rol"**:

| Rol | Plataforma | Alcance |
|---|---|---|
| Ciudadano | App móvil | Global, sin organización |
| Voluntario | App móvil | Exactamente una organización |
| Administrador | Panel web | Exactamente una organización |
| Super admin | Panel web | Global |

El resumen por endpoint está en la sección 4.

> Estado de partida (8 de octubre de 2026):
> - El ambiente está listo en `main`/`develop`.
> - El modelo de base de datos completo está en la rama **`feature/BaseCompleta`** (14 tablas, migración `0002`), todavía sin mergear.
> - La app Flutter (Oscar) y el panel web de administración en React (Elkin, carpeta `rescate360-web/`) funcionan con **datos de prueba** y esperan la API.

---

## 1. Diagnóstico del backend

### Lo que ya funciona

- Docker con PostGIS, Redis, API, worker, beat y pgAdmin.
- `feature/BaseCompleta`:
  - `alembic upgrade head` aplica sin errores.
  - `alembic check` confirma que los modelos coinciden con la BD.
- Buen diseño del modelo:
  - `CHECK` que ata el rol a la organización.
  - Tabla `asignaciones` (voluntario ↔ solicitud o reporte).
  - Campos de IA (`confianza_ia`, `razonamiento_ia`).
  - `organizacion_objetivo_id` para enrutar casos a una organización.
  - Origen `acelerometro` en solicitudes.

### Problemas encontrados (probados contra una BD real)

| # | Problema | Efecto | Quién lo arregla |
|---|---|---|---|
| 1 | `downgrade` de la `0002` no borra los tipos ENUM | Hacer `downgrade` y luego `upgrade` falla con *type "tipo_organizacion" already exists* | Dev B |
| 2 | Ninguna columna geográfica tiene índice espacial (`spatial_index=False` en todas) | Las consultas "centros cercanos", "zonas en mi radio" y "usuarios dentro de la alerta" recorren la tabla entera | Dev B |
| 3 | `auditoria` dice "alimentada por el trigger `fn_auditoria()`", pero el trigger no existe | La tabla nunca se llena. Es un requisito legal (Ley 1273/2009 y defensa por diligencia) | Dev B (trigger) + Dev A (pasar el usuario) |
| 4 | No existe la tabla `consentimientos` | No queda registro de la autorización de datos (Ley 1581/2012) | Dev A |
| 5 | `app/models/__init__.py` lista `"PerfilVoluntario"` en `__all__`, pero su import está comentado | `from app.models import *` revienta con `AttributeError` | Dev B |
| 6 | Se usa `Geometry` (grados) y no `Geography` (metros) | `ST_DWithin(ubicacion, punto, 5000)` significa 5000 **grados**, no 5 km. Hay que castear a `::geography` en cada consulta de distancia | Ambos (regla en `app/utils/geo.py`) |
| 7 | El modelo no coincide con lo que ya muestran la app y el panel web (ver sección 3) | Cuando se conecten, faltarán campos o los estados no cuadrarán | Dueño de cada módulo |
| 8 | `centros_ayuda`, `alertas`, `zonas_peligrosas` y `donaciones` no tienen `organizacion_id` (solo `gestionado_por` / `creado_por`) | No se puede limitar al admin a "su organización" ni "mover recursos entre organizaciones" (super admin). Sin la columna, el alcance depende del usuario que creó el registro y se rompe si ese usuario cambia de organización | Dev B |

---

## 2. Reglas para no pisarnos

1. **Ramas:** `feature/<modulo>-<nombre>` (ej. `feature/auth-libardo`) siempre desde `develop`. Se entra a `develop` por Pull Request; el otro dev lo revisa y el CI debe estar verde. `main` solo recibe `develop` cuando se cierra una entrega.
2. **Cada módulo tiene un solo dueño.** El dueño toca sus archivos en `routes/`, `controllers/`, `services/`, `schemas/`, `repositories/`, `models/` y `tests/`. Si necesitas algo de un módulo ajeno, se lo pides a su dueño.
3. **Archivos compartidos.** En estos solo se **agregan líneas**, sin reordenar ni reformatear, para que los merges no choquen:

   | Archivo | Dueño | Qué agrega el otro |
   |---|---|---|
   | `app/main.py` | Dev A | Su línea `app.include_router(...)` |
   | `app/models/__init__.py` | Dev B | Su línea `from app.models.x import X` |
   | `app/models/enums.py` | Dev B | Sus enums al final |
   | `requirements.txt` | Dev B | Su dependencia, fijada con `==` y verificada con `pip check` |
   | `app/core/security.py`, `app/middlewares/*` | Dev A | — (solo los usa) |
   | `app/utils/geo.py` | Dev B | — (solo lo usa) |

4. **Migraciones:**
   - Antes de crear una, haz `git pull origin develop`.
   - Nómbrala con el siguiente número libre: `--rev-id 0004`.
   - Si dos PR traen el mismo número, **el segundo en mergear** cambia su `rev-id` y su `down_revision`.
   - Alembic no admite dos "head" a la vez; para comprobarlo, `alembic heads` debe mostrar una sola línea.
5. **Arquitectura de 4 capas** (README):
   - `routes` solo declara.
   - `controllers` arma la respuesta HTTP.
   - `services` tiene la lógica.
   - `repositories` es lo único que habla con SQLAlchemy.

---

## 3. Fase 0 — Contrato de la API (los dos juntos, 1-2 días, ANTES de programar)

La app y el panel web ya tienen pantallas con campos y estados propios, y no coinciden con el modelo. Si no se acuerda primero, cada uno programará contra una forma distinta. Se deja escrito en `docs/API_CONTRATO.md`, y se revisa con Oscar y Elkin.

### 3.1 Convenciones a decidir

| Tema | Propuesta | Por qué |
|---|---|---|
| Nombres en JSON | `snake_case` (igual que la BD) | Pydantic lo da sin configurar. El panel web hoy mezcla (`organizacion_id` y `prioridadIA`); Elkin y Oscar adaptan sus modelos una vez |
| Coordenadas | `{"lat": 10.46, "lng": -73.25}` en la API, nunca WKT ni GeoJSON | Es lo que ya usan el panel (`lat`, `lng`) y `flutter_map` (`LatLng`). La conversión vive solo en `app/utils/geo.py` |
| Login | `POST /auth/login` → `{access_token, refresh_token, usuario}` | El panel espera `{token, usuario}`; se le avisa a Elkin del cambio de nombre |
| Rutas de administración | Las mismas rutas por recurso, filtradas por rol (`GET /reportes` devuelve todo al admin y solo lo propio al ciudadano) | El panel hoy llama `/admin/reportes`; Elkin cambia una cadena por servicio. Evita duplicar endpoints |
| Errores | `{"detalle": "...", "codigo": "REPORTE_NO_ENCONTRADO"}` | Un solo formato, lo arma `error_handler_middleware` |
| Paginación | `?pagina=1&por_pagina=20` → `{items, total, pagina, por_pagina}` | El panel de usuarios ya pagina |
| Fechas | ISO 8601 con zona (`2026-10-08T14:30:00-05:00`) | Ambos front ya esperan ISO |
| Teléfonos | Formato E.164 (`+573001234567`), columna `String(15)` | La app pide `+57 300 123 4567`, y Twilio necesita E.164. Hoy la columna es `String(10)` |
| Redirección después del login | La respuesta del login incluye `usuario.rol`. La app móvil acepta solo `ciudadano` y `voluntario`; el panel web, solo `administrador` y `super_admin` | Lo pide el documento de roles. Si alguien entra por la plataforma equivocada, el front muestra el aviso; el backend no bloquea |
| "Mis reportes / solicitudes" del ciudadano | **Solo lectura de lo propio**: lista y estado, sin acciones | El documento lo deja abierto. Ver el estado de tu propio reporte no es "seguimiento operativo", y lo pide el flujo "reporta → consulta estado" del documento de propuesta |
| Seguimiento del voluntario | Ve las solicitudes y reportes de su organización, se **asigna** un caso y cambia el estado **solo de sus asignaciones** (`en_proceso` → `atendida`). No verifica reportes ni cambia la prioridad de la IA | Así lo dice el documento de roles. El documento de arquitectura viejo decía "verificar (limitado)"; manda el nuevo |

### 3.2 Diferencias entre el modelo y los front (cada dueño las resuelve en su módulo)

| Módulo | Lo que piden la app y el panel | Lo que tiene la BD | Dueño |
|---|---|---|---|
| Usuarios | Estado `activo` / `en_espera` / `bloqueado`, `ultimo_acceso`, código `USR-001` | Solo `activo` (booleano) | A |
| Reportes | Tipos `accidente, robo, inundacion, deslizamiento, incendio, otro`; **varias fotos y video**; dirección en texto; nombre del reportante | Una sola `foto_url`, sin dirección | A |
| Personas desaparecidas | `edad`, `sexo`, `estatura`, `fecha_vista`, `lugar`, `senas_particulares`, `vestimenta`, contacto (nombre + teléfono), estados `en_busqueda / en_proceso / encontrada` | Solo `nombre`, `caracteristicas`, `foto_url`, `ultima_ubicacion`; estados `buscando / encontrado` | A |
| Solicitudes | **Tipo de ayuda** (`medica, alimentaria, refugio, rescate, ropa, otro`); estados `pendiente / en_proceso / atendida / cancelada`; el botón SOS (mantener 3 s) | No hay columna `tipo`; estados `pendiente / en_atencion / resuelta` | B |
| Centros | `tipo` (`albergue, comedor, puesto_medico, centro_acopio`), `estado`, dirección; el nombre no cabe en `String(30)` ("Centro Comunitario El Sol") | Sin estado ni dirección | B |
| Zonas peligrosas | `nombre`, `nivel` (alto/medio/bajo), estados `activa / en_monitoreo / inactiva`, se dibujan como **círculo** (`lat`, `lng`, `radio` en metros) | Un polígono, estados `activa / resuelta` | B |
| Donaciones | **Campañas** (meta, recaudado, fecha fin), categorías, monto en dinero, estado | Solo inventario por centro | B |
| Dashboard admin | Contadores y actividad reciente | No existe endpoint | A |

---

## 4. Permisos por endpoint

Traducción del documento de vistas por rol a reglas del backend. **C** = ciudadano, **V** = voluntario, **A** = administrador, **S** = super admin.

- **Propio**: solo los registros que creó el usuario.
- **Org**: solo los registros de la organización del usuario (`organizacion_id`).
- **Todo**: sin filtro.

| Recurso / acción | C | V | A | S |
|---|---|---|---|---|
| Registro / login | ✓ (registro siempre crea `ciudadano`) | login | login | login. Se crea por bootstrap, nunca por registro |
| Ver mapa, alertas, centros, zonas, guía | ✓ (las solicitudes de otros salen con ubicación **aproximada**) | ✓ | Org | Todo |
| Crear reporte / solicitud / SOS / persona desaparecida | ✓ | ✓ | ✓ | ✓ |
| Listar reportes y solicitudes | Propio (solo lectura) | Org | Org | Todo |
| Asignarse un caso y cambiar el estado de **su** asignación | — | ✓ | ✓ | ✓ |
| Verificar / rechazar / marcar duplicado un reporte | — | — | Org | Todo |
| Prioridad manual sobre la IA y cambio de estado de cualquier solicitud | — | — | Org | Todo |
| Gestionar alertas, centros, zonas, donaciones y campañas | — | — | Org | Todo |
| Cambiar el estado de una persona desaparecida (`encontrada`) | — | — | Org | Todo |
| Gestionar usuarios | — | — | Voluntarios y ciudadanos de su org (crear voluntario, bloquear) | Todos |
| Organizaciones (crear, editar, activar/desactivar) | — | — | Ver la suya | ✓ |
| Administradores de una organización (crear, listar, revocar) | — | — | — | ✓ |
| Mover un recurso a otra organización | — | — | — | ✓ |
| Guía de emergencia (escribir) | — | — | — | ✓ |
| Dashboard | — | Resumen de sus asignaciones | De su org | Global |
| Auditoría / historial | — | — | Org | Todo |
| Mi perfil, mis datos, consentimientos, contactos de emergencia | ✓ | ✓ | ✓ | ✓ |

Reglas fijas del super admin: no puede desactivarse ni quitarse el rol a sí mismo, y el sistema nunca queda sin un super admin activo.

---

## 5. División por desarrollador

### Visión general

| | **Dev A — Libardo** | **Dev B — compañero** |
|---|---|---|
| Enfoque | Seguridad, identidad, usuarios y lo que **reporta el ciudadano** | Base de datos, geografía, IA, colas y lo que **coordina la emergencia** |
| Base técnica | Seguridad (JWT, bcrypt), middlewares, errores, paginación, CORS, archivos/fotos | Migraciones, índices, triggers, `utils/geo.py`, Celery, IA, push/SMS |
| Módulos MVP | `auth`, `usuarios`, `organizaciones` (+ mover recursos), `reportes` + verificación | `solicitudes_ayuda` + IA, `asignaciones` del voluntario, `alertas`, `centros_ayuda`, mapa |
| Módulos 2ª iteración | `personas_desaparecidas`, `contactos`, `consentimientos`, `guia_emergencia`, dashboards por rol, auditoría | `zonas_peligrosas`, `donaciones` + campañas, jobs programados |
| Evolución | Seed de datos | Sincronización offline (`/offline/sync`) |

> **Sugerencia:** Sergio modeló toda la BD, así que encaja como Dev B: ya conoce cada tabla.

### Orden y dependencias entre los dos

```
Fase 0 (juntos)  ── Contrato API ──────────────────────────────┐
Sprint 1   A: security + middlewares + auth ──► B usa require_role()
           B: migración 0003 + utils/geo ─────► A usa geo para reportes
Sprint 2   A: usuarios, organizaciones, reportes     B: solicitudes + IA, alertas + push, centros, mapa
                       ─────────── cierre MVP: los dos front ya pueden conectarse ───────────
Sprint 3   A: personas, contactos, consentimientos, dashboard   B: zonas, donaciones, jobs programados
Sprint 4   A: guía, auditoría, seed                              B: offline sync
           Los dos: pruebas integrales, revisión de permisos por rol
```

Para no bloquearse en el sprint 1:
- **Dev A** publica primero `get_current_user` y `require_role(...)`, aunque sea con la firma lista y la lógica mínima.
- **Dev B** publica primero `app/utils/geo.py`.
- Cada uno puede arrancar con la firma acordada y probar sus endpoints sin protección hasta que llegue la del otro.

---

## 6. Tareas de Dev A — Libardo

### A1. Seguridad y middlewares (Sprint 1, primero de todo)
**Para qué:** todo endpoint protegido depende de esto. Es lo que hace que un ciudadano no pueda verificar reportes y que un admin solo vea su organización.

| Archivo | Qué va |
|---|---|
| `app/core/security.py` | `hash_password` / `verify_password` con `bcrypt`, rechazando más de 72 bytes. `crear_access_token` / `crear_refresh_token` / `decodificar_token` con `PyJWT` (el token lleva `sub`, `rol`, `organizacion_id`) |
| `app/middlewares/auth_middleware.py` | Dependencia `get_current_user`: lee `Authorization: Bearer`, valida el token, carga el usuario y rechaza si está bloqueado |
| `app/middlewares/role_middleware.py` | `require_role("administrador", "super_admin")`. Helpers de alcance para la matriz de la sección 4: `alcance_organizacion(usuario)` devuelve `None` para super_admin y el `organizacion_id` para voluntario y admin; `solo_propio(usuario)` sirve para el ciudadano. B los usa en todos sus repositorios |
| `app/middlewares/error_handler_middleware.py` | Excepciones de negocio (`NoEncontrado`, `SinPermiso`, `Conflicto`) → formato de error del contrato |
| `app/middlewares/validation_middleware.py` | Errores de Pydantic (422) → mismo formato de error, en español |
| `app/middlewares/audit_middleware.py` | Hace `SET LOCAL app.usuario_id = '<uuid>'` en la transacción, para que el trigger de B sepa quién hizo el cambio |
| `app/utils/paginacion.py` | `Paginacion` (schema de query) y `Pagina[T]` (respuesta) |
| `app/main.py` | CORS para el panel web (`http://localhost:5173`) y registro de routers y handlers |
| `app/core/logging.py` | Logging con id de petición |
| `tests/unit/middlewares/test_role_middleware.py` | Una prueba por fila de la matriz de la sección 4 |

### A2. Autenticación (Sprint 1)
**Para qué:** pantallas de login y registro de la app (ya hechas) y login del panel web.

| Archivo | Qué va |
|---|---|
| `app/routes/auth_routes.py` · `app/controllers/auth_controller.py` · `app/services/auth_service.py` · `app/schemas/auth_schema.py` | `POST /auth/registro` (siempre rol `ciudadano`, exige `acepta_tratamiento_datos=true`), `POST /auth/login`, `POST /auth/refresh-token`. Actualiza `ultimo_acceso` |
| `app/repositories/usuarios_repository.py` | `buscar_por_email`, `crear`, `actualizar` |
| `tests/integration/test_auth_api.py` | Registro, login correcto e incorrecto, token vencido, usuario bloqueado |

### A3. Usuarios, organizaciones y super admin (Sprint 2)
**Para qué:** la pantalla de usuarios del panel (búsqueda, paginación, bloqueo) y la estructura multi-organización que agregó Sergio al README.

| Archivo | Qué va |
|---|---|
| `app/models/usuario.py` + migración | Estado (`activo` / `en_espera` / `bloqueado`), `ultimo_acceso`, `telefono String(15)` |
| `app/routes/usuarios_routes.py` (+ controller, service, schema) | `GET /usuarios` (paginado, búsqueda, filtro por rol; el admin solo ve su organización), `POST /usuarios` (el admin crea un **voluntario** en su organización), `GET/PATCH/DELETE /usuarios/{id}` (bloquear o desbloquear), `GET/PATCH /usuarios/me` (perfil; el voluntario ve su organización) |
| **Nuevos:** `app/routes/organizaciones_routes.py`, `app/controllers/organizaciones_controller.py`, `app/services/organizaciones_service.py`, `app/schemas/organizaciones_schema.py`, `app/repositories/organizaciones_repository.py` | CRUD de organizaciones y `POST/GET/PATCH/DELETE /organizaciones/{id}/administradores`. Solo `super_admin`. Autoprotección: no puede quedar sin ningún super_admin |
| Módulo `organizaciones` | `PATCH /organizaciones/mover-recurso` → `{tipo, id, organizacion_destino_id}`, donde `tipo` es `centro`, `alerta`, `zona`, `campana`, `reporte` o `solicitud`. Solo super_admin; queda en auditoría. Depende de las columnas `organizacion_id` de B1 |
| `scripts/seed/crear_super_admin.py` | Crea el super admin inicial desde variables de entorno (nunca por registro) |
| `tests/integration/test_usuarios_api.py`, `test_organizaciones_api.py` | |

### A4. Reportes de incidentes + verificación (Sprint 2, cierre de MVP)
**Para qué:** pantalla "Reportar incidente" de la app (con fotos y video) y pantalla de reportes del panel (filtros y verificar/rechazar/duplicado). Es el corazón del pitch: la información tiene estados verificados.

| Archivo | Qué va |
|---|---|
| `app/models/reporte.py` + migración | Columna `direccion`. **Nueva tabla `evidencias`** (o `fotos_urls ARRAY`) para varias fotos y video. `tipo` como enum del contrato |
| `app/routes/reportes_routes.py` (+ controller, service, schema, `reportes_repository.py`) | `POST /reportes` (multipart con fotos), `GET /reportes` (ciudadano: los suyos; voluntario/admin: todos en su alcance; filtros por estado, tipo y fecha), `GET /reportes/{id}`, `PATCH /reportes/{id}/verificar · rechazar · marcar-duplicado` (admin, guarda `verificado_por`) |
| `app/integrations/storage_client.py` | Guardar archivos. En local: volumen `uploads/` servido como estático. Valida tipo y tamaño |
| — | Al crear un reporte, encolar `notificar_voluntarios_cercanos` (el job lo hace B; A solo llama `.delay()`) |
| `tests/integration/test_reportes_api.py` | |

### A5. Personas desaparecidas (Sprint 3)
**Para qué:** las pantallas que Oscar terminó con imágenes, y la de Elkin en el panel. Es el módulo con más requisitos legales (fotos de menores, desaparición forzada).

| Archivo | Qué va |
|---|---|
| `app/models/persona_desaparecida.py` + migración | Campos del contrato (`edad`, `sexo`, `estatura`, `fecha_vista`, `lugar`, `senas_particulares`, `vestimenta`, `contacto_nombre`, `contacto_telefono`, `actualizado_en`); estados acordados; `es_menor` |
| `app/routes/personas_desaparecidas_routes.py` (+ controller, service, schema, repository) | `POST` (con foto), `GET` (búsqueda por nombre, filtro por estado), `GET /{id}`, `PATCH /{id}/estado`. Al marcar `encontrada` encola `notificar_persona_encontrada` |
| Regla legal | Si `es_menor`, la foto solo la ven admins (Ley 1098/2006). El teléfono de contacto no sale en el listado público |

### A6. Contactos de emergencia, consentimientos y datos personales (Sprint 3)
**Para qué:** pantalla "Contactos de emergencia" de la app, y cumplir la Ley 1581 (consultar, corregir y borrar datos).

| Archivo | Qué va |
|---|---|
| `app/models/consentimiento.py` (nuevo) + migración | `usuario_id`, `tipo` (`tratamiento_datos`, `ubicacion`, `foto_persona`), `version_politica`, `aceptado_en`, `ip`. Se llena en el registro |
| `app/repositories/consentimientos_repository.py` | |
| Endpoints en el módulo `usuarios` | `GET/POST/PATCH/DELETE /usuarios/me/contactos-emergencia`, `GET /usuarios/me/datos` (exportar mis datos), `DELETE /usuarios/me` (anonimizar) |

### A7. Dashboards, auditoría y guía de emergencia (Sprint 3-4)
**Para qué:** el dashboard de cada rol (voluntario: sus tareas; admin: su organización; super admin: global), el historial de auditoría que pide el documento de roles, y la pantalla de guía de la app.

| Archivo | Qué va |
|---|---|
| **Nuevo:** `app/routes/dashboard_routes.py` (+ controller, service) | `GET /dashboard` → `{resumen: {reportes_pendientes, solicitudes_activas, alertas_activas, centros_registrados}, recientes: [...]}`. El contenido depende del rol: voluntario = sus asignaciones activas; admin = su organización; super admin = global, con totales por organización |
| **Nuevo:** `app/routes/auditoria_routes.py` (+ controller, service, `auditoria_repository.py`) | `GET /auditoria?tabla=&registro_id=&usuario_id=&desde=&hasta=`. Solo lectura; el admin ve la de su organización y el super admin todo. Se llena con el trigger de B1 |
| `app/routes/guia_emergencia_routes.py` (+ resto) | `GET /guia-emergencia` (todos, por categoría). `POST`/`PATCH` **solo super_admin** (el documento de roles no se la da al admin). Incluir el contenido legal: línea 123 y Mecanismo de Búsqueda Urgente |
| `scripts/seed/` | Datos de prueba: organizaciones, usuarios de cada rol, reportes, guía |

---

## 7. Tareas de Dev B — compañero

### B1. Arreglar y completar la base de datos (Sprint 1, primero de todo)
**Para qué:** sin esto, A no puede hacer consultas por cercanía, la auditoría no funciona y las migraciones no se pueden revertir.

| Archivo | Qué va |
|---|---|
| `migrations/versions/0002_crear_esquema_inicial.py` | En `downgrade()`: `DROP TYPE` de cada enum después de borrar las tablas. Se puede corregir en la misma 0002 porque todavía no está en `develop` |
| `app/models/__init__.py` | Quitar `"PerfilVoluntario"` de `__all__`, o crear el modelo |
| **Nueva:** `migrations/versions/0003_indices_y_auditoria.py` | Índices `GIST` en todas las columnas geográficas. Índices en `reportes.estado`, `solicitudes_ayuda(estado, prioridad_ia)`, `usuarios.organizacion_id`. Función `fn_auditoria()` (lee `current_setting('app.usuario_id', true)`) y triggers `AFTER INSERT/UPDATE/DELETE` en las tablas de negocio |
| Misma migración `0003` | Columna `organizacion_id` (FK a `organizaciones`, con índice) en `centros_ayuda`, `alertas`, `zonas_peligrosas` y `donaciones`. Es lo que permite que el admin vea solo lo suyo y que el super admin mueva recursos (problema 8) |
| `app/utils/geo.py` | `punto_desde_latlng(lat, lng)`, `latlng_desde_punto(geom)`, `circulo_a_poligono(lat, lng, radio_m)` y `cerca_de(columna, lat, lng, metros)`, que castea a `::geography` para que la distancia sea en **metros**. Entregar en los primeros días: A lo necesita |
| — | Hacer el PR de `feature/BaseCompleta` → `develop` cuando esté listo |

### B2. Solicitudes de ayuda + clasificación por IA + SOS (Sprint 2)
**Para qué:** pantallas "Solicitar ayuda" y SOS de la app, y la de solicitudes del panel (prioridad manual sobre la de la IA). Es la parte de IA del pitch.

| Archivo | Qué va |
|---|---|
| `app/models/solicitud_ayuda.py` + migración | Columna `tipo` (`medica, alimentaria, refugio, rescate, ropa, otro`), `direccion`, estados acordados. El SOS usa `origen` (`manual` / `acelerometro` / `sos`) |
| `app/routes/solicitudes_ayuda_routes.py` (+ controller, service, schema, `solicitudes_ayuda_repository.py`) | `POST /solicitudes-ayuda` (guarda con `prioridad_ia=pendiente` y encola el job), `POST /solicitudes-ayuda/sos` (solo ubicación, nace con prioridad `critica`), `GET` (filtros; el ciudadano ve las suyas), `GET /{id}`, `PATCH /{id}/prioridad` (admin: `prioridad_manual` y `modificado_por`), `PATCH /{id}/estado`. Siempre exponer `prioridad_efectiva = prioridad_manual ?? prioridad_ia` |
| `app/integrations/ia_client.py` | Llamada a Claude (`anthropic`) que devuelve `{prioridad, confianza, razonamiento, organizacion_sugerida}` validado con Pydantic. Si falla, la solicitud queda `pendiente`, nunca se cae |
| `app/jobs/eventos/clasificar_prioridad_ia.py` | Job Celery idempotente (si ya tiene prioridad, no hace nada), con reintentos y backoff |
| **Nuevos:** `app/routes/asignaciones_routes.py` (+ controller, service, schema, `asignaciones_repository.py`) | `POST /solicitudes-ayuda/{id}/asignar` y `POST /reportes/{id}/asignar` (el voluntario toma un caso de su organización), `GET /asignaciones/mias` (alimenta el inicio del voluntario: "tareas asignadas"), `PATCH /asignaciones/{id}` (finalizar o cancelar; al finalizar pasa la solicitud a `atendida`). El voluntario **solo** cambia el estado de sus propias asignaciones |
| `tests/unit/jobs/test_clasificar_prioridad_ia.py` | Con la IA simulada (mock): respuesta válida, inválida y timeout |

### B3. Alertas y notificaciones push (Sprint 2)
**Para qué:** pantalla de alertas de la app y alertas recientes del inicio. El admin crea una alerta y avisa a todos los que están dentro de la zona.

| Archivo | Qué va |
|---|---|
| `app/routes/alertas_routes.py` (+ controller, service, schema, repository) | `GET /alertas` (vigentes; con `?lat=&lng=` solo las que me afectan), `POST /alertas` (admin; zona como polígono o círculo), `PATCH /alertas/{id}` (desactivar) |
| `app/models/alerta.py` + migración | `vigente_hasta`, `activa`, `nivel` |
| `app/integrations/firebase_client.py` | Envío de push en lote. Si no hay credenciales, solo deja un log (para desarrollo) |
| `app/jobs/eventos/notificar_alerta_zona.py` | Usuarios con `ubicacion_actual` dentro del polígono → push |
| `app/jobs/eventos/notificar_voluntarios_cercanos.py`, `notificar_persona_encontrada.py` | Los que encola A desde reportes y personas |
| `app/integrations/twilio_client.py` + `app/jobs/eventos/enviar_sms_respaldo.py` | SMS a contactos de emergencia cuando se activa el SOS |
| — | Registro del token del dispositivo: `POST /usuarios/me/dispositivo` (coordinar con A, que es dueño de `usuarios`) |

### B4. Centros de ayuda y mapa (Sprint 2)
**Para qué:** pantalla de centros de la app (búsqueda, distancia), el mapa de emergencia y el mapa operativo del panel.

| Archivo | Qué va |
|---|---|
| `app/models/centro_ayuda.py` + migración | `nombre String(100)`, `tipo` enum, `estado`, `direccion`, `organizacion_id` |
| `app/routes/centros_ayuda_routes.py` (+ resto) | `GET /centros-ayuda?lat=&lng=&radio=&tipo=&q=` ordenado por distancia, con `distancia_m` en la respuesta. `POST` y `PATCH` de admin |
| **Nuevo:** `app/routes/mapa_routes.py` (+ controller, service) | `GET /mapa?lat=&lng=&radio=&capas=reportes,solicitudes,centros,zonas,alertas` → lista de `PuntoMapa`. A los ciudadanos les devuelve la ubicación de las solicitudes **aproximada** (requisito legal de ubicación) |

### B5. Zonas peligrosas y donaciones (Sprint 3)
**Para qué:** pantallas de zonas y donaciones de la app y del panel (incluye campañas).

| Archivo | Qué va |
|---|---|
| `app/models/zona_peligrosa.py` + migración | `nombre`, `nivel`, `descripcion`, estados acordados. Guardar `centro`, `radio_m` y el polígono derivado (`ST_Buffer`) |
| `app/routes/zonas_peligrosas_routes.py` (+ resto) | `GET` (por cercanía), `POST`/`PATCH` de admin |
| `app/models/donacion.py` + **nuevo** `app/models/campana.py` + migración | Categoría, estado, monto. Campañas con meta, recaudado, unidad y `fecha_fin` |
| `app/routes/donaciones_routes.py` (+ resto) | `GET/POST/PATCH /donaciones`, `GET/POST/PATCH /donaciones/campanas` |

### B6. Jobs programados (Sprint 3)
**Para qué:** mantener los datos al día sin intervención manual, y cumplir la retención de datos.

| Archivo | Qué va |
|---|---|
| `app/jobs/beat_schedule.py` | Registrar los 4 jobs con `crontab` |
| `app/jobs/programados/expirar_alertas.py` | Cada hora: desactiva las alertas con `vigente_hasta` vencido |
| `app/jobs/programados/marcar_reportes_no_verificables.py` | Diario: reportes `pendiente` con más de X días |
| `app/jobs/programados/recalcular_estadisticas.py` | Diario: cachea los números del dashboard |
| `app/jobs/programados/limpiar_datos_retencion.py` | Diario: borra fotos y ubicaciones vencidas (`RETENCION_*` del `.env`) |

### B7. Sincronización offline (Sprint 4, evolución)
**Para qué:** la contingencia sin conexión. La app guarda reportes y solicitudes en su cola local y los manda en lote cuando vuelve la señal.

| Archivo | Qué va |
|---|---|
| `app/routes/offline_routes.py` (+ controller, service, schema, `cola_alertas_offline_repository.py`) | `POST /offline/sync` recibe el lote y responde `202` con el id del procesamiento |
| `app/jobs/eventos/procesar_lote_offline.py` | Deduplica por `uuid_origen`, crea los reportes y solicitudes reales y marca `sincronizado` |
| `tests/unit/jobs/test_procesar_lote_offline.py` | El mismo lote enviado dos veces no duplica nada |

---

## 8. Checklist de cada Pull Request

- [ ] Rama creada desde `develop` actualizado.
- [ ] Respeta las 4 capas (sin SQL en controllers, sin HTTP en services).
- [ ] Endpoints protegidos con `require_role` y acotados por organización.
- [ ] Respuesta igual al contrato (`docs/API_CONTRATO.md`).
- [ ] Migración probada con `upgrade`, `downgrade` y otra vez `upgrade`. `alembic heads` muestra una sola línea.
- [ ] Tests del módulo pasan: `docker compose exec api pytest`.
- [ ] Si agregó dependencias: `pip check` limpio.
- [ ] Avisar a Oscar o Elkin qué endpoints quedaron listos para conectar.

---

## Estado al 29-oct-2026 (cierre del Sprint 4)

Desde el 29-oct, Sergio ya no toca backend: B3, B5, B6 y B7 pasaron a Dev A, junto con dos módulos que no estaban en el plan (sismos y "¿Estás bien?"). La migración 0016 también la hizo Dev A.

| Tarea | Estado | Migración |
|---|---|---|
| A7 auditoría y guía de emergencia | ✅ | (sin migración) |
| B3 alertas por zona + push (`firebase_client`; sin credenciales solo escribe en el log) | ✅ | 0016 (zonas) y 0017 |
| B8 **nuevo**: sismos (feed del USGS cada minuto, alerta automática desde M4.5, simulacro) | ✅ | 0018 |
| "¿Estás bien?" (check-ins con vencimiento y SMS a los contactos) | ✅ | 0019 |
| B7 ampliado: `/offline/sync` + `/offline/relevo` (Bluetooth), firma HMAC, origen `mesh` | ✅ | 0020 |
| B5 campañas y donaciones (sin cobros en la app) | ✅ | 0021 |
| B6 jobs programados: expirar alertas, reportes no verificables a las 72 h, retención | ✅ | — |
| Seed de demo (`scripts/seed/datos_demo.py`) y matriz de permisos por rol | ✅ | — |
| **Pendiente (Sergio):** proyecto de Firebase, credenciales y prueba real del push | ⏳ | — |
