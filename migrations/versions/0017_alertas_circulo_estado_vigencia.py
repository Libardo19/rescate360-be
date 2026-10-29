"""alertas: título, nivel, círculo (centro + radio), estado, vigencia y origen (B3)

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-29

Dev A (B3, que pasó a Libardo).

- La alerta se dibuja como círculo, igual que las zonas: `centro` + `radio_m`, y `zona_afectada`
  (POLYGON, ya existía) queda como el polígono derivado para las consultas "dentro de".
- `nivel` bajo/medio/alto (la app lo pinta como info/warning/danger) y `estado`
  activa/expirada/cancelada; `expira_en` la vence sola (job expirar_alertas).
- `origen`: `manual` (la crea un administrador) o `sismo` (la crea el job de sismos).
- Las filas que ya existan toman el centro y el radio de su polígono y vencen a las 24 h.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NIVEL = postgresql.ENUM("bajo", "medio", "alto", name="nivel_alerta", create_type=False)
ESTADO = postgresql.ENUM("activa", "expirada", "cancelada", name="estado_alerta", create_type=False)


def upgrade() -> None:
    NIVEL.create(op.get_bind(), checkfirst=True)
    ESTADO.create(op.get_bind(), checkfirst=True)

    op.add_column("alertas", sa.Column("titulo", sa.String(100), nullable=True))
    op.add_column("alertas", sa.Column("nivel", NIVEL, nullable=False, server_default="medio"))
    op.add_column("alertas", sa.Column("estado", ESTADO, nullable=False, server_default="activa"))
    op.add_column("alertas", sa.Column("origen", sa.String(10), nullable=False, server_default="manual"))
    op.add_column(
        "alertas", sa.Column("centro", Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True)
    )
    op.add_column("alertas", sa.Column("radio_m", sa.Float(), nullable=True))
    op.add_column("alertas", sa.Column("expira_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "alertas",
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute(
        """
        UPDATE alertas
        SET titulo = tipo,
            centro = ST_Centroid(zona_afectada),
            radio_m = GREATEST(ROUND(ST_Distance(
                ST_Centroid(zona_afectada)::geography,
                ST_PointN(ST_ExteriorRing(zona_afectada), 1)::geography
            )::numeric), 1),
            expira_en = creado_en + interval '24 hours'
        """
    )
    for columna in ("titulo", "centro", "radio_m", "expira_en"):
        op.alter_column("alertas", columna, nullable=False)

    op.create_check_constraint("chk_alertas_radio", "alertas", "radio_m > 0 AND radio_m <= 300000")
    op.create_check_constraint("chk_alertas_origen", "alertas", "origen IN ('manual', 'sismo')")
    op.create_index("ix_alertas_estado_expira_en", "alertas", ["estado", "expira_en"])


def downgrade() -> None:
    op.drop_index("ix_alertas_estado_expira_en", table_name="alertas")
    op.drop_constraint("chk_alertas_origen", "alertas", type_="check")
    op.drop_constraint("chk_alertas_radio", "alertas", type_="check")
    for columna in ("actualizado_en", "expira_en", "radio_m", "centro", "origen", "estado", "nivel", "titulo"):
        op.drop_column("alertas", columna)
    ESTADO.drop(op.get_bind(), checkfirst=True)
    NIVEL.drop(op.get_bind(), checkfirst=True)
