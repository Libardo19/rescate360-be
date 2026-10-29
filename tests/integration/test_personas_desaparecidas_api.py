"""Personas desaparecidas (A5): ficha, foto con autorización, reglas de menores, búsqueda y estado."""

from datetime import date, timedelta

import pytest

from app.core.config import get_settings
from app.models.consentimiento import Consentimiento
from app.models.enums import RolUsuario, TipoConsentimiento

C, V, A, S = RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 200
FICHA = {
    "nombre": "María Fernanda Ruiz",
    "edad": "34",
    "sexo": "femenino",
    "fecha_vista": "2026-10-20",
    "lugar": "Parque Novalito, Valledupar",
    "descripcion": "Cabello negro largo, contextura delgada",
    "contacto_nombre": "Carlos Ruiz",
    "contacto_telefono": "300 123 4567",
}


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


def _crear(cliente, headers, foto: bytes | None = None, **campos):
    files = {"foto": ("foto.jpg", foto, "application/octet-stream")} if foto is not None else None
    return cliente.post("/personas-desaparecidas", data={**FICHA, **campos}, files=files, headers=headers)


def _creada(cliente, headers, **kwargs) -> dict:
    r = _crear(cliente, headers, **kwargs)
    assert r.status_code == 201, r.text
    return r.json()


# --- crear ---


def test_crea_ficha_completa_con_foto_autorizada(cliente, db, crear_usuario, headers_de, uploads):
    autor = crear_usuario(C)
    persona = _creada(cliente, headers_de(autor), foto=JPG, acepta_publicar_foto="true", estatura="1.62 m")
    assert persona["estado"] == "buscando"
    assert persona["es_menor"] is False
    assert persona["contacto_telefono"] == "+573001234567"
    assert persona["estatura"] == "1.62 m"
    assert persona["foto_url"].startswith("/uploads/personas/") and persona["foto_oculta"] is False
    assert persona["es_mia"] and persona["puede_gestionar"]
    assert "Mecanismo de Búsqueda Urgente" in persona["aviso"]
    assert len(list(uploads.rglob("*.jpg"))) == 1
    consentimiento = db.query(Consentimiento).filter_by(usuario_id=autor.id).one()
    assert consentimiento.tipo == TipoConsentimiento.FOTO_PERSONA and consentimiento.aceptado


def test_foto_sin_autorizacion_se_rechaza_y_no_se_guarda(cliente, crear_usuario, headers_de, uploads):
    r = _crear(cliente, headers_de(crear_usuario(C)), foto=JPG)
    assert r.status_code == 422 and r.json()["codigo"] == "FOTO_SIN_AUTORIZACION"
    assert not list(uploads.rglob("*.*"))


@pytest.mark.parametrize(
    ("contenido", "codigo"),
    [(MP4, "ARCHIVO_NO_PERMITIDO"), (b"MZ" + b"\x00" * 100, "ARCHIVO_NO_PERMITIDO")],
)
def test_foto_debe_ser_imagen_real(cliente, crear_usuario, headers_de, contenido, codigo):
    r = _crear(cliente, headers_de(crear_usuario(C)), foto=contenido, acepta_publicar_foto="true")
    assert r.status_code == 422 and r.json()["codigo"] == codigo


@pytest.mark.parametrize(
    "campos",
    [
        {"edad": "130"},
        {"sexo": "x"},
        {"fecha_vista": (date.today() + timedelta(days=1)).isoformat()},
        {"contacto_telefono": "123"},
        {"lat": "10.4"},  # sin lng
        {"nombre": "A"},
    ],
)
def test_validaciones_de_la_ficha(cliente, crear_usuario, headers_de, campos):
    r = _crear(cliente, headers_de(crear_usuario(C)), **campos)
    assert r.status_code == 422, r.text


def test_guarda_coordenadas_opcionales(cliente, crear_usuario, headers_de):
    persona = _creada(cliente, headers_de(crear_usuario(C)), lat="10.4631", lng="-73.2532")
    assert persona["ubicacion"] == {"lat": pytest.approx(10.4631), "lng": pytest.approx(-73.2532)}


# --- menores y privacidad ---


def test_foto_de_menor_solo_la_ven_autor_y_administradores(cliente, crear_usuario, headers_de):
    autor = crear_usuario(C)
    persona = _creada(cliente, headers_de(autor), foto=JPG, acepta_publicar_foto="true", edad="12")
    assert persona["es_menor"] is True and persona["foto_url"]

    url = f"/personas-desaparecidas/{persona['id']}"
    otro = cliente.get(url, headers=headers_de(crear_usuario(C))).json()
    assert otro["foto_url"] is None and otro["foto_oculta"] is True
    voluntario = cliente.get(url, headers=headers_de(crear_usuario(V))).json()
    assert voluntario["foto_url"] is None
    for rol in (A, S):
        assert cliente.get(url, headers=headers_de(crear_usuario(rol))).json()["foto_url"]


