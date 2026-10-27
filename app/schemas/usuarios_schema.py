from datetime import datetime
from uuid import UUID

from geoalchemy2.elements import WKBElement
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import BCRYPT_MAX_BYTES
from app.models.enums import EstadoUsuario, PlataformaDispositivo, RolUsuario, TipoConsentimiento
from app.schemas.solicitudes_ayuda_schema import LatLng
from app.utils.geo import latlng_desde_punto
from app.utils.telefono import Telefono


class UsuarioOut(BaseModel):
    """Usuario tal como lo ven los front (nunca incluye password_hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    codigo: str  # USR-001
    nombre: str
    email: str
    telefono: str | None
    rol: RolUsuario
    estado: EstadoUsuario
    organizacion_id: UUID | None
    ultimo_acceso: datetime | None
    creado_en: datetime


def normalizar_nombre(valor: str) -> str:
    valor = " ".join(valor.split())
    if len(valor) < 2:
        raise ValueError("Debe tener al menos 2 caracteres")
    return valor


class UsuarioNuevoIn(BaseModel):
    """Alta por invitación (voluntario que crea un admin, o admin que crea el super admin).

    No lleva contraseña: la pone la persona al activar su cuenta con el código.
    """

    nombre: str = Field(min_length=2, max_length=50)
    email: EmailStr = Field(max_length=100)
    telefono: Telefono | None = None
    # Solo la usa el super admin; el admin siempre crea en su propia organización
    organizacion_id: UUID | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        return normalizar_nombre(valor)

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str) -> str:
        return valor.lower()


class InvitacionOut(BaseModel):
    """El código se muestra UNA sola vez: en la BD solo queda su hash."""

    usuario: UsuarioOut
    codigo_activacion: str
    vence_en: datetime


class UsuarioCambiosIn(BaseModel):
    """Lo que el panel puede cambiar de otro usuario. Solo se aplican los campos enviados."""

    nombre: str | None = Field(default=None, min_length=2, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=100)
    telefono: Telefono | None = None
    estado: EstadoUsuario | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor: str | None) -> str | None:
        return normalizar_nombre(valor) if valor is not None else None

    @field_validator("email")
    @classmethod
    def _email(cls, valor: str | None) -> str | None:
        return valor.lower() if valor is not None else None

    @field_validator("estado")
    @classmethod
    def _estado(cls, valor: EstadoUsuario | None) -> EstadoUsuario | None:
        if valor == EstadoUsuario.EN_ESPERA:
            raise ValueError("El estado debe ser activo o bloqueado; 'en_espera' solo lo pone el alta por invitación")
        return valor


class PerfilCambiosIn(BaseModel):
    """Lo que el usuario cambia de su propio perfil. El correo y el rol no se cambian aquí."""

    nombre: str | None = Field(default=None, min_length=2, max_length=50)
    telefono: Telefono | None = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, valor: str | None) -> str | None:
        return normalizar_nombre(valor) if valor is not None else None


class CambioPasswordIn(BaseModel):
    """El usuario cambia su contraseña desde la app o el panel (sabe la actual)."""

    password_actual: str = Field(min_length=1)
    password_nueva: str = Field(min_length=8)

    @field_validator("password_nueva")
    @classmethod
    def _password(cls, valor: str) -> str:
        if len(valor.encode("utf-8")) > BCRYPT_MAX_BYTES:
            raise ValueError(f"La contraseña no puede superar {BCRYPT_MAX_BYTES} bytes")
        return valor


class UbicacionOut(BaseModel):
    """Última ubicación conocida del usuario (la usan las alertas por zona)."""

    model_config = ConfigDict(from_attributes=True)

    ubicacion_actual: LatLng | None
    ubicacion_actualizada_en: datetime | None

    @field_validator("ubicacion_actual", mode="before")
    @classmethod
    def _a_latlng(cls, valor):
        # El modelo guarda un punto PostGIS; la API lo expone como {"lat", "lng"}
        if isinstance(valor, WKBElement):
            return latlng_desde_punto(valor)
        return valor


class DispositivoIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # Token de Firebase Cloud Messaging que entrega la app al iniciar sesión
    token_push: str = Field(min_length=1, max_length=255)
    plataforma: PlataformaDispositivo


class DispositivoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    token_push: str
    plataforma: PlataformaDispositivo
    actualizado_en: datetime


class ConsentimientoIn(BaseModel):
    """Dar o retirar una autorización. La de tratamiento de datos se da en el registro."""

    tipo: TipoConsentimiento
    aceptado: bool


class ConsentimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tipo: TipoConsentimiento
    aceptado: bool
    version_politica: str
    creado_en: datetime
