"""Organizaciones y sus administradores (A3)."""

from app.models.enums import RolUsuario

C, V, A, S = RolUsuario.CIUDADANO, RolUsuario.VOLUNTARIO, RolUsuario.ADMINISTRADOR, RolUsuario.SUPER_ADMIN
ORG = {"nombre": "  Cruz Roja   Valledupar ", "tipo": "cruz_roja", "telefono_contacto": "605 570 0000"}


def test_super_admin_crea_organizacion(cliente, crear_usuario, headers_de):
    r = cliente.post("/organizaciones", json=ORG, headers=headers_de(crear_usuario(S)))
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["nombre"] == "Cruz Roja Valledupar"
    assert cuerpo["activa"] is True
    assert cuerpo["telefono_contacto"] == "+576055700000"


def test_solo_super_admin_crea_o_edita(cliente, crear_usuario, headers_de):
    for rol in (C, V, A):
        usuario = crear_usuario(rol)
        assert cliente.post("/organizaciones", json=ORG, headers=headers_de(usuario)).status_code == 403
    admin = crear_usuario(A)
    r = cliente.patch(f"/organizaciones/{admin.organizacion_id}", json={"nombre": "X Y"}, headers=headers_de(admin))
    assert r.status_code == 403


def test_admin_y_voluntario_solo_ven_la_suya(cliente, crear_usuario, crear_organizacion, headers_de):
    admin = crear_usuario(A)
    otra = crear_organizacion()
    r = cliente.get("/organizaciones", headers=headers_de(admin))
    assert r.status_code == 200
    assert [o["id"] for o in r.json()["items"]] == [str(admin.organizacion_id)]

    assert cliente.get(f"/organizaciones/{otra.id}", headers=headers_de(admin)).status_code == 403
    voluntario = crear_usuario(V)
    assert cliente.get(f"/organizaciones/{voluntario.organizacion_id}", headers=headers_de(voluntario)).status_code == 200
    # El ciudadano no tiene organización
    assert cliente.get("/organizaciones", headers=headers_de(crear_usuario(C))).status_code == 403


def test_super_admin_lista_y_filtra(cliente, crear_usuario, crear_organizacion, headers_de):
    super_admin = crear_usuario(S)
    org = crear_organizacion(nombre="Bomberos Aguachica Único")
    r = cliente.get("/organizaciones?q=aguachica único", headers=headers_de(super_admin))
    assert [o["id"] for o in r.json()["items"]] == [str(org.id)]


def test_desactivar_organizacion_deja_sin_acceso_a_su_gente(cliente, crear_usuario, headers_de):
    super_admin = crear_usuario(S)
    admin = crear_usuario(A)
    voluntario = crear_usuario(V, organizacion=admin.organizacion)

    r = cliente.patch(
        f"/organizaciones/{admin.organizacion_id}", json={"activa": False}, headers=headers_de(super_admin)
    )
    assert r.status_code == 200 and r.json()["activa"] is False
    for usuario in (admin, voluntario):
        r = cliente.get("/usuarios/me", headers=headers_de(usuario))
        assert r.status_code == 403
        assert r.json()["codigo"] == "ORGANIZACION_INACTIVA"

    # Tampoco se pueden invitar administradores a una organización desactivada
    r = cliente.post(
        f"/organizaciones/{admin.organizacion_id}/administradores",
        json={"nombre": "Ana", "email": "ana@org.co"},
        headers=headers_de(super_admin),
    )
    assert r.json()["codigo"] == "ORGANIZACION_INACTIVA"


def test_invitar_listar_y_revocar_administrador(cliente, crear_usuario, crear_organizacion, headers_de):
    super_admin = crear_usuario(S)
    org = crear_organizacion()
    base = f"/organizaciones/{org.id}/administradores"

    r = cliente.post(base, json={"nombre": "Laura Mejía", "email": "laura@org.co"}, headers=headers_de(super_admin))
    assert r.status_code == 201, r.text
    invitacion = r.json()
    assert invitacion["usuario"]["rol"] == "administrador"
    assert invitacion["usuario"]["estado"] == "en_espera"
    assert invitacion["usuario"]["organizacion_id"] == str(org.id)

    # Activa su cuenta y entra como administrador de esa organización
    r = cliente.post(
        "/auth/activar",
        json={"email": "laura@org.co", "codigo": invitacion["codigo_activacion"], "password": "clave-admin-1",
              "acepta_tratamiento_datos": True},
    )
    assert r.status_code == 200 and r.json()["usuario"]["rol"] == "administrador"

    r = cliente.get(base, headers=headers_de(super_admin))
    assert [u["email"] for u in r.json()["items"]] == ["laura@org.co"]

    r = cliente.delete(f"{base}/{invitacion['usuario']['id']}", headers=headers_de(super_admin))
    assert r.status_code == 200 and r.json()["estado"] == "bloqueado"


def test_revocar_quien_no_es_admin_de_esa_organizacion(cliente, crear_usuario, crear_organizacion, headers_de):
    super_admin = crear_usuario(S)
    org = crear_organizacion()
    ajeno = crear_usuario(A)  # administrador de OTRA organización
    voluntario = crear_usuario(V, organizacion=org)
    for usuario in (ajeno, voluntario):
        r = cliente.delete(f"/organizaciones/{org.id}/administradores/{usuario.id}", headers=headers_de(super_admin))
        assert r.status_code == 404
        assert r.json()["codigo"] == "ADMINISTRADOR_NO_ENCONTRADO"


def test_organizacion_inexistente(cliente, crear_usuario, headers_de):
    r = cliente.get("/organizaciones/00000000-0000-0000-0000-000000000000", headers=headers_de(crear_usuario(S)))
    assert r.status_code == 404
    assert r.json()["codigo"] == "ORGANIZACION_NO_ENCONTRADA"