def test_listado_no_expone_el_contacto_y_el_detalle_si(cliente, crear_usuario, headers_de):
    persona = _creada(cliente, headers_de(crear_usuario(C)))
    lector = headers_de(crear_usuario(C))
    item = cliente.get("/personas-desaparecidas", headers=lector).json()["items"][0]
    assert item["contacto_telefono"] is None and item["contacto_nombre"] is None and item["aviso"] is None
    detalle = cliente.get(f"/personas-desaparecidas/{persona['id']}", headers=lector).json()
    assert detalle["contacto_telefono"] == "+573001234567"
    assert detalle["es_mia"] is False and detalle["puede_gestionar"] is False


def test_sin_sesion_no_se_ve(cliente):
    assert cliente.get("/personas-desaparecidas").status_code == 401


# --- listado ---


def test_busca_por_nombre_sin_tildes_y_filtra(cliente, crear_usuario, headers_de):
    autor = headers_de(crear_usuario(C))
    maria = _creada(cliente, autor)
    _creada(cliente, autor, nombre="Pedro Pérez")
    _creada(cliente, headers_de(crear_usuario(C)), nombre="Ana Gómez")

    r = cliente.get("/personas-desaparecidas", params={"q": "maria"}, headers=autor).json()
    assert [p["id"] for p in r["items"]] == [maria["id"]] and r["total"] == 1

    mias = cliente.get("/personas-desaparecidas", params={"solo_mias": "true"}, headers=autor).json()
    assert mias["total"] == 2

    cliente.patch(f"/personas-desaparecidas/{maria['id']}/estado", json={"estado": "encontrado"}, headers=autor)
    buscando = cliente.get("/personas-desaparecidas", params={"estado": "buscando"}, headers=autor).json()
    assert maria["id"] not in [p["id"] for p in buscando["items"]]
    # Los casos abiertos van primero
    todas = cliente.get("/personas-desaparecidas", headers=autor).json()["items"]
    assert todas[-1]["id"] == maria["id"]


def test_detalle_inexistente(cliente, crear_usuario, headers_de):
    r = cliente.get(
        "/personas-desaparecidas/00000000-0000-0000-0000-000000000000", headers=headers_de(crear_usuario(C))
    )
    assert r.status_code == 404 and r.json()["codigo"] == "PERSONA_NO_ENCONTRADA"


# --- editar y estado ---


def test_autor_edita_y_la_edad_recalcula_es_menor(cliente, crear_usuario, headers_de):
    autor = headers_de(crear_usuario(C))
    persona = _creada(cliente, autor)
    r = cliente.patch(
        f"/personas-desaparecidas/{persona['id']}",
        json={"edad": 15, "vestimenta": "Jean azul", "ubicacion": {"lat": 10.5, "lng": -73.3}},
        headers=autor,
    )
    assert r.status_code == 200, r.text
    assert r.json()["es_menor"] is True and r.json()["vestimenta"] == "Jean azul"
    assert r.json()["ubicacion"] == {"lat": pytest.approx(10.5), "lng": pytest.approx(-73.3)}


def test_no_se_borra_un_campo_obligatorio(cliente, crear_usuario, headers_de):
    autor = headers_de(crear_usuario(C))
    persona = _creada(cliente, autor)
    r = cliente.patch(f"/personas-desaparecidas/{persona['id']}", json={"lugar": None}, headers=autor)
    assert r.status_code == 422 and r.json()["codigo"] == "CAMPO_OBLIGATORIO"


@pytest.mark.parametrize("rol", [C, V])
def test_otros_no_editan_ni_cambian_estado(cliente, crear_usuario, headers_de, rol):
    persona = _creada(cliente, headers_de(crear_usuario(C)))
    intruso = headers_de(crear_usuario(rol))
    r = cliente.patch(f"/personas-desaparecidas/{persona['id']}", json={"lugar": "Otro lugar"}, headers=intruso)
    assert r.status_code == 403 and r.json()["codigo"] == "PERSONA_FUERA_DE_ALCANCE"
    r = cliente.patch(f"/personas-desaparecidas/{persona['id']}/estado", json={"estado": "encontrado"}, headers=intruso)
    assert r.status_code == 403


@pytest.mark.parametrize("rol", [A, S])
def test_administrador_marca_encontrada_y_vuelve_a_buscando(cliente, crear_usuario, headers_de, rol):
    persona = _creada(cliente, headers_de(crear_usuario(C)))
    admin = headers_de(crear_usuario(rol))
    url = f"/personas-desaparecidas/{persona['id']}/estado"
    encontrada = cliente.patch(url, json={"estado": "encontrado"}, headers=admin).json()
    assert encontrada["estado"] == "encontrado" and encontrada["encontrado_en"]
    de_nuevo = cliente.patch(url, json={"estado": "buscando"}, headers=admin).json()
    assert de_nuevo["estado"] == "buscando" and de_nuevo["encontrado_en"] is None
