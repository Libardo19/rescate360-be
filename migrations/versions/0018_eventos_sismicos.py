"""eventos_sismicos (sismos del USGS/SGC o simulados) y alertas creadas por el sistema

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-29

Dev A (B8, sismos).

- `eventos_sismicos`: un sismo por `id_externo` (el id del feed: el job es idempotente),
  epicentro con índice GiST, `radio_afectacion_m` calculado según la magnitud y la alerta
  que se creó para él.
- `alertas.creado_por` deja de ser obligatorio: la alerta de un sismo la crea el sistema.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eventos_sismicos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("id_externo", sa.String(60), nullable=False, unique=True),
        sa.Column("fuente", sa.String(10), nullable=False),
        sa.Column("magnitud", sa.Float(), nullable=False),
        sa.Column("profundidad_km", sa.Float(), nullable=True),
        sa.Column("lugar", sa.String(200), nullable=False),
        sa.Column("epicentro", Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("ocurrido_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("radio_afectacion_m", sa.Float(), nullable=False),
        sa.Column("alerta_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alertas.id"), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("fuente IN ('usgs', 'sgc', 'simulado')", name="chk_eventos_sismicos_fuente"),
        sa.CheckConstraint("magnitud >= 0 AND magnitud <= 10", name="chk_eventos_sismicos_magnitud"),
    )
    op.create_index("ix_eventos_sismicos_epicentro", "eventos_sismicos", ["epicentro"], postgresql_using="gist")
    op.create_index("ix_eventos_sismicos_ocurrido_en", "eventos_sismicos", ["ocurrido_en"])
    op.alter_column("alertas", "creado_por", nullable=True)


def downgrade() -> None:
    # Las alertas del sistema no tienen autor: se borran antes de volver a exigirlo
    op.execute("UPDATE eventos_sismicos SET alerta_id = NULL")
    op.execute("DELETE FROM alertas WHERE creado_por IS NULL")
    op.alter_column("alertas", "creado_por", nullable=False)
    op.drop_index("ix_eventos_sismicos_ocurrido_en", table_name="eventos_sismicos")
    op.drop_index("ix_eventos_sismicos_epicentro", table_name="eventos_sismicos")
    op.drop_table("eventos_sismicos")
