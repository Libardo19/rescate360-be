"""Reportes de incidentes (A4): crear con evidencias, tipos, alcance por rol y verificación."""

from uuid import UUID

import pytest

from app.core.config import get_settings
from app.models.enums import EstadoReporte, RolUsuario
from app.models.reporte import Reporte

C, V, A, S = RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 200
CAMPOS = {"tipo": "incendio", "descripcion": "Sale humo de una bodega", "lat": "10.4631", "lng": "-73.2532"}


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch):
    """Los archivos de las pruebas van a una carpeta temporal, no a uploads/ del repo."""
    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    return tmp_path


def _crear(cliente, headers, archivos=(), **campos):
    files = [("archivos", (nombre, contenido, "application/octet-stream")) for nombre, contenido in archivos]
    return cliente.post("/reportes", data={**CAMPOS, **campos}, files=files or None, headers=headers)


def _creado(cliente, headers, **campos) -> dict:
    r = _crear(cliente, headers, **campos)
    assert r.status_code == 201, r.text
    return r.json()


def _enrutar(db, reporte_id: str, organizacion_id) -> None:
    reporte = db.get(Reporte, UUID(reporte_id))
    reporte.organizacion_manual_id = organizacion_id
    db.flush()


def _estado(db, reporte_id: str, estado: EstadoReporte) -> None:
    reporte = db.get(Reporte, UUID(reporte_id))
    reporte.estado = estado
    db.flush()


# --- crear ---


def test_crea_reporte_con_foto_y_video(cliente, crear_usuario, headers_de, uploads):
    autor = crear_usuario(C)
    r = _crear(cliente, headers_de(autor), archivos=[("foto.jpg", JPG), ("video.mp4", MP4)], direccion="Calle 16 # 9-20")
    assert r.status_code == 201, r.text
    reporte = r.json()
    assert reporte["estado"] == "pendiente"
    assert reporte["tipo"] == "incendio" and reporte["tipo_etiqueta"] == "Incendio"
    assert reporte["ubicacion"] == {"lat": pytest.approx(10.4631), "lng": pytest.approx(-73.2532)}
    assert reporte["direccion"] == "Calle 16 # 9-20"
    assert reporte["reportante"]["nombre"] == autor.nombre
    assert [(e["tipo"], e["mime"]) for e in reporte["evidencias"]] == [("foto", "image/jpeg"), ("video", "video/mp4")]
    for evidencia in reporte["evidencias"]:
        assert evidencia["url"].startswith("/uploads/reportes/")
        assert (uploads / evidencia["url"].removeprefix("/uploads/")).exists()


def test_crea_reporte_sin_archivos(cliente, crear_usuario, headers_de):
    assert _creado(cliente, headers_de(crear_usuario(C)))["evidencias"] == []


@pytest.mark.parametrize(
    ("escrito", "guardado"),
    [("Incendio", "incendio"), ("  INUNDACIÓN ", "inundacion"), ("fuga   de gas", "fuga de gas"), ("Árbol caído", "árbol caído")],
)
def test_tipo_de_la_lista_o_propio(cliente, crear_usuario, headers_de, escrito, guardado):
    reporte = _creado(cliente, headers_de(crear_usuario(C)), tipo=escrito)
    assert reporte["tipo"] == guardado


@pytest.mark.parametrize("tipo", ["", "ab", "x" * 31, "gas <script>", "fuga!!"])
def test_tipo_invalido(cliente, crear_usuario, headers_de, tipo):
    r = _crear(cliente, headers_de(crear_usuario(C)), tipo=tipo)
    assert r.status_code == 422


def test_archivo_falso_renombrado_no_se_acepta_y_no_se_guarda_nada(cliente, db, crear_usuario, headers_de, uploads):
    r = _crear(cliente, headers_de(crear_usuario(C)), archivos=[("foto.jpg", JPG), ("virus.jpg", b"MZ\x90\x00 nada")])
    assert r.status_code == 422 and r.json()["codigo"] == "ARCHIVO_NO_PERMITIDO"
    assert not any(uploads.rglob("*.*"))
    assert db.query(Reporte).count() == 0


