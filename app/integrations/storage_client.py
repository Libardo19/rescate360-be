"""Almacenamiento de fotos y videos (evidencias de reportes; más adelante, fotos de personas).

Con STORAGE_BACKEND=local los archivos van a UPLOADS_DIR y la API los sirve en /uploads.
Con STORAGE_BACKEND=azure van a un contenedor de Blob Storage y se devuelve su URL pública.

El tipo se decide por los primeros bytes del archivo, NO por la extensión ni por el
Content-Type que manda el cliente: un .exe renombrado a .jpg se rechaza.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings

URL_BASE = "/uploads"


def _es_azure() -> bool:
    return get_settings().storage_backend.lower() == "azure"


def _contenedor():
    settings = get_settings()
    if not settings.storage_bucket:
        raise RuntimeError("STORAGE_BUCKET es obligatorio cuando STORAGE_BACKEND=azure")
    if not settings.azure_storage_connection_string:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING es obligatorio cuando STORAGE_BACKEND=azure")
    from azure.storage.blob import BlobServiceClient

    servicio = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
    return servicio.get_container_client(settings.storage_bucket)


@dataclass(frozen=True)
class TipoArchivo:
    mime: str
    extension: str
    clase: str  # foto | video


@dataclass(frozen=True)
class ArchivoGuardado:
    ruta: str  # relativa a UPLOADS_DIR, p. ej. "reportes/3f2c….jpg"
    mime: str
    clase: str
    tamano_bytes: int


class ArchivoInvalido(Exception):
    def __init__(self, detalle: str, codigo: str):
        super().__init__(detalle)
        self.detalle = detalle
        self.codigo = codigo


def detectar_tipo(cabecera: bytes) -> TipoArchivo | None:
    if cabecera.startswith(b"\xff\xd8\xff"):
        return TipoArchivo("image/jpeg", "jpg", "foto")
    if cabecera.startswith(b"\x89PNG\r\n\x1a\n"):
        return TipoArchivo("image/png", "png", "foto")
    if cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP":
        return TipoArchivo("image/webp", "webp", "foto")
    # MP4 y MOV (iPhone) empiezan con una caja "ftyp" en el byte 4
    if cabecera[4:8] == b"ftyp":
        if cabecera[8:10] == b"qt":
            return TipoArchivo("video/quicktime", "mov", "video")
        return TipoArchivo("video/mp4", "mp4", "video")
    return None


def _limite(clase: str) -> int:
    settings = get_settings()
    megas = settings.foto_max_mb if clase == "foto" else settings.video_max_mb
    return megas * 1024 * 1024


def validar(contenido: bytes) -> TipoArchivo:
    tipo = detectar_tipo(contenido[:16])
    if tipo is None:
        raise ArchivoInvalido("Solo se aceptan fotos JPG, PNG o WEBP y videos MP4 o MOV", "ARCHIVO_NO_PERMITIDO")
    if len(contenido) > _limite(tipo.clase):
        megas = _limite(tipo.clase) // (1024 * 1024)
        raise ArchivoInvalido(f"El archivo supera el máximo de {megas} MB para {tipo.clase}s", "ARCHIVO_DEMASIADO_GRANDE")
    return tipo


def guardar(contenido: bytes, carpeta: str) -> ArchivoGuardado:
    """Valida y guarda. El nombre es un uuid: nunca se usa el nombre que manda el cliente."""
    tipo = validar(contenido)
    ruta = f"{carpeta}/{uuid.uuid4().hex}.{tipo.extension}"
    if _es_azure():
        _contenedor().upload_blob(name=ruta, data=contenido, overwrite=True)
    else:
        destino = Path(get_settings().uploads_dir) / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)
    return ArchivoGuardado(ruta=ruta, mime=tipo.mime, clase=tipo.clase, tamano_bytes=len(contenido))


def borrar(ruta: str) -> None:
    if _es_azure():
        _contenedor().delete_blob(ruta)
        return
    (Path(get_settings().uploads_dir) / ruta).unlink(missing_ok=True)


def url_publica(ruta: str) -> str:
    # Rutas que ya son URL (datos viejos de foto_url) se devuelven tal cual
    if ruta.startswith(("http://", "https://", "/")):
        return ruta
    settings = get_settings()
    if _es_azure():
        base = settings.storage_public_url.rstrip("/")
        if not base:
            if not settings.azure_storage_account_name:
                raise RuntimeError("AZURE_STORAGE_ACCOUNT_NAME o STORAGE_PUBLIC_URL es obligatorio cuando STORAGE_BACKEND=azure")
            base = f"https://{settings.azure_storage_account_name}.blob.core.windows.net/{settings.storage_bucket}".rstrip("/")
        return f"{base}/{ruta.lstrip('/')}"
    return f"{URL_BASE}/{ruta}"
