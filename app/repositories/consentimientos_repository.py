from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.consentimiento import Consentimiento
from app.models.enums import TipoConsentimiento


def registrar(
    db: Session,
    usuario_id: UUID,
    tipo: TipoConsentimiento,
    aceptado: bool,
    version_politica: str,
    ip: str | None,
) -> Consentimiento:
    consentimiento = Consentimiento(
        usuario_id=usuario_id, tipo=tipo, aceptado=aceptado, version_politica=version_politica, ip=ip,
        # Hora real y no now() de Postgres (que es el inicio de la transacción): así dos decisiones
        # seguidas no empatan y vigente() siempre toma la última.
        creado_en=datetime.now(UTC),
    )
    db.add(consentimiento)
    db.flush()
    return consentimiento


def vigente(db: Session, usuario_id: UUID, tipo: TipoConsentimiento) -> Consentimiento | None:
    """La última decisión del usuario sobre ese tipo (las filas nunca se borran: manda la más reciente)."""
    consulta = (
        select(Consentimiento)
        .where(Consentimiento.usuario_id == usuario_id, Consentimiento.tipo == tipo)
        .order_by(Consentimiento.creado_en.desc(), Consentimiento.id.desc())
        .limit(1)
    )
    return db.scalar(consulta)


def listar_de_usuario(db: Session, usuario_id: UUID) -> list[Consentimiento]:
    consulta = (
        select(Consentimiento)
        .where(Consentimiento.usuario_id == usuario_id)
        .order_by(Consentimiento.creado_en)
    )
    return list(db.scalars(consulta))
