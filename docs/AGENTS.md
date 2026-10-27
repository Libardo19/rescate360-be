# RESCATE360 — Guía para asistentes de IA

> **Documento autosuficiente.** Contiene todo el contexto necesario para trabajar en este
> backend sin haber leído ningún otro archivo: pégalo completo en cualquier IA (ChatGPT,
> Gemini, Claude, Cursor, opencode...) y esa IA sabrá cómo está organizado el proyecto,
> qué código generar y qué reglas respetar.
>
> Si además trabajas sobre el repo, el orden de lectura recomendado es:
> este archivo → `README.md` (stack y ambiente) → `docs/PLAN_BACKEND.md` (división de tareas
> y permisos por endpoint) → `docs/API_CONTRATO.md` (contrato HTTP).

---

## 1. Proyecto y stack

**RESCATE360** es una plataforma comunitaria de apoyo ante emergencias (terremotos,
inundaciones, desapariciones). Backend en Python que expone una API REST consumida por:

- una **app móvil Flutter** (ciudadanos y voluntarios),
- un **panel web de administración React** (administradores y super admin),
- dos servicios externos: la **app y el panel existen ya con pantallas hechas**; el backend
  se construyó después y debe respetar el contrato que ellos esperan (sección 6).

Universidad Popular del Cesar · Ingeniería de Software II.

| Pieza | Tecnología |
|---|---|
| API | Python 3.12 + **FastAPI** (Uvicorn) |
| BD | **PostgreSQL 16 + PostGIS 3.4** (SQLAlchemy 2.0 con tipo `Mapped`, GeoAlchemy2) |
| Migraciones | **Alembic** |
| Colas/trabajos | **Celery + Redis** (worker + beat) |
| Auth | JWT (`PyJWT`) + `bcrypt` (sin passlib) |
| Externos | IA para priorizar solicitudes, Firebase (push), Twilio (SMS SOS) |
| Pruebas | `pytest` + `httpx` (`TestClient` de FastAPI) |
| Validación | Pydantic v2 (`pydantic-settings` para `.env`) |

**Arquitectura de 4 capas + repositorio** (no se rompe jamás):

```
routes → middlewares → controllers → services → repositories → PostgreSQL
                                                        ↘ Celery (jobs)
```

### Comandos

```bash
# Ambiente completo (Docker: db, redis, api, worker, beat, pgadmin)
cp .env.example .env                       # una sola vez
docker compose up -d --build
docker compose exec api alembic upgrade head    # aplicar migraciones
docker compose exec api pytest                   # correr pruebas
docker compose exec api alembic heads            # debe mostrar UNA sola línea

# Crear una migración nueva (siempre tras git pull origin develop)
docker compose exec api alembic revision --autogenerate -m "crear X" --rev-id 000N

# Endpoints locales
# API:  http://localhost:8000/docs    pgAdmin: http://localhost:5050
# BD:   localhost:5435 (fuera de Docker); dentro de Docker: db:5432
```

CI (`.github/workflows/ci.yml`) en cada PR: `pip install` → `pip check` → `alembic upgrade head` → `pytest -q`.

---

## 2. Cómo se procesa una petición

Ejemplo real: `POST /auth/login`.

| Paso | Carpeta | Qué ocurre |
|---|---|---|
| 1 | `app/routes/` | Declara `router.post("/login", response_model=SesionOut)` → llama a `auth_controller.login`. **Cero lógica.** |
| 2 | `app/middlewares/` | Si el endpoint lo pide: `get_current_user` valida el JWT, `require_role` valida el rol, `error_handler_middleware` convierte excepciones en respuesta, `audit_middleware` fija quién es el actor. |
| 3 | `app/controllers/` | Recibe los datos Pydantic, llama al service y devuelve la respuesta. **Nunca toca SQL.** |
| 4 | `app/services/` | Lógica de negocio: reglas, permisos de alcance, `.delay()` de jobs, lanza excepciones de negocio. **Nunca sabe de HTTP.** |
| 5 | `app/repositories/` | **Único** lugar con `select()`/SQLAlchemy sobre los modelos. |
| 6 | `app/models/` + `app/schemas/` | El modelo mapea la tabla; los schemas Pydantic validan la entrada y serializan la salida (y definen el JSON que ven los front). |

---

## 3. Qué va en cada carpeta

