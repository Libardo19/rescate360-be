"""zonas_peligrosas: nombre, nivel, descripción, círculo (centro + radio) y nuevos estados

Escrita a mano (no autogenerate), como la 0006 y la 0007.

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"  # <-- pon aquí lo que muestre "alembic heads" después del git pull
branch_labels = None
depends_on = None

# create_type=False: el tipo se crea a mano abajo, una sola vez
NIVEL = postgresql.ENUM("bajo", "medio", "alto", name="nivel_zona", create_type=False)


def upgrade() -> None:
    # --- ZONAS PELIGROSAS -------------------------------------------------------------------

    # 1) Estados: resuelta -> inactiva (las filas existentes se conservan) y el nuevo en_monitoreo.
    #    ADD VALUE dentro de la transacción está permitido desde PostgreSQL 12; el valor nuevo no se
    #    usa en esta misma migración, que es la condición.
    op.execute("ALTER TYPE estado_zona RENAME VALUE 'resuelta' TO 'inactiva'")
    op.execute("ALTER TYPE estado_zona ADD VALUE IF NOT EXISTS 'en_monitoreo' BEFORE 'inactiva'")

    # 2) Nivel
    postgresql.ENUM("bajo", "medio", "alto", name="nivel_zona").create(op.get_bind(), checkfirst=True)
    op.add_column("zonas_peligrosas", sa.Column("nivel", NIVEL, nullable=False, server_default="medio"))

    # 3) Texto: nombre (se rellena con el tipo de riesgo en las filas que ya existan), descripción
    #    y tipo_riesgo más largo (es texto libre)
    op.add_column("zonas_peligrosas", sa.Column("nombre", sa.String(length=100), nullable=True))
    op.execute("UPDATE zonas_peligrosas SET nombre = tipo_riesgo")
    op.alter_column("zonas_peligrosas", "nombre", nullable=False)
    op.add_column("zonas_peligrosas", sa.Column("descripcion", sa.Text(), nullable=True))
    op.alter_column(
        "zonas_peligrosas",
        "tipo_riesgo",
        existing_type=sa.String(length=30),
        type_=sa.String(length=60),
        existing_nullable=False,
    )

    # 4) Círculo: centro y radio nacen NULL para rellenar las filas existentes y luego pasan a NOT NULL
    op.add_column(
        "zonas_peligrosas",
        sa.Column("centro", Geometry(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True),
    )
    op.add_column("zonas_peligrosas", sa.Column("radio_m", sa.Float(), nullable=True))
    op.execute(
        """
        UPDATE zonas_peligrosas
        SET centro = ST_Centroid(area),
            radio_m = ROUND(
                ST_Distance(
                    ST_Centroid(area)::geography,
                    ST_PointN(ST_ExteriorRing(area), 1)::geography
                )::numeric
            )
        """
    )
    op.alter_column("zonas_peligrosas", "centro", nullable=False)
    op.alter_column("zonas_peligrosas", "radio_m", nullable=False)

    # --- DONACIONES: pendiente --------------------------------------------------------------
    # DONACIONES: pendiente. Cuando se defina el modelo de donaciones y campañas, sus cambios
    # (columnas nuevas, tabla campanas, enums) se agregan aquí, y su reverso en downgrade().


def downgrade() -> None:
    # --- DONACIONES: pendiente (agregar aquí el reverso, en orden inverso al upgrade) -------

    # --- ZONAS PELIGROSAS -------------------------------------------------------------------
    # tipo_riesgo vuelve a 30 caracteres: se recorta lo que no quepa
    op.alter_column(
        "zonas_peligrosas",
        "tipo_riesgo",
        existing_type=sa.String(length=60),
        type_=sa.String(length=30),
        existing_nullable=False,
        postgresql_using="left(tipo_riesgo, 30)",
    )
    for columna in ("radio_m", "centro", "descripcion", "nombre", "nivel"):
        op.drop_column("zonas_peligrosas", columna)
    postgresql.ENUM(name="nivel_zona").drop(op.get_bind(), checkfirst=True)

    # Un valor de enum no se puede quitar: se crea el tipo viejo y se convierte la columna.
    # inactiva -> resuelta; activa y en_monitoreo -> activa.
    # El DEFAULT se suelta ANTES de cambiar el tipo (si no, Postgres no puede convertirlo) y se repone después.
    op.execute("ALTER TABLE zonas_peligrosas ALTER COLUMN estado DROP DEFAULT")
    op.execute("ALTER TYPE estado_zona RENAME TO estado_zona_nuevo")
    op.execute("CREATE TYPE estado_zona AS ENUM ('activa', 'resuelta')")
    op.execute(
        """
        ALTER TABLE zonas_peligrosas
        ALTER COLUMN estado TYPE estado_zona
        USING (CASE estado::text WHEN 'inactiva' THEN 'resuelta' ELSE 'activa' END)::estado_zona
        """
    )
    op.execute("ALTER TABLE zonas_peligrosas ALTER COLUMN estado SET DEFAULT 'activa'")
    op.execute("DROP TYPE estado_zona_nuevo")
