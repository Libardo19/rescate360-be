"""\"actualizar centros_ayuda""\""

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-27 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('centros_ayuda', 'nombre',
               existing_type=sa.String(length=30),
               type_=sa.String(length=100),
               existing_nullable=False)
    op.add_column('centros_ayuda', sa.Column('estado', sa.String(length=30), server_default=sa.text("'activo'"), nullable=False))
    op.add_column('centros_ayuda', sa.Column('direccion', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('centros_ayuda', 'direccion')
    op.drop_column('centros_ayuda', 'estado')
    op.alter_column('centros_ayuda', 'nombre',
               existing_type=sa.String(length=100),
               type_=sa.String(length=30),
               existing_nullable=False)
