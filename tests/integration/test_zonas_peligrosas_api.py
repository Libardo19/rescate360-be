"""Pruebas de la API de zonas peligrosas (TestClient + BD de pruebas)."""

from uuid import uuid4

import pytest

from app.models.enums import RolUsuario

URL = "/zonas-peligrosas"
ZONA = {"lat": 10.4631, "lng": -73.2532, "radio_m": 800}
LEJOS = {"lat": 10.4901, "lng": -73.2532, "radio_m": 500}  # ~3 km al norte del punto de ZONA
CUERPO = {
    "nombre": "Ribera del río",
    "tipo_riesgo": "Desbordamiento del río Guatapurí",
    "nivel": "alto",
    "descripcion": "Crecida frecuente en invierno",
    "zona": ZONA,
}
DENTRO = {"lat": 10.4631, "lng": -73.2532}
FUERA = {"lat": 11.5, "lng": -73.2532}


def _crear(cliente, headers, **cambios) -> dict:
    r = cliente.post(URL, json={**CUERPO, **cambios}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _modificar(cliente, headers, zona_id: str, **cuerpo):
    return cliente.patch(f"{URL}/{zona_id}", json=cuerpo, headers=headers)


def _ids(respuesta) -> list[str]:
    return [z["id"] for z in respuesta.json()["items"]]


# --- crear -----------------------------------------------------------------------------------


def test_administrador_crea_zona_de_su_organizacion(cliente, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)

    zona = _crear(cliente, headers_de(admin))

    assert zona["organizacion_id"] == str(admin.organizacion_id)
    assert zona["gestionado_por"] == str(admin.id)
    assert zona["nombre"] == "Ribera del río"
    assert zona["tipo_riesgo"] == "Desbordamiento del río Guatapurí"  # texto libre, más de 30 caracteres
    assert zona["nivel"] == "alto"
    assert zona["estado"] == "activa"
    assert zona["descripcion"] == "Crecida frecuente en invierno"
    assert zona["zona"]["lat"] == pytest.approx(10.4631)
    assert zona["zona"]["lng"] == pytest.approx(-73.2532)
    assert zona["zona"]["radio_m"] == 800
    assert zona["propia"] is True
    assert zona["distancia_m"] is None


def test_se_puede_crear_en_monitoreo_y_sin_descripcion(cliente, crear_usuario, headers_de):
    cuerpo = {k: v for k, v in CUERPO.items() if k != "descripcion"}
    r = cliente.post(
        URL, json={**cuerpo, "estado": "en_monitoreo"}, headers=headers_de(crear_usuario(RolUsuario.ADMINISTRADOR))
    )
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "en_monitoreo"
    assert r.json()["descripcion"] is None


def test_administrador_no_puede_elegir_otra_organizacion(cliente, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    otra = crear_usuario(RolUsuario.ADMINISTRADOR)

    r = cliente.post(URL, json={**CUERPO, "organizacion_id": str(otra.organizacion_id)}, headers=headers_de(admin))

    assert r.status_code == 403
    assert r.json()["codigo"] == "ZONA_ORGANIZACION_NO_PERMITIDA"


def test_super_admin_crea_zona_global_o_de_una_organizacion(cliente, crear_usuario, headers_de):
    super_admin = crear_usuario(RolUsuario.SUPER_ADMIN)
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)

    global_ = _crear(cliente, headers_de(super_admin))
    de_org = _crear(cliente, headers_de(super_admin), organizacion_id=str(admin.organizacion_id))

    assert global_["organizacion_id"] is None
    assert de_org["organizacion_id"] == str(admin.organizacion_id)


def test_super_admin_con_organizacion_inexistente_responde_422(cliente, crear_usuario, headers_de):
    r = cliente.post(
        URL,
        json={**CUERPO, "organizacion_id": str(uuid4())},
        headers=headers_de(crear_usuario(RolUsuario.SUPER_ADMIN)),
    )
    assert r.status_code == 422
    assert r.json()["codigo"] == "ORGANIZACION_NO_ENCONTRADA"


@pytest.mark.parametrize("rol", [RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO])
def test_ciudadano_y_voluntario_no_pueden_crear(cliente, crear_usuario, headers_de, rol):
    assert cliente.post(URL, json=CUERPO, headers=headers_de(crear_usuario(rol))).status_code == 403


def test_sin_token_responde_401(cliente):
    assert cliente.post(URL, json=CUERPO).status_code == 401
    assert cliente.get(URL).status_code == 401


@pytest.mark.parametrize(
    "cambio",
    [
        {"zona": {**ZONA, "radio_m": 0}},
        {"zona": {**ZONA, "radio_m": 500_000}},
        {"zona": {**ZONA, "lat": 200}},
        {"nivel": "extremo"},
        {"estado": "resuelta"},
        {"nombre": " "},
        {"tipo_riesgo": "x" * 61},
    ],
)
def test_datos_invalidos_responden_422(cliente, crear_usuario, headers_de, cambio):
    r = cliente.post(URL, json={**CUERPO, **cambio}, headers=headers_de(crear_usuario(RolUsuario.ADMINISTRADOR)))
    assert r.status_code == 422
    assert r.json()["codigo"] == "DATOS_INVALIDOS"


# --- listar: quién ve qué --------------------------------------------------------------------


def test_ciudadano_y_voluntario_ven_zonas_vigentes_de_cualquier_organizacion(cliente, crear_usuario, headers_de):
    activa = _crear(cliente, headers_de(crear_usuario(RolUsuario.ADMINISTRADOR)))
    monitoreo = _crear(cliente, headers_de(crear_usuario(RolUsuario.ADMINISTRADOR)), estado="en_monitoreo")

    for rol in (RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO):
        ids = _ids(cliente.get(URL, headers=headers_de(crear_usuario(rol))))
        assert activa["id"] in ids
        assert monitoreo["id"] in ids


def test_las_inactivas_no_se_listan_por_defecto(cliente, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    zona = _crear(cliente, headers_de(admin))
    _modificar(cliente, headers_de(admin), zona["id"], estado="inactiva")

    assert zona["id"] not in _ids(cliente.get(URL, headers=headers_de(admin)))
    assert zona["id"] not in _ids(cliente.get(URL, headers=headers_de(crear_usuario())))


def test_administrador_puede_pedir_las_inactivas_pero_el_ciudadano_no(cliente, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    zona = _crear(cliente, headers_de(admin))
    _modificar(cliente, headers_de(admin), zona["id"], estado="inactiva")

    del_admin = cliente.get(URL, params={"estado": "inactiva"}, headers=headers_de(admin))
    del_ciudadano = cliente.get(URL, params={"estado": "inactiva"}, headers=headers_de(crear_usuario()))

    assert zona["id"] in _ids(del_admin)
    assert _ids(del_ciudadano) == []


def test_administrador_ve_las_suyas_y_las_globales_por_defecto(cliente, crear_usuario, headers_de):
    admin_a = crear_usuario(RolUsuario.ADMINISTRADOR)
    admin_b = crear_usuario(RolUsuario.ADMINISTRADOR)
    propia = _crear(cliente, headers_de(admin_a))
    ajena = _crear(cliente, headers_de(admin_b))
    global_ = _crear(cliente, headers_de(crear_usuario(RolUsuario.SUPER_ADMIN)))

    ids = _ids(cliente.get(URL, headers=headers_de(admin_a)))

    assert propia["id"] in ids
    assert global_["id"] in ids
    assert ajena["id"] not in ids


def test_administrador_con_alcance_todas_ve_las_ajenas_en_solo_lectura(cliente, crear_usuario, headers_de):
    admin_a = crear_usuario(RolUsuario.ADMINISTRADOR)
    propia = _crear(cliente, headers_de(admin_a))
    ajena = _crear(cliente, headers_de(crear_usuario(RolUsuario.ADMINISTRADOR)))

    r = cliente.get(URL, params={"alcance": "todas"}, headers=headers_de(admin_a))

    por_id = {z["id"]: z for z in r.json()["items"]}
    assert por_id[propia["id"]]["propia"] is True
    assert por_id[ajena["id"]]["propia"] is False


def test_super_admin_ve_todas(cliente, crear_usuario, headers_de):
    a = _crear(cliente, headers_de(crear_usuario(RolUsuario.ADMINISTRADOR)))
    b = _crear(cliente, headers_de(crear_usuario(RolUsuario.ADMINISTRADOR)))

    ids = _ids(cliente.get(URL, headers=headers_de(crear_usuario(RolUsuario.SUPER_ADMIN))))

    assert a["id"] in ids and b["id"] in ids


def test_ciudadano_y_voluntario_no_son_dueños_de_ninguna_zona(cliente, crear_usuario, headers_de):
    zona = _crear(cliente, headers_de(crear_usuario(RolUsuario.ADMINISTRADOR)))

    r = cliente.get(URL, headers=headers_de(crear_usuario()))

    assert {z["id"]: z for z in r.json()["items"]}[zona["id"]]["propia"] is False


# --- listar: cercanía y paginación -----------------------------------------------------------


def test_con_lat_y_lng_solo_salen_las_zonas_cercanas(cliente, crear_usuario, headers_de):
    zona = _crear(cliente, headers_de(crear_usuario(RolUsuario.ADMINISTRADOR)))
    ciudadano = headers_de(crear_usuario())

    cerca = cliente.get(URL, params=DENTRO, headers=ciudadano)
    lejos = cliente.get(URL, params=FUERA, headers=ciudadano)

    assert zona["id"] in _ids(cerca)
    assert zona["id"] not in _ids(lejos)


def test_las_zonas_salen_ordenadas_por_distancia_con_distancia_m(cliente, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    lejana = _crear(cliente, headers_de(admin), nombre="Lejana", zona=LEJOS)  # creada primero a propósito
    cercana = _crear(cliente, headers_de(admin), nombre="Cercana")

    r = cliente.get(URL, params={**DENTRO, "radio_m": 5000}, headers=headers_de(admin))

    items = r.json()["items"]
    assert [z["id"] for z in items] == [cercana["id"], lejana["id"]]
    assert items[0]["distancia_m"] == 0  # estoy dentro del círculo
    assert 2000 < items[1]["distancia_m"] < 3000  # ~3 km al centro menos 500 m de radio


def test_el_radio_de_busqueda_se_respeta(cliente, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    lejana = _crear(cliente, headers_de(admin), zona=LEJOS)

    r = cliente.get(URL, params={**DENTRO, "radio_m": 1000}, headers=headers_de(admin))

    assert lejana["id"] not in _ids(r)


def test_lat_sin_lng_responde_422(cliente, crear_usuario, headers_de):
    r = cliente.get(URL, params={"lat": 10.46}, headers=headers_de(crear_usuario()))
    assert r.status_code == 422
    assert r.json()["codigo"] == "UBICACION_INCOMPLETA"


def test_paginacion(cliente, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    for _ in range(3):
        _crear(cliente, headers_de(admin))

    r = cliente.get(URL, params={"pagina": 1, "por_pagina": 2}, headers=headers_de(admin))

    cuerpo = r.json()
    assert len(cuerpo["items"]) == 2
    assert cuerpo["total"] == 3
    assert cuerpo["por_pagina"] == 2


# --- modificar -------------------------------------------------------------------------------


def test_administrador_modifica_su_zona(cliente, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    zona = _crear(cliente, headers_de(admin))

    r = _modificar(cliente, headers_de(admin), zona["id"], nivel="bajo", estado="en_monitoreo", nombre="Nuevo nombre")

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["nivel"] == "bajo"
    assert cuerpo["estado"] == "en_monitoreo"
    assert cuerpo["nombre"] == "Nuevo nombre"
    assert cuerpo["tipo_riesgo"] == zona["tipo_riesgo"]  # lo que no se envía no cambia
    assert cuerpo["zona"] == zona["zona"]


def test_modificar_el_circulo_actualiza_tambien_la_busqueda_por_cercania(cliente, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    zona = _crear(cliente, headers_de(admin))
    nueva = {"lat": 11.5, "lng": -73.2532, "radio_m": 300}

    r = _modificar(cliente, headers_de(admin), zona["id"], zona=nueva)

    assert r.status_code == 200, r.text
    assert r.json()["zona"]["lat"] == pytest.approx(11.5)
    assert r.json()["zona"]["radio_m"] == 300
    assert zona["id"] not in _ids(cliente.get(URL, params=DENTRO, headers=headers_de(admin)))
    assert zona["id"] in _ids(cliente.get(URL, params=FUERA, headers=headers_de(admin)))


def test_se_puede_borrar_la_descripcion_y_reactivar(cliente, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    zona = _crear(cliente, headers_de(admin))
    _modificar(cliente, headers_de(admin), zona["id"], estado="inactiva")

    r = _modificar(cliente, headers_de(admin), zona["id"], estado="activa", descripcion=None)

    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "activa"
    assert r.json()["descripcion"] is None
    assert zona["id"] in _ids(cliente.get(URL, headers=headers_de(admin)))


def test_administrador_de_otra_organizacion_no_puede_modificar(cliente, crear_usuario, headers_de):
    zona = _crear(cliente, headers_de(crear_usuario(RolUsuario.ADMINISTRADOR)))

    r = _modificar(cliente, headers_de(crear_usuario(RolUsuario.ADMINISTRADOR)), zona["id"], nivel="bajo")

    assert r.status_code == 403
    assert r.json()["codigo"] == "FUERA_DE_ALCANCE"


def test_solo_el_super_admin_modifica_zonas_globales(cliente, crear_usuario, headers_de):
    super_admin = crear_usuario(RolUsuario.SUPER_ADMIN)
    zona = _crear(cliente, headers_de(super_admin))

    r_admin = _modificar(cliente, headers_de(crear_usuario(RolUsuario.ADMINISTRADOR)), zona["id"], nivel="bajo")
    r_super = _modificar(cliente, headers_de(super_admin), zona["id"], nivel="bajo")

    assert r_admin.status_code == 403
    assert r_admin.json()["codigo"] == "ZONA_GLOBAL"
    assert r_super.status_code == 200


@pytest.mark.parametrize("rol", [RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO])
def test_ciudadano_y_voluntario_no_pueden_modificar(cliente, crear_usuario, headers_de, rol):
    zona = _crear(cliente, headers_de(crear_usuario(RolUsuario.ADMINISTRADOR)))

    assert _modificar(cliente, headers_de(crear_usuario(rol)), zona["id"], nivel="bajo").status_code == 403


@pytest.mark.parametrize("cuerpo", [{}, {"nombre": None}, {"zona": None}, {"nivel": "extremo"}, {"estado": "resuelta"}])
def test_modificar_con_datos_invalidos_responde_422(cliente, crear_usuario, headers_de, cuerpo):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    zona = _crear(cliente, headers_de(admin))

    r = _modificar(cliente, headers_de(admin), zona["id"], **cuerpo)

    assert r.status_code == 422
    assert r.json()["codigo"] == "DATOS_INVALIDOS"


def test_zona_inexistente_responde_404(cliente, crear_usuario, headers_de):
    r = _modificar(cliente, headers_de(crear_usuario(RolUsuario.ADMINISTRADOR)), str(uuid4()), nivel="bajo")
    assert r.status_code == 404
    assert r.json()["codigo"] == "ZONA_NO_ENCONTRADA"


# --- la capa "zonas" del mapa ----------------------------------------------------------------


def test_las_zonas_salen_en_el_mapa_con_su_circulo(cliente, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    zona = _crear(cliente, headers_de(admin))
    consulta = {"capas": "zonas", **DENTRO, "radio_m": 5000}

    del_admin = cliente.get("/mapa", params=consulta, headers=headers_de(admin))
    del_ciudadano = cliente.get("/mapa", params=consulta, headers=headers_de(crear_usuario()))

    assert del_admin.status_code == 200, del_admin.text
    punto = {p["id"]: p for p in del_admin.json()["puntos"]}[zona["id"]]
    assert punto["capa"] == "zona"
    assert punto["titulo"] == "Ribera del río"
    assert punto["tipo"] == "Desbordamiento del río Guatapurí"
    assert punto["prioridad"] == "alto"  # el nivel viaja en "prioridad"
    assert punto["radio_m"] == 800
    assert punto["aproximada"] is False
    assert punto["activo"] is True
    assert punto["propio"] is True
    # Es información pública: el ciudadano la ve, pero no es suya
    punto_ciudadano = {p["id"]: p for p in del_ciudadano.json()["puntos"]}[zona["id"]]
    assert punto_ciudadano["propio"] is False


def test_una_zona_desactivada_llega_al_mapa_como_inactiva_en_el_polling(cliente, crear_usuario, headers_de):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    zona = _crear(cliente, headers_de(admin))
    primera = cliente.get("/mapa", params={"capas": "zonas"}, headers=headers_de(admin)).json()
    assert zona["id"] in [p["id"] for p in primera["puntos"]]

    _modificar(cliente, headers_de(admin), zona["id"], estado="inactiva")
    segunda = cliente.get(
        "/mapa", params={"capas": "zonas", "desde": primera["generado_en"]}, headers=headers_de(admin)
    ).json()

    punto = {p["id"]: p for p in segunda["puntos"]}[zona["id"]]
    assert punto["activo"] is False  # el cliente la quita del mapa
