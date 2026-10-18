"""El trigger fn_auditoria() recibe el actor que fija la API."""

from sqlalchemy import select

from app.middlewares.audit_middleware import fijar_actor
from app.models.auditoria import Auditoria
from app.models.contacto_emergencia import ContactoEmergencia
from app.models.enums import OperacionAuditoria, RolUsuario


def _ultima(db, tabla, registro_id):
    return db.scalar(
        select(Auditoria)
        .where(Auditoria.tabla == tabla, Auditoria.registro_id == registro_id)
        .order_by(Auditoria.creado_en.desc())
    )


def test_registro_publico_queda_sin_actor_y_el_consentimiento_con_el_usuario(cliente, db):
    r = cliente.post(
        "/auth/registro",
        json={"nombre": "Ana", "email": "ana@prueba.co", "password": "clave-segura-1", "acepta_tratamiento_datos": True},
    )
    usuario_id = r.json()["usuario"]["id"]

    alta = _ultima(db, "usuarios", usuario_id)
    assert alta.operacion == OperacionAuditoria.INSERT
    assert alta.usuario_id is None  # nadie había iniciado sesión

    consentimiento = db.scalar(
        select(Auditoria).where(Auditoria.tabla == "consentimientos", Auditoria.datos_nuevos["usuario_id"].astext == usuario_id)
    )
    assert str(consentimiento.usuario_id) == usuario_id


def test_cambio_con_actor(db, crear_usuario):
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    fijar_actor(db, admin.id)
    contacto = ContactoEmergencia(usuario_id=admin.id, nombre="Mamá", telefono="+573001234567")
    db.add(contacto)
    db.flush()

    fila = _ultima(db, "contactos_emergencia", contacto.id)
    assert fila.operacion == OperacionAuditoria.INSERT
    assert fila.usuario_id == admin.id


def test_insert_sin_actor_despues_de_una_transaccion_con_actor(db, crear_usuario):
    """Regresión: current_setting() devolvía '' y ''::UUID rompía cualquier INSERT."""
    admin = crear_usuario(RolUsuario.ADMINISTRADOR)
    fijar_actor(db, admin.id)
    db.commit()  # termina la transacción (SAVEPOINT en las pruebas)

    fijar_actor(db, None)
    db.execute(select(1))  # nueva transacción sin actor
    otro = crear_usuario()  # dispara el trigger de usuarios
    assert _ultima(db, "usuarios", otro.id) is not None