| Carpeta | **Va** | **No va** |
|---|---|---|
| `app/routes/` | Un `<modulo>_routes.py`: `APIRouter` con prefijo, tags, verbo, `response_model` y el controller | Lógica, `if` de negocio, queries, `Depends(get_db)` |
| `app/middlewares/` | Corta transversal: `auth_middleware` (JWT → `Usuario`), `role_middleware` (`require_role`, `alcance_organizacion`, `solo_propio`), `error_handler_middleware`, `validation_middleware` (422), `audit_middleware` (`SET LOCAL app.usuario_id`) | Lógica de negocio de un módulo |
| `app/controllers/` | Un `<modulo>_controller.py`: una función por endpoint; arma la respuesta, llama al service, usa `Depends(...)` | SQL, `select()`, reglas de negocio, modelos Pydantic definidos inline |
| `app/services/` | Un `<modulo>_service.py`: reglas de negocio, transiciones de estado, llamadas a `integrations/`, `.delay()`, `raise Conflicto(...)` | HTTP (`Request`/`Response`), SQL crudo, queries |
| `app/repositories/` | Un `<tabla>_repository.py`: queries SQLAlchemy, filtros, `.offset().limit()` | Lógica de negocio, HTTP, Celery |
| `app/models/` | Un modelo SQLAlchemy/GeoAlchemy2 por tabla; enums en `enums.py`; exports en `__init__.py` | Validaciones Pydantic, SQL raw |
| `app/schemas/` | `XxxIn` (entrada), `XxxOut` (salida, `model_config = ConfigDict(from_attributes=True)`) | Lógica, acceso a datos |
| `app/core/` | Transversal: `config.py` (Settings), `database.py` (engine/`Base`/`get_db`), `security.py` (bcrypt+JWT), `excepciones.py` (errores de negocio), `logging.py` (X-Request-ID), `celery_app.py` (cliente Celery + lista `JOBS`) | Código de un módulo concreto |
| `app/integrations/` | Clientes externos: `ia_client.py`, `firebase_client.py`, `twilio_client.py`, `storage_client.py` | Lógica de negocio |
| `app/jobs/eventos/` | Tareas Celery disparadas por una acción (`.delay()` desde un service) | Tareas periódicas |
| `app/jobs/programados/` | Tareas Celery Beat (crontab en `beat_schedule.py`) | — |
| `app/jobs/beat_schedule.py` | El cron de los jobs programados | — |
| `app/utils/` | Helpers puros: `geo.py` (PostGIS), `paginacion.py`, `telefono.py` | Estado, BD |
| `migrations/versions/` | Archivos Alembic `000N_*.py` | Código de negocio |
| `tests/unit/` | `services/`, `jobs/`, `middlewares/`, `test_security.py`, `test_telefono.py` | — |
| `tests/integration/` | `test_<modulo>_api.py` (pasa por `TestClient` y BD real) | — |
| `scripts/seed/` | Datos de prueba (super admin, organizaciones, guía) | Código de producción |
| `docs/` | `PLAN_BACKEND.md`, `API_CONTRATO.md`, `legal/` (política de datos, términos) | — |
| Raíz | `docker-compose.yml`, `Dockerfile`, `alembic.ini`, `requirements*.txt`, `.env.example` | — |

---

## 4. Ejemplos de código por capa (módulo real: `auth`)

Estos archivos existen y funcionan; **imita exactamente sus patrones**.

### 4.1 Ruta — `app/routes/auth_routes.py`

```python
from fastapi import APIRouter

from app.controllers import auth_controller
from app.schemas.auth_schema import SesionOut

router = APIRouter(prefix="/auth", tags=["auth"])

router.post("/registro", status_code=201, response_model=SesionOut, summary="Registro de ciudadano")(
    auth_controller.registrar
)
router.post("/login", response_model=SesionOut, summary="Iniciar sesión")(auth_controller.login)
router.post("/refresh-token", response_model=SesionOut, summary="Renovar la sesión")(auth_controller.refrescar)
```

> Al terminar el módulo, agregar su línea en `app/main.py` (archivo compartido, **solo agregar**):
> `app.include_router(auth_routes.router)`

### 4.2 Controller — `app/controllers/auth_controller.py`

```python
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth_schema import LoginIn, RefreshIn, RegistroIn, SesionOut
from app.services import auth_service


def registrar(datos: RegistroIn, request: Request, db: Session = Depends(get_db)) -> SesionOut:
    ip = request.client.host if request.client else None
    return auth_service.registrar(db, datos, ip)


def login(datos: LoginIn, db: Session = Depends(get_db)) -> SesionOut:
    return auth_service.login(db, datos)


def refrescar(datos: RefreshIn, db: Session = Depends(get_db)) -> SesionOut:
    return auth_service.refrescar(db, datos.refresh_token)
```

### 4.3 Service — `app/services/auth_service.py` (extracto)

```python
def registrar(db: Session, datos: RegistroIn, ip: str | None) -> SesionOut:
    """Autorregistro público: siempre crea un ciudadano (nunca otro rol)."""
    if usuarios_repository.obtener_por_email(db, datos.email):
        raise Conflicto("Ya existe una cuenta con ese correo", codigo="EMAIL_YA_REGISTRADO")

    try:
        usuario = usuarios_repository.crear(
            db, nombre=datos.nombre, email=datos.email, telefono=datos.telefono,
            password_hash=hash_password(datos.password), rol=RolUsuario.CIUDADANO,
        )
    except IntegrityError:
        db.rollback()
        raise Conflicto("Ya existe una cuenta con ese correo", codigo="EMAIL_YA_REGISTRADO") from None

    fijar_actor(db, usuario.id)                     # el actor de auditoría es el usuario
    consentimientos_repository.registrar(db, usuario_id=usuario.id, ...)
    db.commit()
    return _sesion(usuario)
```

