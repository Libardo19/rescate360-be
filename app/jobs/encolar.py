"""Encolar un job de Celery sin que un Redis caído rompa la petición del usuario.

Se llama DESPUÉS del commit, para que el worker encuentre la fila. Si no se puede encolar,
el caso queda como está (p. ej. "sin clasificar") y el administrador lo puede atender a mano.

    from app.jobs import encolar as cola
    cola.encolar(clasificar_reporte_ia, str(reporte.id))
"""

import logging

logger = logging.getLogger(__name__)


def encolar(tarea, *args) -> None:
    try:
        tarea.delay(*args)
    except Exception:  # Redis o el broker no disponibles
        logger.exception("No se pudo encolar %s%s", getattr(tarea, "name", tarea), args)
