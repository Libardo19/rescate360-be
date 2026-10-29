"""modo sin conexión: llave para firmar mensajes, origen mesh y datos del relevo

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-29

Dev A (B7 ampliado: sincronización y relevo por Bluetooth).

- `usuarios.llave_offline`: secreto HMAC de cada usuario. El teléfono firma sus mensajes sin
  conexión con ella y el backend verifica la firma cuando los sube otro teléfono: así un
  intermediario no puede inventar ni cambiar el SOS de otra persona. Es un secreto: se agrega
  a los que fn_auditoria() quita de la auditoría.
- `origen_solicitud` + `mesh`: el SOS que llegó saltando de teléfono en teléfono.
- `cola_alertas_offline`: quién lo subió (`subido_por`), cuántos saltos dio y qué se hizo con
  él (`resultado`, p. ej. "sos_creado").
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fn_auditoria(secretos: str) -> str:
    """Misma función de la 0009; solo cambia la lista de columnas que no se guardan."""
    return f"""
CREATE OR REPLACE FUNCTION fn_auditoria()
RETURNS TRIGGER AS $$
DECLARE
  v_usuario_id UUID;
BEGIN
  v_usuario_id := NULLIF(current_setting('app.usuario_id', true), '')::UUID;

  IF (TG_OP = 'INSERT') THEN
    INSERT INTO auditoria (id, tabla, registro_id, operacion, usuario_id, datos_nuevos)
    VALUES (gen_random_uuid(), TG_TABLE_NAME, NEW.id, 'INSERT', v_usuario_id, (to_jsonb(NEW) - {secretos}));
    RETURN NEW;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO auditoria (id, tabla, registro_id, operacion, usuario_id, datos_anteriores, datos_nuevos)
    VALUES (gen_random_uuid(), TG_TABLE_NAME, NEW.id, 'UPDATE', v_usuario_id,
            (to_jsonb(OLD) - {secretos}), (to_jsonb(NEW) - {secretos}));
    RETURN NEW;
  ELSIF (TG_OP = 'DELETE') THEN
    INSERT INTO auditoria (id, tabla, registro_id, operacion, usuario_id, datos_anteriores)
    VALUES (gen_random_uuid(), TG_TABLE_NAME, OLD.id, 'DELETE', v_usuario_id, (to_jsonb(OLD) - {secretos}));
    RETURN OLD;
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


_SECRETOS_0009 = "ARRAY['password_hash', 'codigo_activacion_hash', 'codigo_recuperacion_hash']"
_SECRETOS = "ARRAY['password_hash', 'codigo_activacion_hash', 'codigo_recuperacion_hash', 'llave_offline']"


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("llave_offline", sa.String(64), nullable=True))
    op.execute(_fn_auditoria(_SECRETOS))
    # Las llaves que ya hubieran quedado en la auditoría (no debería haber ninguna) se borran
    op.execute(
        "UPDATE auditoria SET datos_anteriores = datos_anteriores - 'llave_offline', "
        "datos_nuevos = datos_nuevos - 'llave_offline' WHERE tabla = 'usuarios'"
    )

    op.execute("ALTER TYPE origen_solicitud ADD VALUE IF NOT EXISTS 'mesh'")

    op.add_column(
        "cola_alertas_offline",
        sa.Column("subido_por", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=True),
    )
    op.add_column("cola_alertas_offline", sa.Column("saltos", sa.SmallInteger(), nullable=False, server_default="0"))
    op.add_column("cola_alertas_offline", sa.Column("resultado", sa.String(30), nullable=True))
    op.add_column(
        "cola_alertas_offline",
        sa.Column("recibido_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_check_constraint("chk_cola_alertas_offline_saltos", "cola_alertas_offline", "saltos BETWEEN 0 AND 8")
    op.create_index("ix_cola_alertas_offline_sincronizado", "cola_alertas_offline", ["sincronizado"])


def downgrade() -> None:
    op.drop_index("ix_cola_alertas_offline_sincronizado", table_name="cola_alertas_offline")
    op.drop_constraint("chk_cola_alertas_offline_saltos", "cola_alertas_offline", type_="check")
    for columna in ("recibido_en", "resultado", "saltos", "subido_por"):
        op.drop_column("cola_alertas_offline", columna)
    # Un valor de enum no se puede quitar: los SOS que llegaron por mesh quedan como sos
    op.execute("UPDATE solicitudes_ayuda SET origen = 'sos' WHERE origen = 'mesh'")
    op.execute(_fn_auditoria(_SECRETOS_0009))
    op.drop_column("usuarios", "llave_offline")
