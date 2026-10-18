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
        usuario_id=usuario_id, tipo=tipo, aceptado=aceptado, version_politica=version_politica, ip=ip
    )
    db.add(consentimiento)
    db.flush()
    return consentimiento


def listar_de_usuario(db: Session, usuario_id: UUID) -> list[Consentimiento]:
    consulta = (
        select(Consentimiento)
        .where(Consentimiento.usuario_id == usuario_id)
        .order_by(Consentimiento.creado_en)
    )
    return list(db.scalars(consulta))
