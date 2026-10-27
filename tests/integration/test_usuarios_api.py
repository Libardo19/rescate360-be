from sqlalchemy import select

from app.models.dispositivo import Dispositivo
from app.models.enums import RolUsuario
from app.repositories import dispositivos_repository

UBICACION = {"lat": 10.4631, "lng": -73.2532}  # Valledupar


def _autorizar_ubicacion(cliente, headers, aceptado=True):
    return cliente.post(
        "/usuarios/me/consentimientos", json={"tipo": "ubicacion", "aceptado": aceptado}, headers=headers
    )


# --- /usuarios/me ---


def test_me_devuelve_mi_perfil(cliente, crear_usuario, headers_de):
    usuario = crear_usuario()
    r = cliente.get("/usuarios/me", headers=headers_de(usuario))
    assert r.status_code == 200, r.text
    assert r.json()["id"] == str(usuario.id)
    assert "password_hash" not in r.json()


def test_me_sin_token(cliente):
    r = cliente.get("/usuarios/me")
    assert r.status_code == 401
    assert r.json()["codigo"] == "TOKEN_REQUERIDO"


# --- ubicación ---


def test_ubicacion_sin_consentimiento_se_rechaza(cliente, crear_usuario, headers_de, db):
    usuario = crear_usuario()
    r = cliente.patch("/usuarios/me/ubicacion", json=UBICACION, headers=headers_de(usuario))
    assert r.status_code == 403
    assert r.json()["codigo"] == "CONSENTIMIENTO_UBICACION_REQUERIDO"
    db.refresh(usuario)
    assert usuario.ubicacion_actual is None


def test_ubicacion_con_consentimiento_se_guarda(cliente, crear_usuario, headers_de, db):
    usuario = crear_usuario(RolUsuario.VOLUNTARIO)
    headers = headers_de(usuario)
    assert _autorizar_ubicacion(cliente, headers).status_code == 201

    r = cliente.patch("/usuarios/me/ubicacion", json=UBICACION, headers=headers)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["ubicacion_actual"]["lat"] == UBICACION["lat"]
    assert cuerpo["ubicacion_actual"]["lng"] == UBICACION["lng"]
    assert cuerpo["ubicacion_actualizada_en"] is not None

    db.refresh(usuario)
    assert usuario.ubicacion_actual is not None
    assert usuario.ubicacion_actualizada_en is not None


def test_ubicacion_fuera_de_rango(cliente, crear_usuario, headers_de):
    usuario = crear_usuario()
    headers = headers_de(usuario)
    _autorizar_ubicacion(cliente, headers)
    r = cliente.patch("/usuarios/me/ubicacion", json={"lat": 120, "lng": 0}, headers=headers)
    assert r.status_code == 422
    assert r.json()["errores"][0]["campo"] == "lat"


def test_retirar_consentimiento_borra_la_ubicacion(cliente, crear_usuario, headers_de, db):
    usuario = crear_usuario()
    headers = headers_de(usuario)
    _autorizar_ubicacion(cliente, headers)
    cliente.patch("/usuarios/me/ubicacion", json=UBICACION, headers=headers)

    r = _autorizar_ubicacion(cliente, headers, aceptado=False)
    assert r.status_code == 201
    db.refresh(usuario)
    assert usuario.ubicacion_actual is None
    assert usuario.ubicacion_actualizada_en is None

    # Y ya no se puede volver a guardar hasta autorizar de nuevo
    r = cliente.patch("/usuarios/me/ubicacion", json=UBICACION, headers=headers)
    assert r.status_code == 403


# --- consentimientos ---


def test_consentimientos_quedan_en_el_historial(cliente, crear_usuario, headers_de):
    usuario = crear_usuario()
    headers = headers_de(usuario)
    _autorizar_ubicacion(cliente, headers)
    _autorizar_ubicacion(cliente, headers, aceptado=False)

    r = cliente.get("/usuarios/me/consentimientos", headers=headers)
    assert r.status_code == 200
    assert [(c["tipo"], c["aceptado"]) for c in r.json()] == [("ubicacion", True), ("ubicacion", False)]


