"""reportes: estado "atendido" y fecha de cierre de las asignaciones

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-29

Cuando el voluntario finaliza su asignación de un reporte, el reporte pasa a `atendido` (las
solicitudes ya pasaban a `atendida`). Así deja de salir como activo en la app, el mapa y el panel.
`asignaciones.cerrada_en` guarda cuándo se finalizó o canceló, para mostrar "finalizó a las 10:42".

Solo agrega: un valor al enum y una columna nullable. No toca datos existentes.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE estado_reporte ADD VALUE IF NOT EXISTS 'atendido'")
    op.add_column("asignaciones", sa.Column("cerrada_en", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("asignaciones", "cerrada_en")
    # Un valor de enum no se puede quitar: los reportes atendidos vuelven a verificado
    op.execute("UPDATE reportes SET estado = 'verificado' WHERE estado = 'atendido'")
