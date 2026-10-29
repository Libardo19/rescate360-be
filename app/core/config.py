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

    # IA (Gemini) que clasifica prioridad y organización de solicitudes y reportes.
    # Sin clave, o si Gemini no responde, se clasifica con reglas (clasificador_reglas.py).
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    # Se prueban en orden si el principal está saturado o retirado (Google los rota seguido)
    gemini_modelos_respaldo: list[str] = ["gemini-flash-lite-latest", "gemini-flash-latest"]
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_timeout: int = 20
    firebase_credentials_path: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    storage_bucket: str = ""
    # Carpeta local de fotos y videos (servida en /uploads) y tamaños máximos por archivo
    uploads_dir: str = "uploads"
    foto_max_mb: int = 5
    video_max_mb: int = 30

    # Sismos (feed público del USGS; el del SGC se usa si expone uno consumible)
    sismos_feed_url: str = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
    # Desde esta magnitud se publica la alerta y se pregunta "¿Estás bien?" a quien esté cerca
    sismos_magnitud_alerta: float = 4.5
    # Minutos para responder el "¿Estás bien?" antes de avisar a los contactos de emergencia
    check_in_minutos: int = 10

    retencion_fotos_dias: int = 90
    retencion_ubicaciones_dias: int = 30

    # Orígenes que pueden llamar la API desde el navegador (panel web de administración).
    # En .env como JSON: CORS_ORIGINS=["http://localhost:5173"]
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Versión de la política de tratamiento de datos que acepta el usuario al registrarse
    version_politica_datos: str = "1.0"

    # Horas que dura el código de activación que el admin le entrega a un voluntario o admin nuevo
    activacion_horas: int = 72
    # Minutos que dura el código de "olvidé mi contraseña" (llega por SMS o correo)
    recuperacion_minutos: int = 15

    # Correo saliente por SMTP. Con mail_enabled=False no se envía nada: solo queda en el log.
    # 465 = TLS directo; 587 = STARTTLS.
    mail_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = ""
    mail_from_name: str = "RESCATE360"

    # Super admin inicial (scripts/seed/crear_super_admin.py). Nunca se crea por registro.
    super_admin_nombre: str = "Super Admin"
    super_admin_email: str = ""
    super_admin_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
