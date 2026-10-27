"""usuarios: ubicacion_actualizada_en

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-26

Dev A. Cuándo se guardó `ubicacion_actual` por última vez. Sirve para que
`notificar_alerta_zona` descarte ubicaciones viejas y para que
`limpiar_datos_retencion` borre las que pasen de RETENCION_UBICACIONES_DIAS.

Va después de la 0007 de asignaciones (Dev B), que entra a develop con
`fix/ajustes-migraciones-libardo`.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("ubicacion_actualizada_en", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("usuarios", "ubicacion_actualizada_en")
