"""Quién hizo cada cambio, para los triggers de auditoría.

La función `fn_auditoria()` de Postgres lee `current_setting('app.usuario_id')`
para guardar el actor de cada INSERT/UPDATE/DELETE. Ese valor es local a la
transacción, así que hay que fijarlo al inicio de CADA transacción de la sesión:

- En los endpoints lo hace `get_current_user` automáticamente.
- En los jobs de Celery (no hay request), hay que llamarlo a mano:

      fijar_actor(db, usuario_id)

Si no se fija, la fila de auditoría queda con `usuario_id` nulo (por ejemplo, en el
autorregistro, donde todavía no hay usuario).
"""

from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.orm import Session

_CLAVE = "auditoria_usuario_id"
_SQL = text("SELECT set_config('app.usuario_id', :usuario_id, true)")


def fijar_actor(session: Session, usuario_id: UUID | str | None) -> None:
    session.info[_CLAVE] = str(usuario_id) if usuario_id else None
    # Si ya hay una transacción abierta, el listener no vuelve a correr: se aplica ya.
    if session.in_transaction() and usuario_id:
        session.connection().execute(_SQL, {"usuario_id": str(usuario_id)})


@event.listens_for(Session, "after_begin")
def _fijar_actor_al_iniciar_transaccion(session, transaction, connection):
    usuario_id = session.info.get(_CLAVE)
    if usuario_id:
        connection.execute(_SQL, {"usuario_id": usuario_id})
