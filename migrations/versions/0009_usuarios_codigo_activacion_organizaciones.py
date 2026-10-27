"""usuarios: código USR-001 y código de activación; organizaciones: teléfono E.164;
fn_auditoria() sin secretos

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-26

Dev A (A3).

- `usuarios.codigo`: identificador legible que muestra el panel (USR-001). Sale de una
  secuencia, así que dos altas simultáneas nunca repiten número.
- `usuarios.codigo_activacion_hash` / `codigo_activacion_vence`: el admin crea al
  voluntario en `en_espera` y le entrega un código de un solo uso; el voluntario lo
  canjea en `POST /auth/activar`. Se guarda el hash, nunca el código.
- `usuarios.codigo_recuperacion_hash` / `codigo_recuperacion_vence`: código de un solo uso
  para "olvidé mi contraseña" (`POST /auth/recuperar` y `/auth/restablecer`), por SMS o correo.
- `organizaciones.telefono_contacto`: String(10) → String(15) para E.164 (+573001234567).
- `fn_auditoria()`: dejaba copiados en `auditoria` el `password_hash` y cualquier otro
  secreto de la fila. Ahora los quita antes de guardar.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# lpad corta los números de más de 3 cifras ('1000' → '100'), por eso el CASE.
FN_CODIGO_USUARIO = """
CREATE OR REPLACE FUNCTION fn_codigo_usuario()
RETURNS TEXT AS $$
DECLARE
  n BIGINT := nextval('usuarios_codigo_seq');
BEGIN
  RETURN 'USR-' || CASE WHEN n < 1000 THEN lpad(n::text, 3, '0') ELSE n::text END;
END;
$$ LANGUAGE plpgsql;
"""

# Columnas que nunca deben quedar en la auditoría. Quitar una clave que la tabla no
# tiene no hace nada, así que la misma función sirve para todas las tablas.
_SECRETOS = "ARRAY['password_hash', 'codigo_activacion_hash', 'codigo_recuperacion_hash']"


def _fn_auditoria(sin_secretos: bool) -> str:
    nuevo = f"(to_jsonb(NEW) - {_SECRETOS})" if sin_secretos else "to_jsonb(NEW)"
    viejo = f"(to_jsonb(OLD) - {_SECRETOS})" if sin_secretos else "to_jsonb(OLD)"
    return f"""
CREATE OR REPLACE FUNCTION fn_auditoria()
RETURNS TRIGGER AS $$
DECLARE
  v_usuario_id UUID;
BEGIN
  v_usuario_id := NULLIF(current_setting('app.usuario_id', true), '')::UUID;

  IF (TG_OP = 'INSERT') THEN
    INSERT INTO auditoria (id, tabla, registro_id, operacion, usuario_id, datos_nuevos)
    VALUES (gen_random_uuid(), TG_TABLE_NAME, NEW.id, 'INSERT', v_usuario_id, {nuevo});
    RETURN NEW;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO auditoria (id, tabla, registro_id, operacion, usuario_id, datos_anteriores, datos_nuevos)
    VALUES (gen_random_uuid(), TG_TABLE_NAME, NEW.id, 'UPDATE', v_usuario_id, {viejo}, {nuevo});
    RETURN NEW;
  ELSIF (TG_OP = 'DELETE') THEN
    INSERT INTO auditoria (id, tabla, registro_id, operacion, usuario_id, datos_anteriores)
    VALUES (gen_random_uuid(), TG_TABLE_NAME, OLD.id, 'DELETE', v_usuario_id, {viejo});
    RETURN OLD;
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(_fn_auditoria(sin_secretos=True))

    # --- usuarios.codigo (USR-001) ---
    op.execute("CREATE SEQUENCE usuarios_codigo_seq")
    op.execute(FN_CODIGO_USUARIO)
    # Las filas existentes reciben su código en orden de creación
    op.add_column("usuarios", sa.Column("codigo", sa.String(12), nullable=True))
    op.execute(
        "UPDATE usuarios u SET codigo = fn_codigo_usuario() "
        "FROM (SELECT id FROM usuarios ORDER BY creado_en, id) o WHERE u.id = o.id"
    )
    op.alter_column("usuarios", "codigo", nullable=False, server_default=sa.text("fn_codigo_usuario()"))
    op.create_unique_constraint("uq_usuarios_codigo", "usuarios", ["codigo"])

    # --- código de activación ---
    op.add_column("usuarios", sa.Column("codigo_activacion_hash", sa.String(64), nullable=True))
    op.add_column("usuarios", sa.Column("codigo_activacion_vence", sa.DateTime(timezone=True), nullable=True))

    # --- código para recuperar la contraseña ---
    op.add_column("usuarios", sa.Column("codigo_recuperacion_hash", sa.String(64), nullable=True))
    op.add_column("usuarios", sa.Column("codigo_recuperacion_vence", sa.DateTime(timezone=True), nullable=True))

    # --- organizaciones.telefono_contacto en E.164 ---
    op.alter_column(
        "organizaciones", "telefono_contacto", type_=sa.String(15), existing_type=sa.String(10), existing_nullable=True
    )


def downgrade() -> None:
    op.execute("UPDATE organizaciones SET telefono_contacto = right(telefono_contacto, 10) WHERE telefono_contacto IS NOT NULL")
    op.alter_column(
        "organizaciones", "telefono_contacto", type_=sa.String(10), existing_type=sa.String(15), existing_nullable=True
    )

    op.drop_column("usuarios", "codigo_recuperacion_vence")
    op.drop_column("usuarios", "codigo_recuperacion_hash")
    op.drop_column("usuarios", "codigo_activacion_vence")
    op.drop_column("usuarios", "codigo_activacion_hash")

    op.drop_constraint("uq_usuarios_codigo", "usuarios", type_="unique")
    op.drop_column("usuarios", "codigo")
    op.execute("DROP FUNCTION IF EXISTS fn_codigo_usuario()")
    op.execute("DROP SEQUENCE IF EXISTS usuarios_codigo_seq")

    op.execute(_fn_auditoria(sin_secretos=False))