def test_limites_de_tamano_y_cantidad(cliente, crear_usuario, headers_de, monkeypatch):
    headers = headers_de(crear_usuario(C))
    r = _crear(cliente, headers, archivos=[(f"f{i}.jpg", JPG) for i in range(6)])
    assert r.status_code == 422 and r.json()["codigo"] == "DEMASIADOS_ARCHIVOS"

    monkeypatch.setattr(get_settings(), "foto_max_mb", 1)
    r = _crear(cliente, headers, archivos=[("grande.jpg", JPG + b"\x00" * (1024 * 1024))])
    assert r.status_code == 422 and r.json()["codigo"] == "ARCHIVO_DEMASIADO_GRANDE"


def test_tipos_sugeridos(cliente):
    r = cliente.get("/reportes/tipos")
    assert r.status_code == 200
    assert {"valor": "inundacion", "etiqueta": "Inundación"} in r.json()
    assert "sismo" in [t["valor"] for t in r.json()]


# --- listar y detalle ---


def test_alcance_por_rol(cliente, db, crear_usuario, headers_de):
    autor, vecino = crear_usuario(C), crear_usuario(C)
    admin = crear_usuario(A)
    voluntario = crear_usuario(V, organizacion=admin.organizacion)
    enrutado = _creado(cliente, headers_de(autor))
    sin_enrutar = _creado(cliente, headers_de(autor))
    _enrutar(db, enrutado["id"], admin.organizacion_id)

    def ids(usuario):
        r = cliente.get("/reportes", headers=headers_de(usuario))
        assert r.status_code == 200, r.text
        return {x["id"] for x in r.json()["items"]}

    assert ids(autor) == {enrutado["id"], sin_enrutar["id"]}
    assert ids(vecino) == set()
    assert ids(admin) == ids(voluntario) == {enrutado["id"]}
    assert {enrutado["id"], sin_enrutar["id"]} <= ids(crear_usuario(S))


def test_filtros_por_estado_y_tipo(cliente, db, crear_usuario, headers_de):
    autor = crear_usuario(C)
    headers = headers_de(autor)
    incendio = _creado(cliente, headers)
    gas = _creado(cliente, headers, tipo="fuga de gas")
    _estado(db, incendio["id"], EstadoReporte.VERIFICADO)

    def ids(**params):
        return {x["id"] for x in cliente.get("/reportes", params=params, headers=headers).json()["items"]}

    assert ids(estado="verificado") == {incendio["id"]}
    assert ids(tipo="Incendio") == {incendio["id"]}
    assert ids(tipo="otros") == {gas["id"]}


def test_detalle_verificado_es_publico_pero_sin_reportante(cliente, db, crear_usuario, headers_de):
    reporte = _creado(cliente, headers_de(crear_usuario(C)))
    curioso = crear_usuario(C)

    r = cliente.get(f"/reportes/{reporte['id']}", headers=headers_de(curioso))
    assert r.status_code == 403 and r.json()["codigo"] == "REPORTE_FUERA_DE_ALCANCE"

    _estado(db, reporte["id"], EstadoReporte.VERIFICADO)
    r = cliente.get(f"/reportes/{reporte['id']}", headers=headers_de(curioso))
    assert r.status_code == 200 and r.json()["reportante"] is None


def test_reporte_inexistente(cliente, crear_usuario, headers_de):
    r = cliente.get("/reportes/00000000-0000-0000-0000-000000000000", headers=headers_de(crear_usuario(S)))
    assert r.status_code == 404 and r.json()["codigo"] == "REPORTE_NO_ENCONTRADO"


def test_reportar_exige_sesion(cliente):
    assert cliente.post("/reportes", data=CAMPOS).status_code == 401


# --- verificación ---


