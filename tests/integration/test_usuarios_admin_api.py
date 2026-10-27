"""Gestión de usuarios desde el panel y alta por invitación (A3)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.auditoria import Auditoria
from app.models.consentimiento import Consentimiento
from app.models.enums import EstadoUsuario, RolUsuario, TipoConsentimiento
from app.models.usuario import Usuario

C, V, A, S = RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN
NUEVO = {"nombre": "  Marta   Salcedo ", "email": "Marta@Demo.com", "telefono": "300 123 4567"}


def _invitar(cliente, headers, **extra):
    return cliente.post("/usuarios", json={**NUEVO, **extra}, headers=headers)


def _activar(cliente, email, codigo, password="clave-nueva-123"):
    return cliente.post(
        "/auth/activar",
        json={"email": email, "codigo": codigo, "password": password, "acepta_tratamiento_datos": True},
    )


# --- alta por invitación ---


def test_admin_invita_voluntario_en_su_organizacion(cliente, crear_usuario, headers_de, db):
    admin = crear_usuario(A)
    r = _invitar(cliente, headers_de(admin))
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    usuario = cuerpo["usuario"]
    assert usuario["rol"] == "voluntario"
    assert usuario["estado"] == "en_espera"
    assert usuario["organizacion_id"] == str(admin.organizacion_id)
    assert usuario["nombre"] == "Marta Salcedo"
    assert usuario["email"] == "marta@demo.com"
    assert usuario["telefono"] == "+573001234567"
    assert usuario["codigo"].startswith("USR-")
    assert len(cuerpo["codigo_activacion"]) == 9  # XXXX-XXXX

    # En la BD solo queda el hash del código
    guardado = db.get(Usuario, usuario["id"])
    assert guardado.codigo_activacion_hash and cuerpo["codigo_activacion"] not in guardado.codigo_activacion_hash


def test_admin_no_invita_en_otra_organizacion(cliente, crear_usuario, crear_organizacion, headers_de):
    admin = crear_usuario(A)
    otra = crear_organizacion()
    r = _invitar(cliente, headers_de(admin), organizacion_id=str(otra.id))
    assert r.status_code == 403
    assert r.json()["codigo"] == "FUERA_DE_ALCANCE"


def test_super_admin_debe_indicar_la_organizacion(cliente, crear_usuario, crear_organizacion, headers_de):
    super_admin = crear_usuario(S)
    r = _invitar(cliente, headers_de(super_admin))
    assert r.status_code == 422
    assert r.json()["codigo"] == "ORGANIZACION_REQUERIDA"

    org = crear_organizacion()
    r = _invitar(cliente, headers_de(super_admin), organizacion_id=str(org.id))
    assert r.status_code == 201
    assert r.json()["usuario"]["organizacion_id"] == str(org.id)


def test_invitar_correo_repetido(cliente, crear_usuario, headers_de):
    admin = crear_usuario(A)
    crear_usuario(email="marta@demo.com")
    r = _invitar(cliente, headers_de(admin))
    assert r.status_code == 409
    assert r.json()["codigo"] == "EMAIL_YA_REGISTRADO"


def test_voluntario_y_ciudadano_no_gestionan_usuarios(cliente, crear_usuario, headers_de):
    for rol in (C, V):
        headers = headers_de(crear_usuario(rol))
        assert cliente.get("/usuarios", headers=headers).status_code == 403
        assert _invitar(cliente, headers).status_code == 403


def test_codigos_usr_son_unicos_y_consecutivos(cliente, crear_usuario, headers_de):
    admin = crear_usuario(A)
    a = _invitar(cliente, headers_de(admin), email="a@demo.com").json()["usuario"]["codigo"]
    b = _invitar(cliente, headers_de(admin), email="b@demo.com").json()["usuario"]["codigo"]
    assert a != b
    assert int(b.removeprefix("USR-")) == int(a.removeprefix("USR-")) + 1


# --- activación ---


def test_activar_con_el_codigo(cliente, crear_usuario, headers_de, db):
    admin = crear_usuario(A)
    invitacion = _invitar(cliente, headers_de(admin)).json()

    r = _activar(cliente, "marta@demo.com", invitacion["codigo_activacion"].lower().replace("-", ""))
    assert r.status_code == 200, r.text
    assert r.json()["usuario"]["estado"] == "activo"
    assert r.json()["access_token"]

    usuario = db.get(Usuario, invitacion["usuario"]["id"])
    assert usuario.codigo_activacion_hash is None and usuario.codigo_activacion_vence is None
    consentimiento = db.scalar(select(Consentimiento).where(Consentimiento.usuario_id == usuario.id))
    assert consentimiento.tipo == TipoConsentimiento.TRATAMIENTO_DATOS

    # Ya puede iniciar sesión con su contraseña, y el código no sirve otra vez
    login = cliente.post("/auth/login", json={"email": "marta@demo.com", "password": "clave-nueva-123"})
    assert login.status_code == 200
    assert _activar(cliente, "marta@demo.com", invitacion["codigo_activacion"]).status_code == 422


def test_activar_con_codigo_errado_o_correo_ajeno(cliente, crear_usuario, headers_de):
    admin = crear_usuario(A)
    invitacion = _invitar(cliente, headers_de(admin)).json()
    for email, codigo in [("marta@demo.com", "AAAA-AAAA"), ("otro@demo.com", invitacion["codigo_activacion"])]:
        r = _activar(cliente, email, codigo)
        assert r.status_code == 422
        assert r.json()["codigo"] == "CODIGO_ACTIVACION_INVALIDO"


def test_activar_con_codigo_vencido(cliente, crear_usuario, headers_de, db):
    admin = crear_usuario(A)
    invitacion = _invitar(cliente, headers_de(admin)).json()
    usuario = db.get(Usuario, invitacion["usuario"]["id"])
    usuario.codigo_activacion_vence = datetime.now(UTC) - timedelta(minutes=1)
    db.flush()
    assert _activar(cliente, "marta@demo.com", invitacion["codigo_activacion"]).status_code == 422


def test_invitado_no_entra_por_login_antes_de_activar(cliente, crear_usuario, headers_de):
    admin = crear_usuario(A)
    _invitar(cliente, headers_de(admin))
    r = cliente.post("/auth/login", json={"email": "marta@demo.com", "password": "cualquier-cosa"})
    assert r.status_code == 401


def test_regenerar_codigo_invalida_el_anterior(cliente, crear_usuario, headers_de):
    admin = crear_usuario(A)
    invitacion = _invitar(cliente, headers_de(admin)).json()
    r = cliente.post(f"/usuarios/{invitacion['usuario']['id']}/codigo-activacion", headers=headers_de(admin))
    assert r.status_code == 200
    nuevo = r.json()["codigo_activacion"]

    assert _activar(cliente, "marta@demo.com", invitacion["codigo_activacion"]).status_code == 422
    assert _activar(cliente, "marta@demo.com", nuevo).status_code == 200
    # Ya activa: no se regenera
    r = cliente.post(f"/usuarios/{invitacion['usuario']['id']}/codigo-activacion", headers=headers_de(admin))
    assert r.json()["codigo"] == "CUENTA_NO_PENDIENTE"


def test_el_codigo_no_queda_en_la_auditoria(cliente, crear_usuario, headers_de, db):
    admin = crear_usuario(A)
    invitacion = _invitar(cliente, headers_de(admin)).json()
    _activar(cliente, "marta@demo.com", invitacion["codigo_activacion"])

    filas = db.scalars(select(Auditoria).where(Auditoria.registro_id == invitacion["usuario"]["id"])).all()
    assert filas
    for fila in filas:
        for datos in (fila.datos_nuevos, fila.datos_anteriores):
            assert not datos or ("password_hash" not in datos and "codigo_activacion_hash" not in datos)


# --- listar y ver ---


def test_admin_solo_lista_su_organizacion(cliente, crear_usuario, headers_de):
    admin = crear_usuario(A)
    propio = crear_usuario(V, organizacion=admin.organizacion)
    crear_usuario(V)  # de otra organización
    crear_usuario(C)  # ciudadano: sin organización

    r = cliente.get("/usuarios", headers=headers_de(admin))
    assert r.status_code == 200
    ids = {u["id"] for u in r.json()["items"]}
    assert ids == {str(admin.id), str(propio.id)}

    # Aunque pida otra organización, sigue viendo solo la suya
    r = cliente.get(f"/usuarios?organizacion_id={crear_usuario(V).organizacion_id}", headers=headers_de(admin))
    assert {u["id"] for u in r.json()["items"]} == {str(admin.id), str(propio.id)}


def test_super_admin_lista_todo_y_filtra(cliente, crear_usuario, headers_de):
    super_admin = crear_usuario(S)
    ciudadano = crear_usuario(C)
    crear_usuario(V)
    r = cliente.get("/usuarios?rol=ciudadano&por_pagina=100", headers=headers_de(super_admin))
    assert r.status_code == 200
    assert str(ciudadano.id) in {u["id"] for u in r.json()["items"]}
    assert all(u["rol"] == "ciudadano" for u in r.json()["items"])

    r = cliente.get(f"/usuarios?q={ciudadano.email}", headers=headers_de(super_admin))
    assert [u["id"] for u in r.json()["items"]] == [str(ciudadano.id)]


def test_admin_no_ve_usuario_de_otra_organizacion(cliente, crear_usuario, headers_de):
    admin = crear_usuario(A)
    for ajeno in (crear_usuario(V), crear_usuario(C)):
        r = cliente.get(f"/usuarios/{ajeno.id}", headers=headers_de(admin))
        assert r.status_code == 403
        assert r.json()["codigo"] == "FUERA_DE_ALCANCE"


# --- editar y bloquear ---


def test_admin_bloquea_y_desbloquea_voluntario(cliente, crear_usuario, headers_de):
    admin = crear_usuario(A)
    voluntario = crear_usuario(V, organizacion=admin.organizacion)
    r = cliente.patch(f"/usuarios/{voluntario.id}", json={"estado": "bloqueado"}, headers=headers_de(admin))
    assert r.status_code == 200
    assert r.json()["estado"] == "bloqueado"
    # Bloqueado ya no opera
    assert cliente.get("/usuarios/me", headers=headers_de(voluntario)).json()["codigo"] == "USUARIO_BLOQUEADO"

    r = cliente.patch(f"/usuarios/{voluntario.id}", json={"estado": "activo"}, headers=headers_de(admin))
    assert r.json()["estado"] == "activo"


def test_admin_no_gestiona_otros_administradores(cliente, crear_usuario, headers_de):
    admin = crear_usuario(A)
    colega = crear_usuario(A, organizacion=admin.organizacion)
    r = cliente.patch(f"/usuarios/{colega.id}", json={"estado": "bloqueado"}, headers=headers_de(admin))
    assert r.status_code == 403
    assert r.json()["codigo"] == "USUARIO_NO_GESTIONABLE"


def test_desbloquear_un_invitado_lo_deja_en_espera(cliente, crear_usuario, headers_de):
    admin = crear_usuario(A)
    invitado = _invitar(cliente, headers_de(admin)).json()["usuario"]
    url = f"/usuarios/{invitado['id']}"
    # en_espera → activo a mano: no, se activa con el código
    assert cliente.patch(url, json={"estado": "activo"}, headers=headers_de(admin)).json()["codigo"] == "CUENTA_SIN_ACTIVAR"
    cliente.patch(url, json={"estado": "bloqueado"}, headers=headers_de(admin))
    r = cliente.patch(url, json={"estado": "activo"}, headers=headers_de(admin))
    assert r.json()["estado"] == "en_espera"


def test_en_espera_no_se_pone_a_mano(cliente, crear_usuario, headers_de):
    admin = crear_usuario(A)
    voluntario = crear_usuario(V, organizacion=admin.organizacion)
    r = cliente.patch(f"/usuarios/{voluntario.id}", json={"estado": "en_espera"}, headers=headers_de(admin))
    assert r.status_code == 422


def test_editar_datos_y_correo_repetido(cliente, crear_usuario, headers_de):
    admin = crear_usuario(A)
    voluntario = crear_usuario(V, organizacion=admin.organizacion)
    otro = crear_usuario()
    url = f"/usuarios/{voluntario.id}"
    r = cliente.patch(url, json={"nombre": "Nuevo Nombre", "email": "NUEVO@demo.com"}, headers=headers_de(admin))
    assert r.status_code == 200
    assert (r.json()["nombre"], r.json()["email"]) == ("Nuevo Nombre", "nuevo@demo.com")

    r = cliente.patch(url, json={"email": otro.email}, headers=headers_de(admin))
    assert r.json()["codigo"] == "EMAIL_YA_REGISTRADO"


def test_super_admin_no_cambia_su_propio_estado(cliente, crear_usuario, headers_de):
    super_admin = crear_usuario(S)
    r = cliente.patch(f"/usuarios/{super_admin.id}", json={"estado": "bloqueado"}, headers=headers_de(super_admin))
    assert r.status_code == 409
    assert r.json()["codigo"] == "AUTOPROTECCION"


def test_super_admin_bloquea_a_otro_super_admin(cliente, crear_usuario, headers_de):
    uno, dos = crear_usuario(S), crear_usuario(S)
    r = cliente.patch(f"/usuarios/{dos.id}", json={"estado": "bloqueado"}, headers=headers_de(uno))
    assert r.status_code == 200  # queda al menos "uno" activo
    assert cliente.get("/usuarios", headers=headers_de(dos)).json()["codigo"] == "USUARIO_BLOQUEADO"


def test_ultimo_super_admin_no_se_puede_bloquear(db, crear_usuario):
    """Sin pasar por HTTP: con un solo super admin activo, el service se niega a bloquearlo."""
    import pytest

    from app.core.excepciones import Conflicto
    from app.schemas.usuarios_schema import UsuarioCambiosIn
    from app.services import usuarios_service

    for otro in db.scalars(select(Usuario).where(Usuario.rol == S)).all():
        otro.estado = EstadoUsuario.BLOQUEADO
    db.flush()
    unico = crear_usuario(S)
    # El actor es un super admin bloqueado (caso límite: la regla no depende de quién lo pida)
    actor = crear_usuario(S, estado=EstadoUsuario.BLOQUEADO)
    with pytest.raises(Conflicto) as error:
        usuarios_service.actualizar_usuario(db, actor, unico.id, UsuarioCambiosIn(estado=EstadoUsuario.BLOQUEADO))
    assert error.value.codigo == "ULTIMO_SUPER_ADMIN"


# --- mi perfil ---


def test_editar_mi_perfil(cliente, crear_usuario, headers_de):
    usuario = crear_usuario()
    r = cliente.patch("/usuarios/me", json={"nombre": " Ana  María ", "telefono": "3001112233"}, headers=headers_de(usuario))
    assert r.status_code == 200
    assert (r.json()["nombre"], r.json()["telefono"]) == ("Ana María", "+573001112233")
    # El correo y el rol no se cambian por aquí
    r = cliente.patch("/usuarios/me", json={"rol": "super_admin", "email": "x@x.co"}, headers=headers_de(usuario))
    assert (r.json()["rol"], r.json()["email"]) == ("ciudadano", usuario.email)
