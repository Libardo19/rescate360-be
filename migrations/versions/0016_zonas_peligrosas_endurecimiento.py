"""zonas_peligrosas: CHECK del radio e índice para el mapa (pendientes de Sergio, §3.1 y §3.2)

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-29

Sale de `docs/PENDIENTES_ZONAS.md`. Pydantic ya valida `0 < radio_m <= 100000`; ahora la BD
también. El índice cubre lo que hace el mapa: filtrar por estado y ordenar por `actualizado_en`.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "chk_zonas_peligrosas_radio", "zonas_peligrosas", "radio_m > 0 AND radio_m <= 100000"
    )
    op.create_index(
        "ix_zonas_peligrosas_estado_actualizado", "zonas_peligrosas", ["estado", "actualizado_en"]
    )


def downgrade() -> None:
    op.drop_index("ix_zonas_peligrosas_estado_actualizado", table_name="zonas_peligrosas")
    op.drop_constraint("chk_zonas_peligrosas_radio", "zonas_peligrosas", type_="check")