Patrones del service:
- **excepciones de negocio** de `app/core/excepciones.py`: `NoAutenticado` (401),
  `SinPermiso` (403), `NoEncontrado` (404), `Conflicto` (409), `DatosInvalidos` (422).
  Siempre con `codigo="MAYUSCULAS_DE_MODULO"` (ej. `REPORTE_NO_ENCONTRADO`).
- `db.flush()` dentro del repository, **`db.commit()` solo en el service**.
- Antes de escribir por un usuario: `fijar_actor(db, usuario.id)` (alimenta la auditoría).

### 4.4 Repository — `app/repositories/usuarios_repository.py`

```python
def obtener_por_id(db: Session, usuario_id: UUID) -> Usuario | None:
    return db.get(Usuario, usuario_id)


def obtener_por_email(db: Session, email: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(func.lower(Usuario.email) == email.lower()))


def crear(db: Session, **campos) -> Usuario:
    usuario = Usuario(**campos)
    db.add(usuario)
    db.flush()          # asigna el id generado por la BD
    return usuario
```

### 4.5 Schema — `app/schemas/auth_schema.py` (extracto)

```python
class RegistroIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=50)
    email: EmailStr = Field(max_length=100)
    telefono: Telefono | None = None          # validador E.164 de app/utils/telefono.py
    password: str = Field(min_length=8)       # bcrypt rechaza > 72 bytes (BCRYPT_MAX_BYTES)
    acepta_tratamiento_datos: bool            # Ley 1581; debe ser True (field_validator)

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str) -> str:
        return valor.lower()


class SesionOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut                        # nunca expone password_hash
```

Los mensajes de validación van **en español** (los ven los usuarios).

### 4.6 Protección de endpoints — `app/middlewares/role_middleware.py`

```python
# 1) Restringir a roles:
@router.patch("/{id}/verificar")
def verificar(id: UUID, usuario: Usuario = Depends(require_role(RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN))):
    ...

# 2) Acotar los datos por organización (en el service o repository):
org_id = alcance_organizacion(usuario)     # None = sin filtro (solo super_admin)
if org_id is not None:
    consulta = consulta.where(Reporte.organizacion_objetivo_id == org_id)

dueno_id = solo_propio(usuario)            # el ciudadano solo ve lo que creó
if dueno_id is not None:
    consulta = consulta.where(Reporte.usuario_id == dueno_id)

# 3) Sobre un registro concreto (admin/voluntario solo en su organización):
verificar_misma_organizacion(usuario, reporte.organizacion_objetivo_id)
```

Atajos: `ROLES_ADMIN = (ADMINISTRADOR, SUPER_ADMIN)`, `ROLES_OPERATIVOS = (VOLUNTARIO, ADMINISTRADOR, SUPER_ADMIN)`, `es_super_admin(usuario)`.

### 4.7 Job Celery — patrón en `app/jobs/eventos/`

Los archivos existen como stubs; el patrón obligatorio (README):

```python
from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def clasificar_prioridad_ia(self, solicitud_id: str) -> dict:
    """Idempotente: si la solicitud ya tiene prioridad, no hace nada.
    Si la IA falla, la solicitud queda 'pendiente': jamás revienta el job."""
    ...
```

- Registrar cada job en la lista `JOBS` de `app/core/celery_app.py` (compartido, **solo agregar línea**).
- Los periódicos además van en `app/jobs/beat_schedule.py`.
- **La IA nunca decide sola:** `prioridad_manual` del administrador prevalece sobre `prioridad_ia`.
  Exponer siempre `prioridad_efectiva = prioridad_manual ?? prioridad_ia`.

### 4.8 Pruebas

**Unit** (`tests/unit/...`) — sin BD; para objetos de dominio usa `SimpleNamespace`:

```python
def _usuario(rol=RolUsuario.ADMINISTRADOR, organizacion_id=None):
    return SimpleNamespace(id=uuid4(), rol=rol, organizacion_id=organizacion_id or uuid4())

def test_access_token_lleva_rol_y_organizacion():
    usuario = _usuario()
    payload = decodificar_token(crear_access_token(usuario), TOKEN_ACCESS)
    assert payload["rol"] == "administrador"
```

**Integración** (`tests/integration/test_<modulo>_api.py`) — fixtures de `tests/conftest.py`:

```python
def test_login_correcto_actualiza_ultimo_acceso(cliente, crear_usuario, db):
    usuario = crear_usuario(RolUsuario.ADMINISTRADOR)   # crea su organización
    r = cliente.post("/auth/login", json={"email": usuario.email, "password": PASSWORD_PRUEBAS})
    assert r.status_code == 200, r.text
    assert r.json()["usuario"]["rol"] == "administrador"
```

