"""tipo de solicitud, estados pendiente/en_proceso/atendida/cancelada, origen sos

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Renombrar valores existentes de estado_solicitud y agregar 'cancelada'
    op.execute("ALTER TYPE estado_solicitud RENAME VALUE 'en_atencion' TO 'en_proceso'")
    op.execute("ALTER TYPE estado_solicitud RENAME VALUE 'resuelta' TO 'atendida'")
    op.execute("ALTER TYPE estado_solicitud ADD VALUE IF NOT EXISTS 'cancelada'")

    # 2) Agregar 'sos' a origen_solicitud
    op.execute("ALTER TYPE origen_solicitud ADD VALUE IF NOT EXISTS 'sos'")

    # 3) Crear el nuevo tipo tipo_solicitud
    tipo_solicitud = sa.Enum(
        "medica", "alimentaria", "refugio", "rescate", "ropa", "otro",
        name="tipo_solicitud",
    )
    tipo_solicitud.create(op.get_bind())

    # 4) Agregar la columna tipo a solicitudes_ayuda
    op.add_column(
        "solicitudes_ayuda",
        sa.Column(
            "tipo",
            tipo_solicitud,
            nullable=False,
            server_default="otro",
        ),
    )


def downgrade() -> None:
    # Revertir la columna tipo
    op.drop_column("solicitudes_ayuda", "tipo")
    op.execute("DROP TYPE IF EXISTS tipo_solicitud")

    # Revertir origen_solicitud (Postgres no permite quitar un valor de un
    # ENUM directamente: se recrea el tipo sin 'sos')
    op.execute("ALTER TYPE origen_solicitud RENAME TO origen_solicitud_old")
    op.execute("CREATE TYPE origen_solicitud AS ENUM ('manual', 'acelerometro')")
    op.execute(
        "ALTER TABLE solicitudes_ayuda "
        "ALTER COLUMN origen TYPE origen_solicitud "
        "USING origen::text::origen_solicitud"
    )
    op.execute("DROP TYPE origen_solicitud_old")

    # Revertir estado_solicitud (mismo truco: recrear el tipo viejo)
    op.execute("ALTER TYPE estado_solicitud RENAME TO estado_solicitud_old")
    op.execute("CREATE TYPE estado_solicitud AS ENUM ('pendiente', 'en_atencion', 'resuelta')")
    op.execute(
        "ALTER TABLE solicitudes_ayuda "
        "ALTER COLUMN estado TYPE estado_solicitud "
        "USING estado::text::estado_solicitud"
    )
    op.execute("DROP TYPE estado_solicitud_old")
