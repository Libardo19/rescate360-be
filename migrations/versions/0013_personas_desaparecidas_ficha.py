"""personas_desaparecidas: ficha completa del contrato, foto en el storage y reglas legales

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-28

Dev A (A5).

- Campos de la ficha que piden la app y el panel: edad, sexo, estatura, fecha y lugar en que
  se vio por última vez, señas particulares, vestimenta y el contacto de la familia.
- `es_menor`: si es menor de edad, la foto solo la ven quien reportó y los administradores
  (Ley 1098 de 2006). Se guarda para filtrar sin recalcular.
- `caracteristicas` pasa a `descripcion` y `foto_url` a `foto_ruta` (ahora es la ruta dentro
  del storage, igual que las evidencias de reportes).
- `ultima_ubicacion` deja de ser obligatoria: quien reporta casi nunca tiene las coordenadas
  del lugar; el lugar va como texto.
- Estados: siguen `buscando` / `encontrado` (decisión del 27-oct); se agrega `encontrado_en`.
- Extensión `unaccent`: la búsqueda por nombre no distingue tildes ("maria" encuentra a "María").
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLA = "personas_desaparecidas"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.alter_column(_TABLA, "caracteristicas", new_column_name="descripcion")
    op.alter_column(_TABLA, "foto_url", new_column_name="foto_ruta")
    op.alter_column(_TABLA, "ultima_ubicacion", nullable=True)

    op.add_column(_TABLA, sa.Column("edad", sa.SmallInteger(), nullable=True))
    op.add_column(_TABLA, sa.Column("sexo", sa.String(10), nullable=True))
    op.add_column(_TABLA, sa.Column("estatura", sa.String(10), nullable=True))
    op.add_column(_TABLA, sa.Column("fecha_vista", sa.Date(), nullable=True))
    op.add_column(_TABLA, sa.Column("lugar", sa.String(100), nullable=True))
    op.add_column(_TABLA, sa.Column("senas_particulares", sa.Text(), nullable=True))
    op.add_column(_TABLA, sa.Column("vestimenta", sa.Text(), nullable=True))
    op.add_column(_TABLA, sa.Column("contacto_nombre", sa.String(50), nullable=True))
    op.add_column(_TABLA, sa.Column("contacto_telefono", sa.String(15), nullable=True))
    op.add_column(_TABLA, sa.Column("es_menor", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column(_TABLA, sa.Column("encontrado_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        _TABLA,
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_check_constraint("chk_personas_desaparecidas_edad", _TABLA, "edad BETWEEN 0 AND 120")
    op.create_check_constraint(
        "chk_personas_desaparecidas_sexo", _TABLA, "sexo IN ('femenino', 'masculino', 'otro')"
    )
    op.create_index("ix_personas_desaparecidas_estado_caso", _TABLA, ["estado_caso"])
    op.create_index("ix_personas_desaparecidas_reportado_por", _TABLA, ["reportado_por"])


def downgrade() -> None:
    op.drop_index("ix_personas_desaparecidas_reportado_por", table_name=_TABLA)
    op.drop_index("ix_personas_desaparecidas_estado_caso", table_name=_TABLA)
    op.drop_constraint("chk_personas_desaparecidas_sexo", _TABLA, type_="check")
    op.drop_constraint("chk_personas_desaparecidas_edad", _TABLA, type_="check")
    for columna in (
        "actualizado_en",
        "encontrado_en",
        "es_menor",
        "contacto_telefono",
        "contacto_nombre",
        "vestimenta",
        "senas_particulares",
        "lugar",
        "fecha_vista",
        "estatura",
        "sexo",
        "edad",
    ):
        op.drop_column(_TABLA, columna)
    # Las fichas sin coordenadas no caben en el esquema viejo: se ubican en (0, 0)
    op.execute(f"UPDATE {_TABLA} SET ultima_ubicacion = ST_SetSRID(ST_MakePoint(0, 0), 4326) WHERE ultima_ubicacion IS NULL")
    op.alter_column(_TABLA, "ultima_ubicacion", nullable=False)
    op.alter_column(_TABLA, "foto_ruta", new_column_name="foto_url")
    op.alter_column(_TABLA, "descripcion", new_column_name="caracteristicas")
    op.execute("DROP EXTENSION IF EXISTS unaccent")
