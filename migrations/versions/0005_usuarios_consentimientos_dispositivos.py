"""usuarios (estado, ultimo_acceso, teléfono E.164), consentimientos, dispositivos
y corrección de fn_auditoria()

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-16

Dev A. Va después de la 0004 (la 0004 de Dev B entró a develop primero y esta
migración se ajustó, regla del plan: el segundo en mergear ajusta).

Escrita a mano (sin --autogenerate) porque los modelos de centros, alertas, zonas
y donaciones todavía no declaran lo que creó la 0003, y el autogenerate propondría
borrarlo.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

estado_usuario = postgresql.ENUM("activo", "en_espera", "bloqueado", name="estado_usuario", create_type=False)
tipo_consentimiento = postgresql.ENUM(
    "tratamiento_datos", "ubicacion", "foto_persona", name="tipo_consentimiento", create_type=False
)
plataforma_dispositivo = postgresql.ENUM("android", "ios", "web", name="plataforma_dispositivo", create_type=False)

# Tablas nuevas o de Dev A que deben quedar en la auditoría (regla S-9)
TABLAS_AUDITADAS = ["consentimientos", "contactos_emergencia"]

# current_setting() devuelve '' (no NULL) después de que la conexión ya tuvo un actor
# en una transacción anterior. ''::UUID revienta y bloquea cualquier INSERT sin usuario
# (registro, jobs). NULLIF lo convierte en NULL.
FN_AUDITORIA_CORREGIDA = """
CREATE OR REPLACE FUNCTION fn_auditoria()
RETURNS TRIGGER AS $$
DECLARE
  v_usuario_id UUID;
BEGIN
  v_usuario_id := NULLIF(current_setting('app.usuario_id', true), '')::UUID;

  IF (TG_OP = 'INSERT') THEN
    INSERT INTO auditoria (id, tabla, registro_id, operacion, usuario_id, datos_nuevos)
    VALUES (gen_random_uuid(), TG_TABLE_NAME, NEW.id, 'INSERT', v_usuario_id, to_jsonb(NEW));
    RETURN NEW;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO auditoria (id, tabla, registro_id, operacion, usuario_id, datos_anteriores, datos_nuevos)
    VALUES (gen_random_uuid(), TG_TABLE_NAME, NEW.id, 'UPDATE', v_usuario_id, to_jsonb(OLD), to_jsonb(NEW));
    RETURN NEW;
  ELSIF (TG_OP = 'DELETE') THEN
    INSERT INTO auditoria (id, tabla, registro_id, operacion, usuario_id, datos_anteriores)
    VALUES (gen_random_uuid(), TG_TABLE_NAME, OLD.id, 'DELETE', v_usuario_id, to_jsonb(OLD));
    RETURN OLD;
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(FN_AUDITORIA_CORREGIDA)

    # --- usuarios: estado en lugar del booleano activo ---
    estado_usuario.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "usuarios",
        sa.Column("estado", estado_usuario, nullable=False, server_default="activo"),
    )
    op.execute("UPDATE usuarios SET estado = 'bloqueado' WHERE activo = false")
    op.drop_column("usuarios", "activo")
    op.add_column("usuarios", sa.Column("ultimo_acceso", sa.DateTime(timezone=True), nullable=True))

    # --- teléfonos en E.164 (+573001234567) ---
    op.alter_column("usuarios", "telefono", type_=sa.String(15), existing_type=sa.String(10), existing_nullable=True)
    op.alter_column(
        "contactos_emergencia", "telefono", type_=sa.String(15), existing_type=sa.String(10), existing_nullable=False
    )

    # --- consentimientos (Ley 1581) ---
    tipo_consentimiento.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "consentimientos",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=False),
        sa.Column("tipo", tipo_consentimiento, nullable=False),
        sa.Column("aceptado", sa.Boolean(), nullable=False),
        sa.Column("version_politica", sa.String(20), nullable=False),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consentimientos_usuario_id", "consentimientos", ["usuario_id"])

    # --- dispositivos (token de push) ---
    plataforma_dispositivo.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "dispositivos",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=False),
        sa.Column("token_push", sa.String(255), nullable=False),
        sa.Column("plataforma", plataforma_dispositivo, nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_push"),
    )
    op.create_index("ix_dispositivos_usuario_id", "dispositivos", ["usuario_id"])

    for tabla in TABLAS_AUDITADAS:
        op.execute(
            f"""
            CREATE TRIGGER trg_auditoria_{tabla}
            AFTER INSERT OR UPDATE OR DELETE ON {tabla}
            FOR EACH ROW EXECUTE FUNCTION fn_auditoria();
            """
        )


def downgrade() -> None:
    for tabla in TABLAS_AUDITADAS:
        op.execute(f"DROP TRIGGER IF EXISTS trg_auditoria_{tabla} ON {tabla};")

    op.drop_index("ix_dispositivos_usuario_id", table_name="dispositivos")
    op.drop_table("dispositivos")
    plataforma_dispositivo.drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_consentimientos_usuario_id", table_name="consentimientos")
    op.drop_table("consentimientos")
    tipo_consentimiento.drop(op.get_bind(), checkfirst=True)

    # Los teléfonos de más de 10 caracteres se recortan para poder volver a String(10)
    op.execute("UPDATE contactos_emergencia SET telefono = right(telefono, 10)")
    op.execute("UPDATE usuarios SET telefono = right(telefono, 10) WHERE telefono IS NOT NULL")
    op.alter_column(
        "contactos_emergencia", "telefono", type_=sa.String(10), existing_type=sa.String(15), existing_nullable=False
    )
    op.alter_column("usuarios", "telefono", type_=sa.String(10), existing_type=sa.String(15), existing_nullable=True)

    op.drop_column("usuarios", "ultimo_acceso")
    op.add_column("usuarios", sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"))
    op.execute("UPDATE usuarios SET activo = (estado = 'activo')")
    op.drop_column("usuarios", "estado")
    estado_usuario.drop(op.get_bind(), checkfirst=True)
    # fn_auditoria() se deja corregida: la versión anterior tenía el error de ''::UUID.
