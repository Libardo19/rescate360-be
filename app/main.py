from pathlib import Path

import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import RequestIdMiddleware, configurar_logging
from app.middlewares.error_handler_middleware import registrar_manejadores_errores
from app.routes import auth_routes
from app.routes import solicitudes_ayuda_routes
from app.routes import asignaciones_routes
from app.routes import usuarios_routes
from app.routes import organizaciones_routes
from app.routes import mapa_routes
from app.routes import reportes_routes
from app.routes import centros_ayuda_routes
from app.routes import zonas_peligrosas_routes
from app.routes import alertas_routes
from app.routes import sismos_routes
from app.routes import offline_routes
from app.routes import personas_desaparecidas_routes
from app.routes import dashboard_routes
from app.routes import auditoria_routes
from app.routes import guia_emergencia_routes

configurar_logging()

app = FastAPI(title="RESCATE360 API", version="0.1.0")

# En local se acepta cualquier puerto de localhost: Flutter Web (`flutter run -d chrome`)
# abre la app en un puerto distinto cada vez. Fuera de local solo valen CORS_ORIGINS.
_CORS_LOCAL = r"http://(localhost|127\.0\.0\.1)(:\d+)?" if get_settings().app_env == "local" else None

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_origin_regex=_CORS_LOCAL,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestIdMiddleware)
registrar_manejadores_errores(app)

# Routers: cada dueño agrega su línea (archivo compartido, solo agregar).
app.include_router(auth_routes.router)
# Antes de usuarios: trae /usuarios/me/llave-offline, que no debe leerse como /usuarios/{usuario_id}
app.include_router(offline_routes.router)
app.include_router(solicitudes_ayuda_routes.router)
app.include_router(asignaciones_routes.router)
app.include_router(usuarios_routes.router)
app.include_router(organizaciones_routes.router)
app.include_router(mapa_routes.router)
app.include_router(reportes_routes.router)
app.include_router(centros_ayuda_routes.router)
app.include_router(zonas_peligrosas_routes.router)
app.include_router(alertas_routes.router)
app.include_router(sismos_routes.router)
app.include_router(personas_desaparecidas_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(auditoria_routes.router)
app.include_router(guia_emergencia_routes.router)

# Fotos y videos subidos (evidencias). Con bucket, esto lo sirve el bucket y no la API.
_uploads = Path(get_settings().uploads_dir)
_uploads.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_uploads), name="uploads")


@app.get("/health", tags=["health"])
def health():
    """La API está arriba."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready():
    """La API puede atender: responden PostGIS y Redis."""
    checks = {}
    try:
        with engine.connect() as conn:
            checks["postgis"] = conn.execute(text("SELECT postgis_lib_version()")).scalar()
    except Exception as exc:
        checks["postgis"] = f"error: {exc.__class__.__name__}"
    try:
        redis.Redis.from_url(get_settings().redis_url).ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc.__class__.__name__}"

    ok = not any(str(v).startswith("error") for v in checks.values())
    return JSONResponse({"status": "ok" if ok else "degraded", **checks}, status_code=200 if ok else 503)
