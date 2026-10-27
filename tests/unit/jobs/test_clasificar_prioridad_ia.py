from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.jobs.eventos import clasificar_prioridad_ia
from app.models.enums import OrigenSolicitud, PrioridadSolicitud, TipoSolicitud


def test_ya_clasificada_no_llama_ia():
    solicitud = SimpleNamespace(
        id=uuid4(),
        origen=OrigenSolicitud.MANUAL,
        prioridad_ia=PrioridadSolicitud.ALTA,
        tipo=TipoSolicitud.MEDICA,
        descripcion="test",
        direccion=None,
    )
    db = MagicMock()
    with patch("app.jobs.eventos.clasificar_prioridad_ia.SessionLocal", return_value=db), \
         patch("app.jobs.eventos.clasificar_prioridad_ia.repo.obtener_para_clasificar", return_value=solicitud), \
         patch("app.jobs.eventos.clasificar_prioridad_ia.ia_client.clasificar_solicitud") as mock_ia:
        res = clasificar_prioridad_ia.clasificar_prioridad_ia.run(str(solicitud.id))
        assert res["status"] == "ya_clasificada"
        mock_ia.assert_not_called()


def test_sos_no_llama_ia():
    solicitud = SimpleNamespace(
        id=uuid4(),
        origen=OrigenSolicitud.SOS,
        prioridad_ia=PrioridadSolicitud.PENDIENTE,
        tipo=TipoSolicitud.RESCATE,
        descripcion="SOS",
        direccion=None,
    )
    db = MagicMock()
    with patch("app.jobs.eventos.clasificar_prioridad_ia.SessionLocal", return_value=db), \
         patch("app.jobs.eventos.clasificar_prioridad_ia.repo.obtener_para_clasificar", return_value=solicitud), \
         patch("app.jobs.eventos.clasificar_prioridad_ia.ia_client.clasificar_solicitud") as mock_ia:
        res = clasificar_prioridad_ia.clasificar_prioridad_ia.run(str(solicitud.id))
        assert res["status"] == "omitida_sos"
        mock_ia.assert_not_called()


def test_respuesta_valida_con_organizacion_existente_asigna():
    solicitud = SimpleNamespace(
        id=uuid4(),
        origen=OrigenSolicitud.MANUAL,
        prioridad_ia=PrioridadSolicitud.PENDIENTE,
        tipo=TipoSolicitud.MEDICA,
        descripcion="herido",
        direccion=None,
    )
    org_id = uuid4()
    org = SimpleNamespace(id=org_id, nombre="Cruz Roja", tipo=SimpleNamespace(value="cruz_roja"), activa=True)
    db = MagicMock()
    db.scalars.return_value.all.return_value = [org]

    resultado_mock = SimpleNamespace(prioridad=PrioridadSolicitud.ALTA, confianza=0.9, razonamiento="urgente", organizacion_sugerida="Cruz Roja")

    with patch("app.jobs.eventos.clasificar_prioridad_ia.SessionLocal", return_value=db), \
         patch("app.jobs.eventos.clasificar_prioridad_ia.repo.obtener_para_clasificar", return_value=solicitud), \
         patch("app.jobs.eventos.clasificar_prioridad_ia.ia_client.clasificar_solicitud", return_value=resultado_mock), \
         patch("app.jobs.eventos.clasificar_prioridad_ia.repo.aplicar_clasificacion_ia") as mock_aplicar:
        res = clasificar_prioridad_ia.clasificar_prioridad_ia.run(str(solicitud.id))
        assert res["status"] == "ok"
        assert res["prioridad_ia"] == "alta"
        assert res["organizacion_objetivo_id"] == str(org_id)
        mock_aplicar.assert_called_once()


def test_respuesta_valida_sin_match_deja_none():
    solicitud = SimpleNamespace(
        id=uuid4(),
        origen=OrigenSolicitud.MANUAL,
        prioridad_ia=PrioridadSolicitud.PENDIENTE,
        tipo=TipoSolicitud.OTRO,
        descripcion="otro caso",
        direccion=None,
    )
    org = SimpleNamespace(id=uuid4(), nombre="Bomberos", tipo=SimpleNamespace(value="bomberos"), activa=True)
    db = MagicMock()
    db.scalars.return_value.all.return_value = [org]

    resultado_mock = SimpleNamespace(prioridad=PrioridadSolicitud.MEDIA, confianza=0.7, razonamiento="revisar", organizacion_sugerida="ONG Desconocida")

    with patch("app.jobs.eventos.clasificar_prioridad_ia.SessionLocal", return_value=db), \
         patch("app.jobs.eventos.clasificar_prioridad_ia.repo.obtener_para_clasificar", return_value=solicitud), \
         patch("app.jobs.eventos.clasificar_prioridad_ia.ia_client.clasificar_solicitud", return_value=resultado_mock), \
         patch("app.jobs.eventos.clasificar_prioridad_ia.repo.aplicar_clasificacion_ia") as mock_aplicar:
        res = clasificar_prioridad_ia.clasificar_prioridad_ia.run(str(solicitud.id))
        assert res["status"] == "ok"
        assert res["organizacion_objetivo_id"] is None
        mock_aplicar.assert_called_once()


def test_fallo_ia_tras_reintentos_deja_pendiente():
    solicitud = SimpleNamespace(
        id=uuid4(),
        origen=OrigenSolicitud.MANUAL,
        prioridad_ia=PrioridadSolicitud.PENDIENTE,
        tipo=TipoSolicitud.MEDICA,
        descripcion="emergencia",
        direccion=None,
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = []

    task = clasificar_prioridad_ia.clasificar_prioridad_ia
    task.request.retries = task.max_retries

    with patch("app.jobs.eventos.clasificar_prioridad_ia.SessionLocal", return_value=db), \
         patch("app.jobs.eventos.clasificar_prioridad_ia.repo.obtener_para_clasificar", return_value=solicitud), \
         patch("app.jobs.eventos.clasificar_prioridad_ia.ia_client.clasificar_solicitud", side_effect=Exception("timeout")):
        res = task.run(str(solicitud.id))
        assert res["status"] == "fallback_pendiente"