def _caso(cliente, db, crear_usuario, headers_de):
    """Un admin y un reporte pendiente ya enrutado a su organización."""
    admin = crear_usuario(A)
    reporte = _creado(cliente, headers_de(crear_usuario(C)))
    _enrutar(db, reporte["id"], admin.organizacion_id)
    return admin, reporte


def test_admin_verifica_y_el_reporte_queda_publico(cliente, db, crear_usuario, headers_de):
    admin, reporte = _caso(cliente, db, crear_usuario, headers_de)
    r = cliente.patch(f"/reportes/{reporte['id']}/verificar", headers=headers_de(admin))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "verificado"
    assert cuerpo["verificado_por"] == str(admin.id) and cuerpo["verificado_en"]
    # Ya sale en el mapa de cualquier ciudadano
    mapa = cliente.get("/mapa", params={"capas": "reportes"}, headers=headers_de(crear_usuario(C))).json()
    assert reporte["id"] in [p["id"] for p in mapa["puntos"]]


def test_rechazar_con_motivo_cancela_asignaciones(cliente, db, crear_usuario, headers_de):
    admin, reporte = _caso(cliente, db, crear_usuario, headers_de)
    voluntario = crear_usuario(V, organizacion=admin.organizacion)
    asignacion = cliente.post(f"/reportes/{reporte['id']}/asignar", headers=headers_de(voluntario))
    assert asignacion.status_code == 201, asignacion.text

    r = cliente.patch(
        f"/reportes/{reporte['id']}/rechazar", json={"motivo": "La foto es de otro año"}, headers=headers_de(admin)
    )
    assert r.status_code == 200 and r.json()["estado"] == "rechazado"
    assert r.json()["motivo_rechazo"] == "La foto es de otro año"
    mias = cliente.get("/asignaciones/mias", params={"estado": "activa"}, headers=headers_de(voluntario)).json()
    assert mias["total"] == 0


def test_rechazar_sin_cuerpo(cliente, db, crear_usuario, headers_de):
    admin, reporte = _caso(cliente, db, crear_usuario, headers_de)
    r = cliente.patch(f"/reportes/{reporte['id']}/rechazar", headers=headers_de(admin))
    assert r.status_code == 200 and r.json()["motivo_rechazo"] is None


def test_marcar_duplicado_apunta_al_original(cliente, db, crear_usuario, headers_de):
    admin, original = _caso(cliente, db, crear_usuario, headers_de)
    _, copia = _caso(cliente, db, crear_usuario, headers_de)
    _enrutar(db, copia["id"], admin.organizacion_id)
    _, tercera = _caso(cliente, db, crear_usuario, headers_de)
    _enrutar(db, tercera["id"], admin.organizacion_id)

    r = cliente.patch(
        f"/reportes/{copia['id']}/marcar-duplicado", json={"duplicado_de_id": original["id"]}, headers=headers_de(admin)
    )
    assert r.status_code == 200 and r.json()["estado"] == "duplicado"
    # Duplicado de un duplicado: apunta al primero de la cadena
    r = cliente.patch(
        f"/reportes/{tercera['id']}/marcar-duplicado", json={"duplicado_de_id": copia["id"]}, headers=headers_de(admin)
    )
    assert r.json()["duplicado_de_id"] == original["id"]


def test_duplicado_invalido(cliente, db, crear_usuario, headers_de):
    admin, reporte = _caso(cliente, db, crear_usuario, headers_de)
    url = f"/reportes/{reporte['id']}/marcar-duplicado"
    r = cliente.patch(url, json={"duplicado_de_id": reporte["id"]}, headers=headers_de(admin))
    assert r.status_code == 422 and r.json()["codigo"] == "DUPLICADO_DE_SI_MISMO"
    r = cliente.patch(url, json={"duplicado_de_id": "00000000-0000-0000-0000-000000000000"}, headers=headers_de(admin))
    assert r.status_code == 404 and r.json()["codigo"] == "REPORTE_ORIGINAL_NO_ENCONTRADO"


