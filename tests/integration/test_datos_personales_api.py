"""Ley 1581 (A6): exportar mis datos y eliminar mi cuenta (anonimizar)."""

from sqlalchemy import select

from app.models.asignacion import Asignacion
from app.models.auditoria import Auditoria
from app.models.contacto_emergencia import ContactoEmergencia
from app.models.dispositivo import Dispositivo
from app.models.enums import EstadoAsignacion, EstadoUsuario, RolUsuario
from app.models.solicitud_ayuda import SolicitudAyuda
from tests.conftest import PASSWORD_PRUEBAS

UBICACION = {"lat": 10.4631, "lng": -73.2532}


def _llenar(cliente, h):
    cliente.post(
        "/usuarios/me/consentimientos", json={"tipo": "ubicacion", "aceptado": True}, headers=h
    )
    cliente.patch("/usuarios/me/ubicacion", json=UBICACION, headers=h)
    cliente.post("/usuarios/me/contactos-emergencia", json={"nombre": "Ana", "telefono": "3001234567"}, headers=h)
    cliente.post("/usuarios/me/dispositivo", json={"token_push": "tok-123", "plataforma": "android"}, headers=h)
    cliente.post(
        "/solicitudes-ayuda",
        json={"descripcion": "Necesito agua", "tipo": "alimentaria", "ubicacion": UBICACION},
        headers=h,
    )


def test_exporta_todo_lo_mio(cliente, crear_usuario, headers_de, encolados):
    usuario = crear_usuario()
    h = headers_de(usuario)
    _llenar(cliente, h)
    r = cliente.get("/usuarios/me/datos", headers=h)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["perfil"]["email"] == usuario.email
    assert datos["ubicacion"]["ubicacion_actual"] == {"lat": 10.4631, "lng": -73.2532}
    assert [c["tipo"] for c in datos["consentimientos"]] == ["ubicacion"]
    assert datos["contactos_emergencia"][0]["telefono"] == "+573001234567"
    assert datos["dispositivos"] == [{"plataforma": "android", "creado_en": datos["dispositivos"][0]["creado_en"]}]
    assert [s["tipo"] for s in datos["solicitudes"]] == ["alimentaria"]
    assert datos["reportes"] == [] and datos["personas_reportadas"] == []
    assert "password_hash" not in r.text


def test_solo_exporta_lo_propio(cliente, crear_usuario, headers_de, encolados):
    _llenar(cliente, headers_de(crear_usuario()))
    datos = cliente.get("/usuarios/me/datos", headers=headers_de(crear_usuario())).json()
    assert datos["contactos_emergencia"] == [] and datos["solicitudes"] == [] and datos["dispositivos"] == []


def test_eliminar_cuenta_anonimiza_y_conserva_los_casos(cliente, db, crear_usuario, headers_de, encolados):
    usuario = crear_usuario()
    email = usuario.email
    h = headers_de(usuario)
    _llenar(cliente, h)
    cliente.patch("/usuarios/me", json={"telefono": "3109876543"}, headers=h)

    r = cliente.request("DELETE", "/usuarios/me", json={"password": PASSWORD_PRUEBAS}, headers=h)
    assert r.status_code == 204, r.text

    db.refresh(usuario)
    assert usuario.nombre == "Usuario eliminado" and usuario.email.endswith("@rescate360.invalid")
    assert usuario.telefono is None and usuario.ubicacion_actual is None
    assert usuario.estado == EstadoUsuario.BLOQUEADO and usuario.eliminado_en is not None
    assert db.scalars(select(ContactoEmergencia).where(ContactoEmergencia.usuario_id == usuario.id)).all() == []
    assert db.scalars(select(Dispositivo).where(Dispositivo.usuario_id == usuario.id)).all() == []
    # La solicitud sigue (le sirve a la emergencia), ya sin datos de quién la hizo
    assert len(db.scalars(select(SolicitudAyuda).where(SolicitudAyuda.usuario_id == usuario.id)).all()) == 1

    # La historia de auditoría ya no tiene sus datos personales
    historia = db.scalars(select(Auditoria).where(Auditoria.tabla == "usuarios", Auditoria.registro_id == usuario.id)).all()
    assert historia
    for fila in historia:
        for datos in (fila.datos_anteriores or {}, fila.datos_nuevos or {}):
            assert not {"nombre", "email", "telefono", "ubicacion_actual"} & datos.keys()

    # Ni el token viejo ni la contraseña sirven
    assert cliente.get("/usuarios/me", headers=h).status_code in (401, 403)
    login = cliente.post("/auth/login", json={"email": email, "password": PASSWORD_PRUEBAS})
    assert login.status_code == 401


def test_eliminar_pide_la_contrasena_correcta(cliente, crear_usuario, headers_de):
    h = headers_de(crear_usuario())
    r = cliente.request("DELETE", "/usuarios/me", json={"password": "otra-cosa"}, headers=h)
    assert r.status_code == 422 and r.json()["codigo"] == "CONTRASENA_ACTUAL_INVALIDA"
    assert cliente.get("/usuarios/me", headers=h).status_code == 200


def test_el_ultimo_super_admin_no_se_elimina(cliente, crear_usuario, headers_de):
    unico = crear_usuario(RolUsuario.SUPER_ADMIN)
    r = cliente.request("DELETE", "/usuarios/me", json={"password": PASSWORD_PRUEBAS}, headers=headers_de(unico))
    assert r.status_code == 409 and r.json()["codigo"] == "ULTIMO_SUPER_ADMIN"


def test_voluntario_eliminado_suelta_sus_tareas(cliente, db, crear_usuario, headers_de, encolados):
    voluntario = crear_usuario(RolUsuario.VOLUNTARIO)
    ciudadano = headers_de(crear_usuario())
    sid = cliente.post(
        "/solicitudes-ayuda",
        json={"descripcion": "Necesito agua", "tipo": "alimentaria", "ubicacion": UBICACION},
        headers=ciudadano,
    ).json()["id"]
    solicitud = db.get(SolicitudAyuda, sid)
    solicitud.organizacion_manual_id = voluntario.organizacion_id
    db.flush()
    hv = headers_de(voluntario)
    assert cliente.post(f"/solicitudes-ayuda/{sid}/asignar", headers=hv).status_code in (200, 201)

    cliente.request("DELETE", "/usuarios/me", json={"password": PASSWORD_PRUEBAS}, headers=hv)
    asignacion = db.scalars(select(Asignacion).where(Asignacion.voluntario_id == voluntario.id)).one()
    assert asignacion.estado_asignacion == EstadoAsignacion.CANCELADA
