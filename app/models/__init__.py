"""Modelos de la aplicación.

Todo modelo debe importarse en este `__init__`: `migrations/env.py` hace
`import app.models` para llenar `Base.metadata`, y un modelo que no se importe
no aparece en el metadata. El síntoma es que `alembic --autogenerate` propone
`drop_table` de las tablas que no importó.
"""

from app.models.usuario import Usuario

__all__ = ["Usuario"]
