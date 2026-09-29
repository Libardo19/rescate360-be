import redis
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine

app = FastAPI(title="RESCATE360 API", version="0.1.0")


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
