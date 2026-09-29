# RESCATE360 — Backend (API)

Plataforma de apoyo y coordinación comunitaria ante emergencias. Este repositorio contiene la **API** que consume la app móvil ([rescate360-fe](https://github.com/Libardo19/rescate360-fe)).

> RESCATE360 es una herramienta de apoyo comunitario. **No sustituye** a los organismos oficiales de atención de emergencias. En caso de riesgo vital: línea **123**.

Universidad Popular del Cesar · Ingeniería de Software II
Equipo: Libardo José Acosta García, Sergio Eli Saucedo, Oscar Javier Ávila Ovallos

> **Estado:** ambiente listo (Docker, dependencias, migraciones, CI). Los módulos todavía están vacíos.

---

## Stack

| Pieza | Tecnología |
|---|---|
| API | Python + **FastAPI** (Uvicorn) |
| Base de datos | **PostgreSQL 16 + PostGIS 3.4** (SQLAlchemy 2.0 + GeoAlchemy2) |
| Runtime | Python 3.12 en Docker (`python:3.12-slim`) |
| Herramientas | pgAdmin 4 (modelado y consulta de la BD) |
| Migraciones | **Alembic** |
| Colas / workers | **Celery + Redis** (Celery Beat para jobs programados) |
| Auth | JWT (`PyJWT`) + `bcrypt` |
| Externos | Servicio de IA (priorización), Firebase (push), Twilio (SMS de respaldo) |
| Pruebas | `pytest` + `httpx` |

## Ambiente de desarrollo (Docker)

> Guía paso a paso para montar el proyecto en tu PC: [docs/AMBIENTACION.md](docs/AMBIENTACION.md).

Todo el backend corre en contenedores: **no hace falta instalar Python ni PostgreSQL en el PC**. Solo se necesita Docker Desktop.

```bash
cp .env.example .env                              # una sola vez
docker compose up -d --build                      # levanta los 6 contenedores
docker compose exec api alembic upgrade head      # aplica las migraciones
```

| Contenedor | Qué es | Acceso desde tu PC |
|---|---|---|
| `rescate360-db` | PostgreSQL 16 + PostGIS 3.4 (`postgis/postgis:16-3.4`) | `localhost:5435` |
| `rescate360-redis` | Redis 7.4, broker de Celery | `localhost:6379` |
| `rescate360-api` | FastAPI con recarga automática | http://localhost:8000/docs |
| `rescate360-worker` | Worker de Celery (jobs por evento) | — |
| `rescate360-beat` | Celery Beat (jobs programados) | — |
| `rescate360-pgadmin` | pgAdmin 4, para ver tablas y el diagrama ER | http://localhost:5050 |

- **Salud:** `GET /health` (la API está arriba) y `GET /health/ready` (responden PostGIS y Redis).
- **pgAdmin:** abre sin login. El servidor *RESCATE360 (local)* ya está registrado; la primera vez pide la contraseña de la BD (`POSTGRES_PASSWORD` del `.env`). Para ver el modelado: clic derecho sobre la base `rescate360` → **ERD For Database**.
- **Puerto de la BD:** 5435 porque 5432-5434 los usan otros proyectos locales. Dentro de Docker la API siempre se conecta a `db:5432`.
- **Comandos útiles:** `docker compose logs -f api worker` · `docker compose exec api pytest` · `docker compose down` (conserva los datos) · `docker compose down -v` (borra la BD).
- **Editor:** el código se monta como volumen, así que lo que guardes se recarga solo. Si quieres autocompletado en VS Code, crea un venv local con Python 3.12 y `pip install -r requirements-dev.txt` (opcional).

### Dependencias

- `requirements.txt` (producción) y `requirements-dev.txt` (+ pytest, httpx), con versiones fijas probadas juntas con `pip check` sobre Python 3.12.
- **Base de datos (acordadas por el equipo, no se cambian):** `sqlalchemy==2.0.54`, `geoalchemy2==0.20.0`, `alembic==1.20.0`, `psycopg2-binary==2.9.13`.
- **Contraseñas con `bcrypt` directo, sin `passlib`**: passlib no se mantiene desde 2020 y falla con bcrypt 4.1+. bcrypt 5 rechaza contraseñas de más de 72 bytes, así que el schema de registro debe limitar el largo.
- **JWT con `PyJWT`** en lugar de `python-jose` (sin mantenimiento activo). `JWT_SECRET` debe tener 32+ caracteres.
- Solo se fijan dependencias directas; `greenlet` y demás transitivas las resuelve pip.
- Para agregar una librería: fijarla con `==` en el requirements, `docker compose build`, y verificar con `docker compose exec api pip check`.

### CI

`.github/workflows/ci.yml` levanta PostGIS y Redis como servicios, instala dependencias, corre `pip check`, `alembic upgrade head` y `pytest`.

## Arquitectura de 4 capas

Toda petición atraviesa las capas en el mismo orden:

```
Cliente Flutter → 1. routes → 2. middlewares → 3. controllers → 4. services → repositories → PostgreSQL / Redis
```

| Capa | Carpeta | Responsabilidad | Regla |
|---|---|---|---|
| 1. Rutas | `app/routes/` | Declaran endpoint, verbo y controlador | Sin lógica |
| 2. Middlewares | `app/middlewares/` | JWT, rol, validación, errores, auditoría | Se ejecutan antes del controlador |
| 3. Controladores | `app/controllers/` | Llaman al servicio y arman la respuesta HTTP | No saben de SQL |
| 4. Servicios | `app/services/` | Lógica de negocio, disparo de jobs | No saben de HTTP |

## Estructura

```
rescate360-be/
├── app/
│   ├── main.py                     # Punto de entrada FastAPI
│   ├── core/                       # config, database, security (JWT), celery_app, logging
│   ├── routes/                     # 1. <modulo>_routes.py
│   ├── middlewares/                # 2. auth, role, validation, error_handler, audit
│   ├── controllers/                # 3. <modulo>_controller.py
│   ├── services/                   # 4. <modulo>_service.py
│   ├── repositories/               # Acceso a datos (ORM) por tabla
│   ├── models/                     # Modelos SQLAlchemy / GeoAlchemy2 + enums
│   ├── schemas/                    # Esquemas Pydantic (entrada/salida)
│   ├── integrations/               # Clientes externos: IA, Firebase, Twilio, almacenamiento de fotos
│   ├── jobs/
│   │   ├── eventos/                # Jobs Celery disparados por una acción
│   │   ├── programados/            # Jobs Celery Beat periódicos
│   │   └── beat_schedule.py
│   └── utils/                      # geo (PostGIS), paginación
├── migrations/
│   ├── env.py                      # Integra GeoAlchemy2 con --autogenerate
│   ├── script.py.mako
│   └── versions/                   # 0001 lista; las demás se crean al hacer cada tabla
├── tests/
│   ├── unit/                       # services, jobs, middlewares
│   └── integration/                # test_<modulo>_api.py
├── scripts/seed/                   # Datos de prueba
├── docker/pgadmin/                 # servers.json: pgAdmin ya conectado a la BD
├── docs/legal/                     # Política de datos, términos y condiciones
├── .github/workflows/              # CI/CD
├── .env.example
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── requirements-dev.txt
```

## Módulos

Cada módulo tiene su archivo en `routes/`, `controllers/`, `services/` y `schemas/`.

| Módulo | Endpoints principales | Iteración |
|---|---|---|
| `auth` | `POST /auth/registro`, `/auth/login`, `/auth/refresh-token` | MVP |
| `organizaciones` | `POST/GET /organizaciones`, `GET/PATCH /organizaciones/{id}`, `POST/GET/PATCH/DELETE /organizaciones/{id}/administradores[/{usuario_id}]` — solo `super_admin` | MVP |
| `usuarios` | `GET/PATCH/DELETE /usuarios/{id}`, `POST /usuarios/{id}/contactos-emergencia` | MVP |
| `reportes` | `POST/GET /reportes`, `PATCH /reportes/{id}/verificar · rechazar · marcar-duplicado` | MVP |
| `solicitudes_ayuda` | `POST/GET /solicitudes-ayuda`, `PATCH …/{id}/prioridad`, `PATCH …/{id}/estado` | MVP |
| `alertas` | `GET/POST /alertas` | MVP |
| `centros_ayuda` | `GET /centros-ayuda` (por cercanía), `POST`, `PATCH` | MVP |
| `personas_desaparecidas` | `POST/GET /personas-desaparecidas`, `PATCH …/{id}/encontrado` | 2ª iteración |
| `zonas_peligrosas` | `GET/POST/PATCH /zonas-peligrosas` | 2ª iteración |
| `donaciones` | `GET/POST/PATCH /donaciones` | 2ª iteración |
| `guia_emergencia` | `GET/POST/PATCH /guia-emergencia` | 2ª iteración |
| `offline` | `POST /offline/sync` | Evolución |

## Jobs (Celery)

| Job | Tipo | Disparador |
|---|---|---|
| `clasificar_prioridad_ia` | Evento | Crear solicitud de ayuda (queda en `pendiente` hasta que responda la IA) |
| `notificar_alerta_zona` | Evento | Crear alerta: push a usuarios dentro del polígono |
| `notificar_voluntarios_cercanos` | Evento | Crear reporte |
| `notificar_persona_encontrada` | Evento | Marcar persona como encontrada |
| `enviar_sms_respaldo` | Evento | Usuarios sin la app (Twilio) |
| `procesar_lote_offline` | Evento | `POST /offline/sync` (deduplica por `uuid_origen`) |
| `expirar_alertas` | Programado | Cada hora |
| `marcar_reportes_no_verificables` | Programado | Diario |
| `recalcular_estadisticas` | Programado | Diario |
| `limpiar_datos_retencion` | Programado | Diario: borra fotos y ubicaciones vencidas (Ley 1581) |

Todos los jobs deben ser **idempotentes**. La IA **nunca decide sola**: `prioridad_manual` del administrador prevalece sobre `prioridad_ia`.

## Migraciones (orden)

`0001_habilitar_postgis` → `0002_crear_usuarios` → `0003_crear_contactos_emergencia` → `0004_crear_reportes` → `0005_crear_personas_desaparecidas` → `0006_crear_solicitudes_ayuda` → `0007_crear_centros_ayuda` → `0008_crear_alertas` → `0009_crear_zonas_peligrosas` → `0010_crear_donaciones` → `0011_crear_guia_emergencia` → `0012_crear_cola_alertas_offline` → `0013_indices_busqueda` → `0014_crear_auditoria` → `0015_crear_consentimientos` → `0016_crear_organizaciones`

Solo existe `0001`. Cada una de las demás se crea cuando se implemente su tabla, con su número fijo:

```bash
docker compose exec api alembic revision --autogenerate -m "crear usuarios" --rev-id 0002
```

Las migraciones 0014 y 0015 **no están en el modelo de datos original**. Se agregaron por el marco legal: trazabilidad de quién verificó o modificó qué, y registro de la autorización de tratamiento de datos (Ley 1581 de 2012).

La migración **0016** agrega la tabla `organizaciones` y la columna `usuarios.organizacion_id`, que queda **nullable a propósito**: solo el `super_admin` se registra sin organización. `usuarios.rol` admite `ciudadano`, `voluntario`, `administrador` y `super_admin`.

## Roles

El `Administrador` está **acotado a una organización** (cada organización —p. ej. una fundación, un cuerpo de bomberos o una ONG— tiene sus propios administradores). El `Super admin` es el único rol **global**: no pertenece a ninguna organización y opera sobre todas.

| Función | Ciudadano | Voluntario | Administrador | Super admin |
|---|:---:|:---:|:---:|:---:|
| Mapa, alertas, centros, guía | ✅ | ✅ | ✅ | ✅ |
| Reportar / solicitar ayuda | ✅ | ✅ | ✅ | ✅ |
| Seguimiento de solicitudes/reportes | ❌ | ✅ | ✅ | ✅ |
| Verificar / rechazar reportes | ❌ | ❌ | ✅ | ✅ |
| Modificar prioridad de IA | ❌ | ❌ | ✅ | ✅ |
| Gestionar centros, zonas, alertas, donaciones, usuarios | ❌ | ❌ | ✅ | ✅ |
| Crear organizaciones | ❌ | ❌ | ❌ | ✅ |
| Crear administradores de una organización | ❌ | ❌ | ❌ | ✅ |
| Quitar / desactivar administradores de una organización | ❌ | ❌ | ❌ | ✅ |
| Mover recursos entre organizaciones | ❌ | ❌ | ❌ | ✅ |
| Eliminar o desactivar una organización | ❌ | ❌ | ❌ | ✅ |

### Rol `super_admin`

Es el **dueño de la plataforma**. Su responsabilidad principal es la **estructura multi-organización**: crear organizaciones y crear los administradores que las gobiernan. Además tiene acceso a **todas las funciones** de los demás roles, en **todas** las organizaciones.

| Capacidad | Detalle |
|---|---|
| Crear organizaciones | `POST /organizaciones` — alta con nombre, NIT, municipio, tipo y datos de contacto |
| Crear admins de organización | `POST /organizaciones/{id}/administradores` — crea el usuario o promueve un ciudadano existente a `administrador` de esa organización |
| Administrar admins | `GET /organizaciones/{id}/administradores`, `PATCH/DELETE /organizaciones/{id}/administradores/{usuario_id}` (revocar, cambiar a ciudadano) |
| Gestión de organizaciones | `GET/PATCH /organizaciones`, `GET /organizaciones/{id}` — listar, editar, activar/desactivar |
| Acceso total | Todos los endpoints de todos los módulos, de cualquier organización, sin filtro de alcance |

Reglas de implementación:

- **Alcance global vs. scoped:** `super_admin` es el único rol con `organizacion_id = NULL`. Los usuarios `voluntario` y `administrador` pertenecen a exactamente una organización.
- **Filtro obligatorio en repositorios:** las consultas se acotan por `organizacion_id` salvo que quien llama sea `super_admin`; este último puede además pasar `?organizacion_id=` para filtrar por una en concreto.
- **El super admin se crea por bootstrap,** no por autorregistro: lo siembra `scripts/seed/` o una migración inicial. `POST /auth/registro` nunca puede asignar este rol.
- **Autoprotección:** un `super_admin` no puede desactivarse ni quitarse el rol a sí mismo, y el sistema no permite quedar sin ningún `super_admin` activo.
- **Trazabilidad total:** toda acción suya queda en `auditoria` con `usuario_actor_id` y `organizacion_id` de la organización afectada.
- **Job de mantenimiento:** `limpiar_datos_retencion` y el resto de jobs programados corren igual para todos; el super admin solo interviene si se requiere un ajuste puntual.

## Requisitos legales que afectan al backend

- **Autorización de datos** (Ley 1581/2012, Decreto 1074/2015): guardar el consentimiento de cada usuario (`consentimientos`) y permitir consultar, corregir y eliminar sus datos.
- **Ubicación**: la ubicación exacta de quien pide ayuda solo la ven voluntarios o administradores asignados. Los demás ciudadanos ven un punto aproximado.
- **Fotos sensibles y de menores** (Ley 1098/2006): acceso restringido y borrado por retención.
- **Auditoría** (Ley 1273/2009): `audit_middleware` + tabla `auditoria` con quién revisó qué y cuándo. Se registra también el alta de organizaciones y de sus administradores por parte del `super_admin`.
- **IA** (CONPES 4144/2025): guardar la prioridad sugerida junto a la decisión humana final.

## Roadmap (8 semanas)

| Semana | Entregable |
|---|---|
| 1 | Setup, arquitectura de 4 capas, migraciones 0001-0003, autenticación |
| 2 | `super_admin`, organizaciones, admins de organización, mapa (consultas geoespaciales) + reportes |
| 3 | Solicitudes de ayuda + job de clasificación por IA |
| 4 | Verificación administrativa + alertas + centros — **cierre MVP** |
| 5 | Personas desaparecidas + zonas peligrosas |
| 6 | Donaciones + guía de emergencia — **cierre 2ª iteración** |
| 7 | `procesar_lote_offline` (prueba de concepto de contingencia) |
| 8 | Pruebas integrales, seguridad, documentación y pitch |
