# Imagen de la API y de los workers de Celery.
# Python 3.12: todas las dependencias traen wheels, no hace falta compilar nada.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    HOME=/home/appuser

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends redis-server supervisor \
    && rm -rf /var/lib/apt/lists/*

# true en desarrollo (docker-compose), false en producción
ARG INSTALL_DEV=false

COPY requirements.txt requirements-dev.txt ./
RUN if [ "$INSTALL_DEV" = "true" ]; then pip install -r requirements-dev.txt; else pip install -r requirements.txt; fi \
    && pip check

RUN useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser . .
COPY docker/supervisord.conf /etc/supervisor/conf.d/rescate360.conf

EXPOSE 8000
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/rescate360.conf", "-n"]
