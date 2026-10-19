from logging.config import fileConfig

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  registra los modelos en Base.metadata
from app.core.config import get_settings
from app.core.database import Base

config = context.config
# Las pruebas fijan su propia URL (BD _test); si no viene, se usa DATABASE_URL.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # Ignora tablas que no son nuestras (spatial_ref_sys de PostGIS, etc.)
    # para que --autogenerate no proponga borrarlas.
    if type_ == "table" and reflected and compare_to is None:
        return False
    return alembic_helpers.include_object(obj, name, type_, reflected, compare_to)


def _configure(**kwargs):
    context.configure(
        target_metadata=target_metadata,
        include_object=include_object,
        process_revision_directives=alembic_helpers.writer,
        render_item=alembic_helpers.render_item,
        compare_type=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    _configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