| Fixture | Qué hace |
|---|---|
| `cliente` | `TestClient` de FastAPI con `get_db` sobrescrito |
| `db` | `Session` sobre BD `_test`; cada prueba se deshace al final (rollback) |
| `crear_usuario(rol, organizacion, estado, email, password)` | Crea usuario; voluntario/admin reciben organización nueva automáticamente |
| `crear_organizacion(nombre, tipo)` | Crea organización |
| `headers_de(usuario)` | `{"Authorization": "Bearer <access_token>"}` |
| `PASSWORD_PRUEBAS` | `"clave-de-prueba-123"` |

La BD de pruebas (`<DATABASE_URL>_test`) se crea y migra sola una vez por sesión.

---

## 5. Base de datos

**17 tablas.** Todas las PK son `UUID` con `server_default = gen_random_uuid()`.
Las columnas de tiempo son `timestamptz` (`server_default = now()`); `actualizado_en`
lleva `onupdate=func.now()`. Geografía: `Geometry` con `srid=4326` y `spatial_index=False`
(los índices GIST los crea la migración 0003).

### 5.1 Enums (15)

| Enum PG | Valores |
|---|---|
| `rol_usuario` | `ciudadano`, `voluntario`, `administrador`, `super_admin` |
| `estado_usuario` | `activo`, `en_espera`, `bloqueado` |
| `tipo_organizacion` | `bomberos`, `policia`, `cruz_roja`, `defensa_civil`, `ong`, `otro` |
| `estado_reporte` | `pendiente`, `verificado`, `rechazado`, `duplicado`, `no_verificable` |
| `estado_caso_persona` | `buscando`, `encontrado` |
| `estado_solicitud` | `pendiente`, `en_proceso`, `atendida`, `cancelada` |
| `tipo_solicitud` | `medica`, `alimentaria`, `refugio`, `rescate`, `ropa`, `otro` |
| `origen_solicitud` | `manual`, `acelerometro`, `sos` |
| `prioridad_solicitud` | `pendiente`, `baja`, `media`, `alta`, `critica` |
| `estado_zona` | `activa`, `resuelta` |
| `estado_asignacion` | `activa`, `finalizada`, `cancelada` |
| `metodo_envio` | `sms`, `mesh`, `local` |
| `operacion_auditoria` | `INSERT`, `UPDATE`, `DELETE` |
| `tipo_consentimiento` | `tratamiento_datos`, `ubicacion`, `foto_persona` |
| `plataforma_dispositivo` | `android`, `ios`, `web` |

Se declaran en `app/models/enums.py` con el helper `pg_enum(Clase, "nombre_pg")`.

### 5.2 Tablas

#### `usuarios`
| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | uuid | PK |
| `nombre` | varchar(50) | NOT NULL |
| `email` | varchar(100) | NOT NULL, UNIQUE |
| `telefono` | varchar(15) | NULL, formato E.164 `+573001234567` |
| `password_hash` | varchar(255) | NOT NULL (bcrypt) |
| `rol` | `rol_usuario` | NOT NULL, default `ciudadano` |
| `estado` | `estado_usuario` | NOT NULL, default `activo` |
| `ultimo_acceso` | timestamptz | NULL |
| `organizacion_id` | uuid | FK `organizaciones.id`, NULL |
| `ubicacion_actual` | Geometry(POINT,4326) | NULL |
| `creado_en` / `actualizado_en` | timestamptz | NOT NULL |

CHECK `chk_organizacion_segun_rol`: rol `voluntario`/`administrador` → `organizacion_id`
**NO NULL**; rol `ciudadano`/`super_admin` → `organizacion_id` **NULL**.
Índices: `ix_usuarios_organizacion_id`, `ix_usuarios_ubicacion_actual` (GIST).

#### `organizaciones`
`id` PK · `nombre` varchar(100) NOT NULL · `tipo` `tipo_organizacion` NOT NULL ·
`telefono_contacto` varchar(10) NULL · `zona_cobertura` Geometry(POLYGON,4326) NULL ·
`activa` bool NOT NULL default true · `creado_en`.
Índice GIST: `ix_organizaciones_zona_cobertura`.

#### `reportes`
| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | uuid | PK |
| `usuario_id` | uuid | FK `usuarios.id` NOT NULL |
| `tipo` | varchar(30) | NOT NULL |
| `descripcion` | text | NOT NULL |
| `foto_url` | varchar(500) | NULL |
| `ubicacion` | Geometry(POINT,4326) | NOT NULL |
| `estado` | `estado_reporte` | NOT NULL, default `pendiente` |
| `verificado_por` | uuid | FK `usuarios.id` NULL |
| `organizacion_objetivo_id` | uuid | FK `organizaciones.id` NULL (enruta el caso a una org) |
| `creado_en` / `actualizado_en` | timestamptz | NOT NULL |

Índices: `ix_reportes_ubicacion` (GIST), `ix_reportes_estado`.

