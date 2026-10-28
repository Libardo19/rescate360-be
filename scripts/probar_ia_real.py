"""Prueba explícita del API HTTP + Redis + worker + Gemini, sin mocks.

Ejecutar en local: docker compose exec -T api python -m scripts.probar_ia_real
Acepta --url https://... para probar también el túnel desde fuera del API.
Crea datos sintéticos identificados con PRUEBA IA; no usa cuentas personales.
La sesión del super admin existente se firma localmente, sin cambiar su clave.
"""

import argparse
import base64
import json
import secrets
import time
from uuid import uuid4

import httpx

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import crear_access_token
from app.jobs.eventos.clasificar_prioridad_ia import clasificar_prioridad_ia
from app.jobs.eventos.clasificar_reporte_ia import clasificar_reporte_ia
from app.models.enums import EstadoUsuario, RolUsuario
from app.models.usuario import Usuario
from sqlalchemy import select


def exigir(respuesta, status=200):
    if respuesta.status_code != status:
        # No imprimir cuerpos: el login contiene tokens y datos personales.
        raise RuntimeError(f"{respuesta.request.method} {respuesta.request.url.path}: HTTP {respuesta.status_code}")
    return respuesta.json()


def ejecutar(url):
    settings = get_settings()
    if settings.app_env != "local":
        raise RuntimeError("Esta prueba crea casos sintéticos: usar solo un entorno local/de pruebas")
    if not settings.gemini_api_key:
        raise RuntimeError("Falta GEMINI_API_KEY: el respaldo por reglas no cuenta como prueba real")
    marca = uuid4().hex[:12]
    informe = {"marca": marca, "api": url, "casos": []}
    with httpx.Client(base_url=url, timeout=40) as api:
        salud = exigir(api.get("/health/ready"))
        assert salud["status"] == "ok", salud
        # Solo dentro del contenedor local; el login público se prueba abajo.
        with SessionLocal() as db:
            admin = db.scalar(select(Usuario).where(
                Usuario.rol == RolUsuario.SUPER_ADMIN, Usuario.estado == EstadoUsuario.ACTIVO,
            ))
            if admin is None:
                raise RuntimeError("Primero ejecutar scripts.seed.crear_super_admin")
            ha = {"Authorization": f"Bearer {crear_access_token(admin)}"}
        orgs = exigir(api.get("/organizaciones", headers=ha, params={"por_pagina": 100}))["items"]
        for tipo in ("bomberos", "cruz_roja"):
            if not any(o["tipo"] == tipo and o["activa"] for o in orgs):
                orgs.append(exigir(api.post("/organizaciones", headers=ha, json={
                    "nombre": f"PRUEBA IA {tipo} {marca}", "tipo": tipo,
                }), 201))
        org_ids = {o["id"] for o in orgs if o["activa"]}

        email = f"prueba.ia.{marca}@example.com"
        password = secrets.token_urlsafe(24)
        registro = exigir(api.post("/auth/registro", json={
            "nombre": f"PRUEBA IA {marca}", "email": email, "password": password,
            "acepta_tratamiento_datos": True,
        }), 201)
        sesion = exigir(api.post("/auth/login", json={"email": email, "password": password}))
        assert sesion["usuario"]["id"] == registro["usuario"]["id"]
        hu = {"Authorization": f"Bearer {sesion['access_token']}"}
        perfil = exigir(api.get("/usuarios/me", headers=hu))
        assert perfil["email"] == email
        informe["registro_login_perfil"] = "ok"

        # Consultar resultados en el broker real sin reemplazar el encolado.
        # El API no devuelve task_id: el resultado Celery se localiza por el ID del caso.
        # Se compara con claves previas para no leer resultados de otros usuarios.
        import redis
        broker = redis.Redis.from_url(settings.redis_url)
        previas = set(broker.scan_iter("celery-task-meta-*"))
        solicitud = exigir(api.post("/solicitudes-ayuda", headers=hu, json={
            "tipo": "medica", "descripcion": f"PRUEBA IA {marca}: persona inconsciente, no respira.",
            "ubicacion": {"lat": 10.46, "lng": -73.25}, "direccion": "Escenario simulado",
        }), 201)
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aG1sAAAAASUVORK5CYII=")
        reporte = exigir(api.post("/reportes", headers=hu, data={
            "tipo": "incendio", "descripcion": f"PRUEBA IA {marca}: incendio con personas atrapadas adentro.",
            "lat": "10.46", "lng": "-73.25", "direccion": "Escenario simulado",
        }, files={"archivos": ("prueba.png", png, "image/png")}), 201)
        sos = exigir(api.post("/solicitudes-ayuda/sos", headers=hu,
                               json={"ubicacion": {"lat": 10.46, "lng": -73.25}}), 201)
        casos = [("solicitudes-ayuda", solicitud, "solicitud_id"),
                 ("reportes", reporte, "reporte_id"), ("solicitudes-ayuda", sos, "solicitud_id")]
        pendientes = {caso["id"] for _, caso, _ in casos}
        resultados = {}
        limite = time.monotonic() + 150
        while pendientes and time.monotonic() < limite:
            for clave in set(broker.scan_iter("celery-task-meta-*")) - previas:
                contenido = broker.get(clave)
                if not contenido:
                    continue
                meta = json.loads(contenido)
                resultado = meta.get("result")
                if meta.get("status") == "SUCCESS" and isinstance(resultado, dict):
                    identificador = resultado.get("solicitud_id", resultado.get("reporte_id"))
                    if identificador in pendientes:
                        resultados[identificador] = resultado
                        pendientes.remove(identificador)
            if pendientes:
                time.sleep(2)
        assert not pendientes, f"El worker no terminó: {sorted(pendientes)}"
        for recurso, caso, campo in casos:
            resultado = resultados[caso["id"]]
            detalle = exigir(api.get(f"/{recurso}/{caso['id']}", headers=hu))
            assert detalle["prioridad_ia"] in ("critica", "alta"), detalle["prioridad_ia"]
            assert detalle["organizacion_objetivo_id"] in org_ids
            assert detalle["razonamiento_ia"] and 0 <= detalle["confianza_ia"] <= 1
            if caso["id"] != sos["id"]:
                assert resultado["fuente"].startswith("gemini:"), resultado
            else:
                assert detalle["prioridad_ia"] == "critica"
            # Listados que consumen los paneles: el caso persistido es visible.
            listado = exigir(api.get(f"/{recurso}", headers=ha, params={"por_pagina": 100}))["items"]
            assert any(item["id"] == caso["id"] for item in listado)
            tarea = clasificar_reporte_ia if recurso == "reportes" else clasificar_prioridad_ia
            repetido = tarea.delay(caso["id"]).get(timeout=30)
            assert repetido["status"] in ("ya_clasificada", "ya_clasificado")
            informe["casos"].append({"recurso": recurso, "id": caso["id"],
                                     "prioridad": detalle["prioridad_ia"], "fuente": resultado["fuente"],
                                     "organizacion_id": detalle["organizacion_objetivo_id"],
                                     "idempotencia": "ok"})
        manual = exigir(api.patch(f"/reportes/{reporte['id']}/prioridad", headers=ha,
                                  json={"prioridad_manual": "media"}))
        assert manual["prioridad_manual"] == "media"
        assert manual["prioridad_ia"] == resultados[reporte["id"]]["prioridad_ia"]
        mapa = exigir(api.get("/mapa", headers=ha, params={"capas": "solicitudes,reportes"}))
        for _, caso, _ in casos:
            assert caso["id"] in json.dumps(mapa), f"Caso ausente del mapa: {caso['id']}"
        informe["prioridad_manual_y_mapa"] = "ok"
    print(json.dumps(informe, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    ejecutar(parser.parse_args().url)