def test_solo_se_revisa_un_pendiente(cliente, db, crear_usuario, headers_de):
    admin, reporte = _caso(cliente, db, crear_usuario, headers_de)
    cliente.patch(f"/reportes/{reporte['id']}/verificar", headers=headers_de(admin))
    r = cliente.patch(f"/reportes/{reporte['id']}/rechazar", headers=headers_de(admin))
    assert r.status_code == 409 and r.json()["codigo"] == "TRANSICION_NO_PERMITIDA"


def test_quien_puede_verificar(cliente, db, crear_usuario, headers_de):
    admin, reporte = _caso(cliente, db, crear_usuario, headers_de)
    url = f"/reportes/{reporte['id']}/verificar"
    voluntario = crear_usuario(V, organizacion=admin.organizacion)
    assert cliente.patch(url, headers=headers_de(voluntario)).status_code == 403
    assert cliente.patch(url, headers=headers_de(crear_usuario(C))).status_code == 403
    assert cliente.patch(url, headers=headers_de(crear_usuario(A))).status_code == 403  # otra organización
    assert cliente.patch(url, headers=headers_de(crear_usuario(S))).status_code == 200


# --- enrutar a una organización ---


def test_super_admin_enruta_y_el_admin_ya_lo_ve(cliente, crear_usuario, headers_de):
    admin = crear_usuario(A)
    reporte = _creado(cliente, headers_de(crear_usuario(C)))
    r = cliente.patch(
        f"/reportes/{reporte['id']}/organizacion",
        json={"organizacion_id": str(admin.organizacion_id)},
        headers=headers_de(crear_usuario(S)),
    )
    assert r.status_code == 200 and r.json()["organizacion_manual_id"] == str(admin.organizacion_id)
    items = cliente.get("/reportes", headers=headers_de(admin)).json()["items"]
    assert [x["id"] for x in items] == [reporte["id"]]
    assert items[0]["reportante"] is not None


def test_enrutar_reporte_reglas(cliente, db, crear_usuario, crear_organizacion, headers_de):
    super_admin = crear_usuario(S)
    admin, reporte = _caso(cliente, db, crear_usuario, headers_de)
    url = f"/reportes/{reporte['id']}/organizacion"

    assert cliente.patch(url, json={"organizacion_id": str(admin.organizacion_id)}, headers=headers_de(admin)).status_code == 403

    voluntario = crear_usuario(V, organizacion=admin.organizacion)
    cliente.post(f"/reportes/{reporte['id']}/asignar", headers=headers_de(voluntario))
    r = cliente.patch(url, json={"organizacion_id": str(crear_organizacion().id)}, headers=headers_de(super_admin))
    assert r.status_code == 409 and r.json()["codigo"] == "REPORTE_CON_ASIGNACIONES"

    _estado(db, reporte["id"], EstadoReporte.RECHAZADO)
    r = cliente.patch(url, json={"organizacion_id": str(crear_organizacion().id)}, headers=headers_de(super_admin))
    assert r.status_code == 409 and r.json()["codigo"] == "REPORTE_CERRADO"


def test_admin_fija_la_prioridad_manual(cliente, db, crear_usuario, headers_de):
    admin, reporte = _caso(cliente, db, crear_usuario, headers_de)
    r = cliente.patch(f"/reportes/{reporte['id']}/prioridad", json={"prioridad_manual": "critica"}, headers=headers_de(admin))
    assert r.status_code == 200 and r.json()["prioridad_manual"] == "critica"
    otro = crear_usuario(A)
    r = cliente.patch(f"/reportes/{reporte['id']}/prioridad", json={"prioridad_manual": "baja"}, headers=headers_de(otro))
    assert r.status_code == 403
    r = cliente.patch(f"/reportes/{reporte['id']}/prioridad", json={"prioridad_manual": "pendiente"}, headers=headers_de(admin))
    assert r.status_code == 422
