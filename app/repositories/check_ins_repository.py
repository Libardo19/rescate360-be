from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.check_in import CheckIn
from app.models.enums import EstadoCheckIn, EstadoUsuario
from app.models.usuario import Usuario


def abrir_para_usuarios_en_circulo(
    db: Session,
    *,
    evento_sismico_id: UUID,
    zona,
    horas_ubicacion: int,
    vence_en: datetime,
) -> int:
    """Un check-in pendiente para cada usuario activo con ubicación reciente dentro de `zona`.

    Quien ya tiene uno pendiente no recibe otro (índice único parcial + ON CONFLICT DO NOTHING).
    """
    limite = datetime.now(UTC) - timedelta(hours=horas_ubicacion)
    usuarios = db.execute(
        select(Usuario.id, Usuario.ubicacion_actual).where(
            Usuario.estado == EstadoUsuario.ACTIVO,
            Usuario.ubicacion_actual.is_not(None),
            Usuario.ubicacion_actualizada_en >= limite,
            func.ST_Intersects(Usuario.ubicacion_actual, zona),
        )
    ).all()
    if not usuarios:
        return 0
    filas = [
        {
            "usuario_id": usuario_id,
            "evento_sismico_id": evento_sismico_id,
            "motivo": "sismo",
            "ultima_ubicacion": ubicacion,
            "vence_en": vence_en,
        }
        for usuario_id, ubicacion in usuarios
    ]
    consulta = (
        insert(CheckIn)
        .values(filas)
        .on_conflict_do_nothing(index_elements=[CheckIn.usuario_id], index_where=CheckIn.estado == EstadoCheckIn.PENDIENTE)
        .returning(CheckIn.id)
    )
    return len(db.scalars(consulta).all())


def crear(db: Session, **campos) -> CheckIn:
    check_in = CheckIn(**campos)
    db.add(check_in)
    db.flush()
    db.refresh(check_in)
    return check_in


def pendiente_de(db: Session, usuario_id: UUID) -> CheckIn | None:
    return db.scalar(
        select(CheckIn).where(CheckIn.usuario_id == usuario_id, CheckIn.estado == EstadoCheckIn.PENDIENTE)
    )


def bloquear(db: Session, check_in_id: UUID) -> CheckIn | None:
    consulta = (
        select(CheckIn).where(CheckIn.id == check_in_id).with_for_update().execution_options(populate_existing=True)
    )
    return db.scalars(consulta).one_or_none()


def actualizar(db: Session, check_in: CheckIn, **campos) -> CheckIn:
    for campo, valor in campos.items():
        setattr(check_in, campo, valor)
    db.flush()
    db.refresh(check_in)
    return check_in


def vencidos_bloqueados(db: Session, limite: int = 200) -> list[CheckIn]:
    """Pendientes cuyo plazo pasó. SKIP LOCKED: dos workers no procesan el mismo."""
    consulta = (
        select(CheckIn)
        .where(CheckIn.estado == EstadoCheckIn.PENDIENTE, CheckIn.vence_en <= datetime.now(UTC))
        .order_by(CheckIn.vence_en)
        .limit(limite)
        .with_for_update(skip_locked=True)
    )
    return list(db.scalars(consulta).all())


def listar_con_usuario(db: Session, evento_sismico_id: UUID | None) -> list[tuple[CheckIn, Usuario]]:
    consulta = select(CheckIn, Usuario).join(Usuario, Usuario.id == CheckIn.usuario_id).order_by(CheckIn.creado_en.desc())
    if evento_sismico_id is not None:
        consulta = consulta.where(CheckIn.evento_sismico_id == evento_sismico_id)
    return [(c, u) for c, u in db.execute(consulta).all()]
