from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración leída de variables de entorno (o del archivo .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"

    database_url: str
    redis_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_expires_min: int = 30
    jwt_refresh_expires_days: int = 7

    ia_api_key: str = ""
    firebase_credentials_path: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    storage_bucket: str = ""

    retencion_fotos_dias: int = 90
    retencion_ubicaciones_dias: int = 30

    # Orígenes que pueden llamar la API desde el navegador (panel web de administración).
    # En .env como JSON: CORS_ORIGINS=["http://localhost:5173"]
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Versión de la política de tratamiento de datos que acepta el usuario al registrarse
    version_politica_datos: str = "1.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
