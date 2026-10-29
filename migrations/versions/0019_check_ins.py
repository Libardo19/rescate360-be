"""check_ins: el "¿Estás bien?" con vencimiento (después de un sismo o en modo emergencia)

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-29

Dev A.

- Un check-in pregunta a la persona si está bien. Si no responde antes de `vence_en`, queda
  `sin_respuesta` y se avisa a sus contactos de emergencia con su última ubicación.
- Si responde `necesito_ayuda`, se crea un SOS (`solicitud_id`).
- Una persona tiene como máximo un check-in pendiente a la vez (índice único parcial).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESTADO = postgresql.ENUM(
    "pendiente", "a_salvo", "necesito_ayuda", "sin_respuesta", name="estado_check_in", create_type=False
)


def upgrade() -> None:
    ESTADO.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "check_ins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "evento_sismico_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("eventos_sismicos.id"), nullable=True
        ),
        sa.Column("motivo", sa.String(10), nullable=False),
        sa.Column("estado", ESTADO, nullable=False, server_default="pendiente"),
        sa.Column(
            "ultima_ubicacion", Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True
        ),
        sa.Column("vence_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("respondido_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "solicitud_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("solicitudes_ayuda.id"), nullable=True
        ),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("motivo IN ('sismo', 'manual')", name="chk_check_ins_motivo"),
    )
    op.create_index(
        "uq_check_in_pendiente_por_usuario",
        "check_ins",
        ["usuario_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'pendiente'"),
    )
    op.create_index("ix_check_ins_evento_sismico_id", "check_ins", ["evento_sismico_id"])
    op.create_index("ix_check_ins_estado_vence_en", "check_ins", ["estado", "vence_en"])


def downgrade() -> None:
    op.drop_index("ix_check_ins_estado_vence_en", table_name="check_ins")
    op.drop_index("ix_check_ins_evento_sismico_id", table_name="check_ins")
    op.drop_index("uq_check_in_pendiente_por_usuario", table_name="check_ins")
    op.drop_table("check_ins")
    ESTADO.drop(op.get_bind(), checkfirst=True)
