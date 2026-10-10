"""índices GIST, función/triggers de auditoría, organizacion_id en
centros_ayuda, alertas, zonas_peligrosas y donaciones.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


# (tabla, columna, nombre_del_indice)
SPATIAL_INDICES = [
    ("usuarios", "ubicacion_actual", "ix_usuarios_ubicacion_actual"),
    ("organizaciones", "zona_cobertura", "ix_organizaciones_zona_cobertura"),
    ("reportes", "ubicacion", "ix_reportes_ubicacion"),
    ("personas_desaparecidas", "ultima_ubicacion", "ix_personas_desaparecidas_ultima_ubicacion"),
    ("solicitudes_ayuda", "ubicacion", "ix_solicitudes_ayuda_ubicacion"),
    ("centros_ayuda", "ubicacion", "ix_centros_ayuda_ubicacion"),
    ("alertas", "zona_afectada", "ix_alertas_zona_afectada"),
    ("zonas_peligrosas", "area", "ix_zonas_peligrosas_area"),
    ("cola_alertas_offline", "ubicacion", "ix_cola_alertas_offline_ubicacion"),
    # perfiles_voluntario.zona_cobertura 
]

# Tablas a las que les falta organizacion_id directo (problema #8)
ORGANIZACION_FK_TABLAS = ["centros_ayuda", "alertas", "zonas_peligrosas", "donaciones"]

# Tablas que llevan trigger de auditoría
AUDITORIA_TABLAS = [
    "usuarios",
    "reportes",
    "solicitudes_ayuda",
    "personas_desaparecidas",
    "zonas_peligrosas",
    "alertas",
]

FN_AUDITORIA_SQL = """
CREATE OR REPLACE FUNCTION fn_auditoria()
RETURNS TRIGGER AS $$
DECLARE
  v_usuario_id UUID;
BEGIN
  -- Lo setea audit_middleware.py de Dev A con SET LOCAL app.usuario_id
  v_usuario_id := current_setting('app.usuario_id', true)::UUID;

  IF (TG_OP = 'INSERT') THEN
    INSERT INTO auditoria (id, tabla, registro_id, operacion, usuario_id, datos_nuevos)
    VALUES (gen_random_uuid(), TG_TABLE_NAME, NEW.id, 'INSERT', v_usuario_id, to_jsonb(NEW));
    RETURN NEW;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO auditoria (id, tabla, registro_id, operacion, usuario_id, datos_anteriores, datos_nuevos)
    VALUES (gen_random_uuid(), TG_TABLE_NAME, NEW.id, 'UPDATE', v_usuario_id, to_jsonb(OLD), to_jsonb(NEW));
    RETURN NEW;
  ELSIF (TG_OP = 'DELETE') THEN
    INSERT INTO auditoria (id, tabla, registro_id, operacion, usuario_id, datos_anteriores)
    VALUES (gen_random_uuid(), TG_TABLE_NAME, OLD.id, 'DELETE', v_usuario_id, to_jsonb(OLD));
    RETURN OLD;
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    # 1) organizacion_id en las 4 tablas que les faltaba (problema #8)
    for tabla in ORGANIZACION_FK_TABLAS:
        op.add_column(
            tabla,
            sa.Column(
                "organizacion_id",
                UUID(as_uuid=True),
                sa.ForeignKey("organizaciones.id"),
                nullable=True,
            ),
        )
        op.create_index(f"ix_{tabla}_organizacion_id", tabla, ["organizacion_id"])

    # índice que también faltaba sobre usuarios.organizacion_id
    op.create_index("ix_usuarios_organizacion_id", "usuarios", ["organizacion_id"])

    # 2) índices de consulta frecuente (no espaciales)
    op.create_index("ix_reportes_estado", "reportes", ["estado"])
    op.create_index(
        "ix_solicitudes_ayuda_estado_prioridad",
        "solicitudes_ayuda",
        ["estado", "prioridad_ia"],
    )

    # 3) índices GIST en columnas geográficas (problema #2)
    for tabla, columna, nombre_indice in SPATIAL_INDICES:
        op.create_index(
            nombre_indice,
            tabla,
            [columna],
            unique=False,
            postgresql_using="gist",
        )

    # 4) función y triggers de auditoría (problema #3)
    op.execute(FN_AUDITORIA_SQL)
    for tabla in AUDITORIA_TABLAS:
        op.execute(
            f"""
            CREATE TRIGGER trg_auditoria_{tabla}
            AFTER INSERT OR UPDATE OR DELETE ON {tabla}
            FOR EACH ROW EXECUTE FUNCTION fn_auditoria();
            """
        )


def downgrade() -> None:
    for tabla in AUDITORIA_TABLAS:
        op.execute(f"DROP TRIGGER IF EXISTS trg_auditoria_{tabla} ON {tabla};")
    op.execute("DROP FUNCTION IF EXISTS fn_auditoria() CASCADE;")

    for tabla, columna, nombre_indice in SPATIAL_INDICES:
        op.drop_index(nombre_indice, table_name=tabla)

    op.drop_index("ix_solicitudes_ayuda_estado_prioridad", table_name="solicitudes_ayuda")
    op.drop_index("ix_reportes_estado", table_name="reportes")
    op.drop_index("ix_usuarios_organizacion_id", table_name="usuarios")

    for tabla in ORGANIZACION_FK_TABLAS:
        op.drop_index(f"ix_{tabla}_organizacion_id", table_name=tabla)
        op.drop_column(tabla, "organizacion_id")