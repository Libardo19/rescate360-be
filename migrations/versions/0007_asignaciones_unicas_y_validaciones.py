"""asignaciones unicas y validaciones

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-26 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_asignacion_activa_solicitud
        ON asignaciones (voluntario_id, solicitud_id)
        WHERE solicitud_id IS NOT NULL AND estado_asignacion = 'activa';
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_asignacion_activa_reporte
        ON asignaciones (voluntario_id, reporte_id)
        WHERE reporte_id IS NOT NULL AND estado_asignacion = 'activa';
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_asignacion_activa_reporte;")
    op.execute("DROP INDEX IF EXISTS uq_asignacion_activa_solicitud;")
