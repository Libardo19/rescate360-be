"""campañas de donación y registro de donaciones (B5)

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-29

Dev A (B5, que pasó a Libardo).

- `campanas`: lo que una organización necesita reunir (meta, unidad, fecha de cierre). El
  ciudadano las ve en la app; lo recaudado se calcula sumando sus donaciones.
- `donaciones` pasa de inventario de un centro a registro de donaciones que lleva la
  organización: categoría, descripción, cantidad y unidad, monto (solo dinero), estado y la
  campaña o el centro al que van. **La app no cobra nada**: el pago se coordina por fuera.
- `tipo` se renombra a `categoria` (alimentos, ropa, medicamentos, agua, dinero, otro).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESTADO = postgresql.ENUM("recibida", "en_proceso", "entregada", name="estado_donacion", create_type=False)
CATEGORIAS = "('alimentos', 'ropa', 'medicamentos', 'agua', 'dinero', 'otro')"


def upgrade() -> None:
    op.create_table(
        "campanas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("titulo", sa.String(100), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("categoria", sa.String(15), nullable=False),
        sa.Column("meta", sa.Float(), nullable=False),
        sa.Column("unidad", sa.String(20), nullable=False),
        sa.Column("fecha_fin", sa.Date(), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("organizacion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizaciones.id"), nullable=True),
        sa.Column("creado_por", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("meta > 0", name="chk_campanas_meta"),
        sa.CheckConstraint(f"categoria IN {CATEGORIAS}", name="chk_campanas_categoria"),
    )
    op.create_index("ix_campanas_organizacion_id", "campanas", ["organizacion_id"])

    ESTADO.create(op.get_bind(), checkfirst=True)
    op.alter_column("donaciones", "tipo", new_column_name="categoria", type_=sa.String(15), existing_type=sa.String(25))
    op.alter_column("donaciones", "centro_id", nullable=True)
    op.add_column("donaciones", sa.Column("descripcion", sa.String(200), nullable=True))
    op.add_column("donaciones", sa.Column("monto", sa.Float(), nullable=True))
    op.add_column("donaciones", sa.Column("estado", ESTADO, nullable=False, server_default="recibida"))
    op.add_column(
        "donaciones",
        sa.Column("campana_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campanas.id"), nullable=True),
    )
    op.add_column(
        "donaciones",
        sa.Column("registrada_por", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id"), nullable=True),
    )
    op.add_column(
        "donaciones",
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.execute(f"UPDATE donaciones SET categoria = 'otro' WHERE categoria NOT IN {CATEGORIAS}")
    op.create_check_constraint("chk_donaciones_categoria", "donaciones", f"categoria IN {CATEGORIAS}")
    op.create_check_constraint("chk_donaciones_cantidad", "donaciones", "cantidad > 0")
    op.create_index("ix_donaciones_campana_id", "donaciones", ["campana_id"])


def downgrade() -> None:
    op.drop_index("ix_donaciones_campana_id", table_name="donaciones")
    op.drop_constraint("chk_donaciones_cantidad", "donaciones", type_="check")
    op.drop_constraint("chk_donaciones_categoria", "donaciones", type_="check")
    for columna in ("creado_en", "registrada_por", "campana_id", "estado", "monto", "descripcion"):
        op.drop_column("donaciones", columna)
    # Las donaciones sin centro no caben en el esquema viejo
    op.execute("DELETE FROM donaciones WHERE centro_id IS NULL")
    op.alter_column("donaciones", "centro_id", nullable=False)
    op.alter_column("donaciones", "categoria", new_column_name="tipo", type_=sa.String(25), existing_type=sa.String(15))
    ESTADO.drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_campanas_organizacion_id", table_name="campanas")
    op.drop_table("campanas")
