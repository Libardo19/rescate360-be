"""Regresión: Uvicorn debe publicar en el mismo Redis que el worker.

Un proceso limpio evita que los imports de pytest oculten la app por defecto
de Celery (AMQP), incluida la resolución desde un hilo de FastAPI.
"""

import subprocess
import sys


def test_api_y_sus_hilos_publican_en_el_broker_configurado():
    codigo = '''
from concurrent.futures import ThreadPoolExecutor
from app.main import app
from app.core.config import get_settings
from app.jobs.eventos.clasificar_prioridad_ia import clasificar_prioridad_ia
from app.jobs.eventos.clasificar_reporte_ia import clasificar_reporte_ia

def verificar():
    for tarea in (clasificar_prioridad_ia, clasificar_reporte_ia):
        assert tarea.app.main == "rescate360", tarea.app.main
        assert tarea.app.conf.broker_url == get_settings().redis_url
        with tarea.app.connection_for_write() as conexion:
            assert conexion.transport.driver_type == "redis"

verificar()
with ThreadPoolExecutor(max_workers=1) as pool:
    pool.submit(verificar).result()
'''
    resultado = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=30)
    assert resultado.returncode == 0, resultado.stderr