#### `personas_desaparecidas`
`id` PK · `reportado_por` FK `usuarios` NOT NULL · `nombre` varchar(50) ·
`caracteristicas` text · `foto_url` varchar(500) NULL ·
`ultima_ubicacion` Geometry(POINT,4326) NOT NULL ·
`estado_caso` `estado_caso_persona` default `buscando` · `creado_en`.
Índice GIST: `ix_personas_desaparecidas_ultima_ubicacion`.

#### `solicitudes_ayuda`
| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | uuid | PK |
| `usuario_id` | uuid | FK `usuarios.id` NOT NULL |
| `descripcion` | text | NOT NULL |
| `tipo` | `tipo_solicitud` | NOT NULL, default `otro` |
| `ubicacion` | Geometry(POINT,4326) | NOT NULL |
| `origen` | `origen_solicitud` | NOT NULL, default `manual` (`sos` lo manda el botón) |
| `prioridad_ia` | `prioridad_solicitud` | NOT NULL, default `pendiente` |
| `prioridad_manual` | `prioridad_solicitud` | NULL (prevalece sobre la IA) |
| `organizacion_objetivo_id` | uuid | FK `organizaciones` NULL (sugerida por la IA) |
| `organizacion_manual_id` | uuid | FK `organizaciones` NULL (asignada por admin) |
| `confianza_ia` | float | NULL |
| `razonamiento_ia` | text | NULL |
| `modificado_por` | uuid | FK `usuarios.id` NULL |
| `estado` | `estado_solicitud` | NOT NULL, default `pendiente` |
| `creado_en` / `actualizado_en` | timestamptz | NOT NULL |

Índices: `ix_solicitudes_ayuda_ubicacion` (GIST), `ix_solicitudes_ayuda_estado_prioridad (estado, prioridad_ia)`.

#### `centros_ayuda`
`id` PK · `nombre` varchar(30) · `tipo` varchar(30) ·
`ubicacion` Geometry(POINT,4326) NOT NULL · `recursos_disponibles` text NULL ·
`gestionado_por` FK `usuarios` NOT NULL · `organizacion_id` FK `organizaciones` NULL*.
Índices: `ix_centros_ayuda_ubicacion` (GIST), `ix_centros_ayuda_organizacion_id`.

#### `alertas`
`id` PK · `tipo` varchar(30) · `mensaje` text ·
`zona_afectada` Geometry(POLYGON,4326) NOT NULL · `creado_por` FK `usuarios` NOT NULL ·
`creado_en` · `organizacion_id` FK `organizaciones` NULL*.
Índices: `ix_alertas_zona_afectada` (GIST), `ix_alertas_organizacion_id`.

#### `zonas_peligrosas`
`id` PK · `tipo_riesgo` varchar(30) · `area` Geometry(POLYGON,4326) NOT NULL ·
`estado` `estado_zona` default `activa` · `gestionado_por` FK `usuarios` NOT NULL ·
`actualizado_en` · `organizacion_id` FK `organizaciones` NULL*.
Índices: `ix_zonas_peligrosas_area` (GIST), `ix_zonas_peligrosas_organizacion_id`.

#### `donaciones`
`id` PK · `centro_id` FK `centros_ayuda` NOT NULL · `tipo` varchar(25) ·
`cantidad` int · `unidad` varchar(20) · `actualizado_en` ·
`organizacion_id` FK `organizaciones` NULL*.

> **\* Atención:** `organizacion_id` existe en la **BD** (la creó la migración 0003) pero
> **los modelos de estas 4 tablas todavía no la declaran**. Si generas código que la use,
> declara la columna también en el modelo (y verifica `alembic check`).

#### `asignaciones`
`id` PK · `solicitud_id` FK `solicitudes_ayuda` NULL · `reporte_id` FK `reportes` NULL ·
`voluntario_id` FK `usuarios` NOT NULL · `asignado_en` timestamptz ·
`estado_asignacion` `estado_asignacion` default `activa`.
CHECK `chk_asignacion_a_uno_solo`: exactamente uno de los dos FK no nulos.

#### `contactos_emergencia`
`id` PK · `usuario_id` FK `usuarios` NOT NULL · `nombre` varchar(50) ·
`telefono` varchar(15) NOT NULL (E.164, lo usa Twilio) · `parentesco` varchar(15) NULL.
Con trigger de auditoría.

#### `consentimientos` (Ley 1581)
`id` PK · `usuario_id` FK `usuarios` NOT NULL (índice) · `tipo` `tipo_consentimiento` ·
`aceptado` bool · `version_politica` varchar(20) · `ip` varchar(45) NULL · `creado_en`.
No se borra: retirar la autorización inserta otra fila con `aceptado = false`.
Con trigger de auditoría.

#### `dispositivos` (push)
`id` PK · `usuario_id` FK `usuarios` NOT NULL `ON DELETE CASCADE` (índice) ·
`token_push` varchar(255) UNIQUE · `plataforma` `plataforma_dispositivo` ·
`creado_en` · `actualizado_en`.

