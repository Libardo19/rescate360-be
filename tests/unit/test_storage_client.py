import pytest

from app.core.config import get_settings
from app.integrations import storage_client
from app.integrations.storage_client import ArchivoInvalido

JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 100
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100
MOV = b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 100


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize(
    ("contenido", "mime", "clase"),
    [
        (JPG, "image/jpeg", "foto"),
        (PNG, "image/png", "foto"),
        (WEBP, "image/webp", "foto"),
        (MP4, "video/mp4", "video"),
        (MOV, "video/quicktime", "video"),
    ],
)
def test_detecta_el_tipo_por_los_primeros_bytes(contenido, mime, clase):
    tipo = storage_client.validar(contenido)
    assert (tipo.mime, tipo.clase) == (mime, clase)


@pytest.mark.parametrize("contenido", [b"MZ\x90\x00 ejecutable", b"%PDF-1.7", b"", b"texto plano"])
def test_rechaza_lo_que_no_es_foto_ni_video(contenido):
    with pytest.raises(ArchivoInvalido) as error:
        storage_client.validar(contenido)
    assert error.value.codigo == "ARCHIVO_NO_PERMITIDO"


def test_limite_de_tamano_por_clase(monkeypatch):
    monkeypatch.setattr(get_settings(), "foto_max_mb", 1)
    with pytest.raises(ArchivoInvalido) as error:
        storage_client.validar(JPG + b"\x00" * (1024 * 1024))
    assert error.value.codigo == "ARCHIVO_DEMASIADO_GRANDE"


def test_guarda_con_nombre_propio_y_borra(carpeta):
    guardado = storage_client.guardar(PNG, "reportes")
    assert guardado.ruta.startswith("reportes/") and guardado.ruta.endswith(".png")
    assert (carpeta / guardado.ruta).read_bytes() == PNG
    assert storage_client.url_publica(guardado.ruta) == f"/uploads/{guardado.ruta}"

    storage_client.borrar(guardado.ruta)
    assert not (carpeta / guardado.ruta).exists()


def test_url_publica_respeta_urls_viejas():
    assert storage_client.url_publica("https://cdn.x/foto.jpg") == "https://cdn.x/foto.jpg"
