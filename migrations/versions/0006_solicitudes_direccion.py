"""solicitudes_ayuda: columna direccion

Escrita a mano (no autogenerate): los modelos de centros_ayuda, alertas, zonas_peligrosas y
donaciones aún no declaran organizacion_id y autogenerate propondría borrar esas columnas.

Revision ID: 0006
Revises: 0005
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("solicitudes_ayuda", sa.Column("direccion", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("solicitudes_ayuda", "direccion")