#### `auditoria` (la llena el trigger, jamás el código)
`id` PK · `tabla` varchar(100) (índice) · `registro_id` uuid (índice) ·
`operacion` `operacion_auditoria` · `usuario_id` FK `usuarios` NULL (índice) ·
`datos_anteriores` jsonb · `datos_nuevos` jsonb · `campos_modificados` text[] ·
`creado_en`.

Trigger `fn_auditoria()` en: `usuarios`, `reportes`, `solicitudes_ayuda`,
`personas_desaparecidas`, `zonas_peligrosas`, `alertas` (0003) +
`consentimientos`, `contactos_emergencia` (0005). Lee `current_setting('app.usuario_id')`,
que fija `audit_middleware` con `SET LOCAL` en cada petición.

#### `cola_alertas_offline`
`id` PK · `uuid_origen` uuid UNIQUE NOT NULL (clave de deduplicación) ·
`usuario_id` FK `usuarios` NOT NULL · `tipo` varchar(30) · `payload` jsonb ·
`ubicacion` Geometry(POINT,4326) NOT NULL · `metodo_envio` `metodo_envio` ·
`generado_en` timestamptz · `sincronizado` bool default false.
Índice GIST: `ix_cola_alertas_offline_ubicacion`.

#### `guia_emergencia`
`id` PK · `titulo` varchar(50) · `contenido` text · `categoria` varchar(25).

### 5.3 Convenciones geográficas

- La API recibe y devuelve **`{"lat": 10.46, "lng": -73.25}`** — nunca WKT ni GeoJSON.
  La conversión vive **solo** en `app/utils/geo.py` (`punto_desde_latlng`,
  `latlng_desde_punto`, `circulo_a_poligono`, `cerca_de`).
- En las consultas de distancia hay que castear a `::geography` (o usar `cerca_de`) para
  que los metros sean metros: `ST_DWithin` sobre `Geometry` se mide en **grados**.
- Índices GIST ya creados (0003): `usuarios.ubicacion_actual`, `organizaciones.zona_cobertura`,
  `reportes.ubicacion`, `personas_desaparecidas.ultima_ubicacion`, `solicitudes_ayuda.ubicacion`,
  `centros_ayuda.ubicacion`, `alertas.zona_afectada`, `zonas_peligrosas.area`,
  `cola_alertas_offline.ubicacion`.

---

## 6. Convenciones de API (contrato con los fronts)

| Tema | Regla |
|---|---|
| Nombres JSON | `snake_case` (igual que la BD) |
| Coordenadas | `{"lat", "lng"}` |
| Fechas | ISO 8601 con zona: `2026-10-08T14:30:00-05:00` |
| Teléfonos | E.164: `+573001234567` (`String(15)`; validar con `app/utils/telefono.py`) |
| Paginación | Entrada `?pagina=1&por_pagina=20` → salida `{items, total, pagina, por_pagina}` (usar `app/utils/paginacion.py`) |
| Errores de negocio | `{"detalle": "...", "codigo": "MAYUSCULAS"}` — se generan lanzando excepciones de `core/excepciones.py`; `error_handler_middleware` arma la respuesta |
| Errores de validación (422) | `{"codigo": "DATOS_INVALIDOS", "errores": [{"campo", "mensaje"}]}` con mensajes **en español** (`validation_middleware`) |
| Login | `POST /auth/login` → `{access_token, refresh_token, token_type, usuario}` |
| Rutas de admin | Las mismas rutas por recurso, filtradas por rol (no duplicar endpoints `/admin/...`) |

### Roles y alcance (resumen)

| Rol | Quién | Alcance |
|---|---|---|
| `ciudadano` | App móvil | Global; **solo sus propios** reportes/solicitudes (solo lectura) |
| `voluntario` | App móvil | Su organización; se asigna casos y cambia estado **solo de sus asignaciones** |
| `administrador` | Panel web | Su organización; verifica reportes, prioridad manual, gestiona recursos |
| `super_admin` | Panel web | Todo; gestiona organizaciones y usuarios; nunca se desactiva a sí mismo |

Regla fija: el sistema **nunca** puede quedar sin un `super_admin` activo, y
`super_admin` no puede quitarse el rol ni desactivarse.

Rutas previstas por módulo: `/auth`, `/organizaciones`, `/usuarios`, `/reportes`,
`/solicitudes-ayuda`, `/alertas`, `/centros-ayuda`, `/personas-desaparecidas`,
`/zonas-peligrosas`, `/donaciones`, `/guia-emergencia`, `/offline/sync`,
`/auditoria`, `/dashboard`.

---

## 7. Migraciones (Alembic)

**Cadena actual (lineal, un solo head):**

```
0001_habilitar_postgis → 0002_crear_esquema_inicial → 0003_indices_y_auditoria
→ 0004_solicitudes_tipo_estado → 0005_usuarios_consentimientos_dispositivos
```

Reglas:

1. `alembic heads` debe mostrar **una sola línea**. Dos migraciones con el mismo
   `down_revision` = dos heads = `alembic upgrade head` falla.
