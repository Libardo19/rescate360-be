"""reportes: clasificación de la IA (prioridad, confianza y razonamiento)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-27

Dev A (integración de la IA).

Los reportes se clasifican igual que las solicitudes: la IA sugiere prioridad y
organización (`organizacion_objetivo_id`, que ya existía) y el administrador puede
fijar una prioridad manual que prevalece. Reutiliza el tipo `prioridad_solicitud`.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# El tipo ya existe (lo creó la 0002 para solicitudes): no se vuelve a crear
_PRIORIDAD = postgresql.ENUM(
    "pendiente", "baja", "media", "alta", "critica", name="prioridad_solicitud", create_type=False
)


def upgrade() -> None:
    op.add_column(
        "reportes", sa.Column("prioridad_ia", _PRIORIDAD, nullable=False, server_default="pendiente")
    )
    op.add_column("reportes", sa.Column("prioridad_manual", _PRIORIDAD, nullable=True))
    op.add_column("reportes", sa.Column("confianza_ia", sa.Float(), nullable=True))
    op.add_column("reportes", sa.Column("razonamiento_ia", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("reportes", "razonamiento_ia")
    op.drop_column("reportes", "confianza_ia")
    op.drop_column("reportes", "prioridad_manual")
    op.drop_column("reportes", "prioridad_ia")