def test_no_se_retira_tratamiento_de_datos_por_aqui(cliente, crear_usuario, headers_de):
    usuario = crear_usuario()
    r = cliente.post(
        "/usuarios/me/consentimientos",
        json={"tipo": "tratamiento_datos", "aceptado": False},
        headers=headers_de(usuario),
    )
    assert r.status_code == 422
    assert r.json()["codigo"] == "CONSENTIMIENTO_NO_MODIFICABLE"


# --- dispositivos ---


def test_registrar_dispositivo(cliente, crear_usuario, headers_de, db):
    usuario = crear_usuario()
    r = cliente.post(
        "/usuarios/me/dispositivo",
        json={"token_push": "fcm-token-1", "plataforma": "android"},
        headers=headers_de(usuario),
    )
    assert r.status_code == 200, r.text
    assert r.json()["token_push"] == "fcm-token-1"
    assert dispositivos_repository.tokens_de_usuarios(db, [usuario.id]) == ["fcm-token-1"]


def test_registrar_el_mismo_token_dos_veces_no_duplica(cliente, crear_usuario, headers_de, db):
    usuario = crear_usuario()
    datos = {"token_push": "fcm-token-2", "plataforma": "android"}
    cliente.post("/usuarios/me/dispositivo", json=datos, headers=headers_de(usuario))
    r = cliente.post("/usuarios/me/dispositivo", json={**datos, "plataforma": "ios"}, headers=headers_de(usuario))
    assert r.status_code == 200
    filas = db.scalars(select(Dispositivo).where(Dispositivo.token_push == "fcm-token-2")).all()
    assert len(filas) == 1
    assert filas[0].plataforma.value == "ios"


def test_token_pasa_al_usuario_que_inicia_sesion_en_el_telefono(cliente, crear_usuario, headers_de, db):
    anterior, nuevo = crear_usuario(), crear_usuario()
    datos = {"token_push": "fcm-token-3", "plataforma": "android"}
    cliente.post("/usuarios/me/dispositivo", json=datos, headers=headers_de(anterior))
    cliente.post("/usuarios/me/dispositivo", json=datos, headers=headers_de(nuevo))

    assert dispositivos_repository.tokens_de_usuarios(db, [anterior.id]) == []
    assert dispositivos_repository.tokens_de_usuarios(db, [nuevo.id]) == ["fcm-token-3"]


def test_eliminar_dispositivo_es_idempotente(cliente, crear_usuario, headers_de, db):
    usuario = crear_usuario()
    headers = headers_de(usuario)
    cliente.post("/usuarios/me/dispositivo", json={"token_push": "fcm-token-4", "plataforma": "ios"}, headers=headers)

    assert cliente.delete("/usuarios/me/dispositivo/fcm-token-4", headers=headers).status_code == 204
    assert cliente.delete("/usuarios/me/dispositivo/fcm-token-4", headers=headers).status_code == 204
    assert dispositivos_repository.tokens_de_usuarios(db, [usuario.id]) == []


def test_no_se_puede_borrar_el_token_de_otro(cliente, crear_usuario, headers_de, db):
    dueno, otro = crear_usuario(), crear_usuario()
    cliente.post(
        "/usuarios/me/dispositivo", json={"token_push": "fcm-token-5", "plataforma": "android"}, headers=headers_de(dueno)
    )
    assert cliente.delete("/usuarios/me/dispositivo/fcm-token-5", headers=headers_de(otro)).status_code == 204
    assert dispositivos_repository.tokens_de_usuarios(db, [dueno.id]) == ["fcm-token-5"]


def test_plataforma_invalida(cliente, crear_usuario, headers_de):
    usuario = crear_usuario()
    r = cliente.post(
        "/usuarios/me/dispositivo", json={"token_push": "x", "plataforma": "symbian"}, headers=headers_de(usuario)
    )
    assert r.status_code == 422