2. Antes de crear una: `git pull origin develop` y usar el **siguiente número libre**
   (`--rev-id 000N`). Si dos PR traen el mismo número, **el segundo en mergear** cambia
   su `rev-id` y su `down_revision`.
3. Siempre probar `upgrade → downgrade → upgrade`.
4. Solo se usa `--autogenerate` cuando los modelos reflejan todo lo que hay en la BD;
   si no, se escribe a mano (la 0005 fue escrita a mano por eso).
5. Los enums se agregan/renombran con SQL crudo (`ALTER TYPE ... ADD VALUE`,
   `RENAME VALUE`) y en el `downgrade` hay que recrear el tipo y migrar los datos
   con `USING ...::text::tipo`.

---

## 8. Git y trabajo en equipo (2 desarrolladores)

- **Ramas:** `feature/<modulo>-<nombre>` siempre desde `develop` actualizado.
  Se entra a `develop` solo por **Pull Request** con **CI verde** (pip check → alembic → pytest).
  `main` recibe `develop` al cerrar una entrega.
- **Un dueño por módulo** (ver `docs/PLAN_BACKEND.md` §5-7): el dueño toca sus archivos en
  `routes/`, `controllers/`, `services/`, `schemas/`, `repositories/`, `models/` y `tests/`.
  Si necesitas algo de un módulo ajeno, se lo pides a su dueño.
- **Archivos compartidos: solo agregar líneas** (sin reordenar ni reformatear, para que los
  merges no choquen):

  | Archivo | Quién agrega qué |
  |---|---|
  | `app/main.py` | Cada uno su `app.include_router(...)` |
  | `app/models/__init__.py` | Cada uno su `from app.models.x import X` |
  | `app/models/enums.py` | Cada uno sus enums **al final** |
  | `app/core/celery_app.py` | Cada uno sus jobs en la lista `JOBS` |
  | `requirements.txt` | Cada uno su dependencia con `==` y `pip check` limpio |

- **Checklist de cada PR** (PLAN §8): rama desde `develop` · respeta las 4 capas ·
  endpoints con `require_role` y alcance de organización · formato igual al contrato ·
  migración probada (upgrade/downgrade/upgrade) · `alembic heads` una sola línea ·
  `docker compose exec api pytest` verde · `pip check` limpio · avisar a los fronts
  qué endpoints quedaron listos.

---

## 9. Checklist: agregar un módulo nuevo

1. **Modelo** en `app/models/<tabla>.py` + línea en `models/__init__.py` + enums al final de `enums.py`.
2. **Migración** `000N` (número siguiente libre, cadena lineal, probada en ambos sentidos).
3. **Los 5 archivos:** `<modulo>_routes.py` → `<modulo>_controller.py` → `<modulo>_service.py`
   → `<modulo>_repository.py` → `<modulo>_schema.py`.
4. **Proteger:** `Depends(require_role(...))` + `alcance_organizacion` / `solo_propio`
   en el service/repository.
5. **Registrar** `app.include_router(...)` en `main.py` (solo agregar línea).
6. **Tests:** `tests/unit/services/test_<modulo>_service.py` +
   `tests/integration/test_<modulo>_api.py` (fixtures `cliente`, `crear_usuario`, `headers_de`).
7. Si tiene job: agregarlo a `JOBS` en `celery_app.py` (+ `beat_schedule.py` si es periódico)
   y **registrarlo también** en la tabla de jobs del README.

---

## 10. Reglas duras — SIEMPRE / NUCA

**SIEMPRE:**
- Respetar las 4 capas: SQL solo en `repositories/`, HTTP solo en `controllers/`.
- Proteger endpoints con `require_role` y acotar por organización.
- Excepciones de negocio en services (`NoEncontrado`, `Conflicto`, `SinPermiso`, `NoAutenticado`)
  con `codigo="MAYUSCULAS_DE_MODULO"`.
- `db.commit()` solo en el service; `db.flush()` en el repository.
- Jobs **idempotentes**; la IA de priorización **nunca decide sola**.
- Mensajes de error y validación **en español**.
- Antes de crear una migración: `git pull origin develop`; después: `alembic heads` con un solo head.
- `password` limitado a 72 bytes (bcrypt) y `JWT_SECRET` de 32+ caracteres.

**NUCA:**
- SQL, `select()` ni modelos en controllers; `Request`/`Response` en services.
- Exponer `password_hash` en ninguna respuesta (`UsuarioOut` no lo incluye).
- Crear roles distintos de `ciudadano` por registro público (solo el bootstrap crea super admins).
- Borrar filas de `auditoria` (se llena con trigger) ni escribirla desde código.
- Distancias en grados: usar `::geography` / `utils/geo.py`.
- Dos heads de Alembic; reformatear los archivos compartidos.
- Romper la compatibilidad de los contratos que ya esperan la app Flutter y el panel React.

---

## 11. Referencias (solo si trabajas sobre el repo)

