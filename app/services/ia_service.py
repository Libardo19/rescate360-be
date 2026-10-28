"""Clasificación de casos: Gemini primero y, si no está disponible, las reglas.

La usan los jobs de clasificación de solicitudes y de reportes. Nunca deja un caso sin
clasificar por culpa de la IA: el sistema siempre sugiere prioridad y organización.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations import ia_client
from app.models.organizacion import Organizacion
from app.schemas.ia_schema import CasoIA, ClasificacionIA, OrganizacionIA
from app.services import clasificador_reglas


def organizaciones_activas(db: Session) -> list[OrganizacionIA]:
    filas = db.scalars(select(Organizacion).where(Organizacion.activa.is_(True)).order_by(Organizacion.nombre)).all()
    return [OrganizacionIA(id=o.id, nombre=o.nombre, tipo=o.tipo.value) for o in filas]


def clasificar(caso: CasoIA, organizaciones: list[OrganizacionIA]) -> ClasificacionIA:
    try:
        return ia_client.clasificar(caso, organizaciones)
    except ia_client.IAClasificacionError:
        return clasificador_reglas.clasificar(caso, organizaciones)
