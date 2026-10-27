"""reportes: dirección, organización manual, verificación y evidencias (fotos y video)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-27

Dev A (A4).

- `reportes.tipo` sigue siendo texto: hay una lista sugerida (GET /reportes/tipos), pero el
  usuario puede escribir otro tipo de emergencia. Se le agrega un índice para filtrar.
- `direccion`, `organizacion_manual_id` (el super admin enruta a mano, como en solicitudes),
  `duplicado_de_id`, `verificado_en` y `motivo_rechazo`.
- Tabla nueva `evidencias_reporte`: varias fotos y videos por reporte. Reemplaza a
  `reportes.foto_url` (una sola foto); las que existan se copian antes de borrar la columna.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reportes", sa.Column("direccion", sa.String(50), nullable=True))
    op.add_column(
        "reportes",
        sa.Column("organizacion_manual_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizaciones.id"), nullable=True),
    )
    op.add_column(
        "reportes",
        sa.Column("duplicado_de_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reportes.id"), nullable=True),
    )
    op.add_column("reportes", sa.Column("verificado_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reportes", sa.Column("motivo_rechazo", sa.String(200), nullable=True))
    op.create_index("ix_reportes_tipo", "reportes", ["tipo"])

    op.create_table(
        "evidencias_reporte",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "reporte_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reportes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("ruta", sa.String(500), nullable=False),
        sa.Column("mime", sa.String(50), nullable=False),
        sa.Column("tamano_bytes", sa.Integer(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("tipo IN ('foto', 'video')", name="chk_evidencias_reporte_tipo"),
    )
    op.create_index("ix_evidencias_reporte_reporte_id", "evidencias_reporte", ["reporte_id"])

    # La única foto que podía tener cada reporte pasa a ser su primera evidencia
    op.execute(
        "INSERT INTO evidencias_reporte (reporte_id, tipo, ruta, mime) "
        "SELECT id, 'foto', foto_url, 'image/jpeg' FROM reportes WHERE foto_url IS NOT NULL"
    )
    op.drop_column("reportes", "foto_url")


def downgrade() -> None:
    op.add_column("reportes", sa.Column("foto_url", sa.String(500), nullable=True))
    op.execute(
        "UPDATE reportes r SET foto_url = e.ruta FROM ("
        "  SELECT DISTINCT ON (reporte_id) reporte_id, ruta FROM evidencias_reporte"
        "  WHERE tipo = 'foto' ORDER BY reporte_id, creado_en"
        ") e WHERE e.reporte_id = r.id"
    )
    op.drop_index("ix_evidencias_reporte_reporte_id", table_name="evidencias_reporte")
    op.drop_table("evidencias_reporte")

    op.drop_index("ix_reportes_tipo", table_name="reportes")
    op.drop_column("reportes", "motivo_rechazo")
    op.drop_column("reportes", "verificado_en")
    op.drop_column("reportes", "duplicado_de_id")
    op.drop_column("reportes", "organizacion_manual_id")
    op.drop_column("reportes", "direccion")
