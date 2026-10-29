"""contactos de emergencia (índice, borrado en cascada, fechas) y baja de usuarios (Ley 1581)

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-28

Dev A (A6).

- `contactos_emergencia`: índice por `usuario_id` (se listan siempre por usuario), borrado en
  cascada al borrar el usuario y `creado_en` para ordenarlos.
- `usuarios.eliminado_en`: cuando alguien pide borrar su cuenta, sus datos personales se
  anonimizan pero la fila se conserva (los casos que reportó siguen sirviendo). Esta fecha la
  distingue de una cuenta solo bloqueada.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("contactos_emergencia_usuario_id_fkey", "contactos_emergencia", type_="foreignkey")
    op.create_foreign_key(
        "contactos_emergencia_usuario_id_fkey",
        "contactos_emergencia",
        "usuarios",
        ["usuario_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_contactos_emergencia_usuario_id", "contactos_emergencia", ["usuario_id"])
    op.add_column(
        "contactos_emergencia",
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.add_column("usuarios", sa.Column("eliminado_en", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("usuarios", "eliminado_en")
    op.drop_column("contactos_emergencia", "creado_en")
    op.drop_index("ix_contactos_emergencia_usuario_id", table_name="contactos_emergencia")
    op.drop_constraint("contactos_emergencia_usuario_id_fkey", "contactos_emergencia", type_="foreignkey")
    op.create_foreign_key(
        "contactos_emergencia_usuario_id_fkey", "contactos_emergencia", "usuarios", ["usuario_id"], ["id"]
    )