| Archivo | Qué encuentra |
|---|---|
| `README.md` | Ambiente Docker, stack, arquitectura de 4 capas, jobs, roles, roadmap |
| `docs/PLAN_BACKEND.md` | División Dev A/Dev B, tareas por archivo (§6-7), matriz de permisos por endpoint (§4), diferencias modelo↔fronts (§3.2), checklist de PR (§8) |
| `docs/API_CONTRATO.md` | Contrato HTTP acordado con los fronts |
| `docs/AMBIENTACION.md` | Guía paso a paso del ambiente |
| `docs/legal/` | Política de tratamiento de datos y términos |
| `.env.example` | Todas las variables de configuración |
| `.github/workflows/ci.yml` | Pipeline de CI |

> Estado del proyecto: solo el módulo `auth` está implementado de punta a punta;
> el resto de carpetas contiene **stubs vacíos** esperando a su dueño (ver §5-7 de
> `docs/PLAN_BACKEND.md`).

---

## 12. Mantenimiento de este documento (para la IA asistente)

**Aviso a la IA:** esta sección es para ti. El usuario te pedirá leerla con una frase
como *"revisa el AGENTS.md"* o *"actualiza el AGENTS.md"*. En ese momento tu tarea es
**contrastar este documento con el estado real del proyecto** y corregirlo donde esté
desactualizado. El usuario tiene la última palabra sobre qué cambios aplicar.

### 12.1 Qué verificar (y con qué herramienta)

| Sección | Qué comparar | Cómo verificarlo |
|---|---|---|
| §1 Stack y comandos | `requirements*.txt`, `docker-compose.yml` (servicios y puertos), `.github/workflows/ci.yml` | Leer esos archivos; verificar que no cambió ninguna versión fijada ni el orden de CI |
| §1 Estado | Si `auth` sigue siendo el único módulo implementado | Contar archivos con contenido > 0 líneas en `routes/`, `controllers/`, `services/`, `repositories/`, `schemas/` |
| §3 Carpetas | Existencia de carpetas nuevas o eliminadas en `app/` | Listar `app/` real y comparar con la tabla |
| §4 Ejemplos de código | Que los fragmentos sigan siendo idénticos a los archivos reales | Releer `app/routes/auth_routes.py`, `auth_controller.py`, `auth_service.py`, `usuarios_repository.py`, `auth_schema.py`, `role_middleware.py`, `tests/conftest.py` |
| §5 Base de datos | Tablas, columnas, enums, índices y CHECK | Releer `app/models/*.py` (los 17 modelos) + `app/models/enums.py` + migraciones `0001`–`000N`; **manda el código, no este documento** |
| §5.2 Advertencia de `organizacion_id` | Si los modelos de `centros_ayuda`, `alertas`, `zonas_peligrosas` y `donaciones` ya declaran la columna | Comparar esos modelos con la migración 0003; si ya la declaran, quitar el asterisco y el párrafo |
| §6 Convenciones de API | Formatos de error, paginación, rutas y matriz de roles | Releer `core/excepciones.py`, `middlewares/validation_middleware.py`, `utils/paginacion.py`, `docs/API_CONTRATO.md` |
| §7 Migraciones | Cadena, `down_revision` y número de head | Listar `migrations/versions/*.py` y extraer `revision`/`down_revision`; debe ser lineal y **un solo head** |
| §8 Git | Archivos compartidos y dueños por módulo | Comparar con `docs/PLAN_BACKEND.md` §2 y §5-7 |
| §9-§10 | Que las reglas sigan vigentes | Contrastar con `README.md` y con el código de `core/security.py` (72 bytes, JWT) |
| §11 y §Final | Que los archivos referenciados existan | `Glob` sobre cada ruta citada |

### 12.2 Cómo corregir

1. **Primero informa**, después edita: enumera las diferencias encontradas
   (`sección X decía Y, ahora es Z`) y deja que el usuario apruebe.
2. Edita **solo lo que cambió**: conserva formato, tablas, numeración y redacción.
   Este documento es también el que reciben IAs externas: debe seguir siendo
   autosuficiente (nada de "mira el archivo tal").
3. Los hechos siempre salen **del código o de los archivos de config**, nunca de
   otro documento de `docs/` (esos también pueden estar viejos; si lo están,
   avísalo aparte).
4. Al terminar, actualiza el pie de estado (§11 final) con lo que haya cambiado
   (módulos nuevos implementados, número de migraciones, etc.).
5. **No hagas commit** salvo que el usuario lo pida explícitamente.

### 12.3 Señales de que este documento ya se quedó viejo

- Apareció una migración `000N+1` o cambió la cadena.
- Un stub de `§3`/`§11` dejó de estar vacío (nuevo módulo implementado).
- Cambió un formato del contrato (`§6`) o una regla de `§10`.
- Se agregó una carpeta nueva en `app/` o se eliminó una.
- Los fragmentos de `§4` ya no coinciden con los archivos reales.
