from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import EstadoCasoPersona
from app.models.persona_desaparecida import PersonaDesaparecida
from app.utils.paginacion import Paginacion


def crear(db: Session, **campos) -> PersonaDesaparecida:
    persona = PersonaDesaparecida(**campos)
    db.add(persona)
    db.flush()
    return persona


def obtener_por_id(db: Session, persona_id: UUID) -> PersonaDesaparecida | None:
    return db.get(PersonaDesaparecida, persona_id)


def bloquear(db: Session, persona_id: UUID) -> PersonaDesaparecida | None:
    consulta = (
        select(PersonaDesaparecida)
        .where(PersonaDesaparecida.id == persona_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalars(consulta).one_or_none()


def listar(
    db: Session,
    pag: Paginacion,
    *,
    q: str | None = None,
    estado: EstadoCasoPersona | None = None,
    reportado_por: UUID | None = None,
) -> tuple[list[PersonaDesaparecida], int]:
    filtros = []
    if q:
        # Sin importar mayúsculas ni tildes: "maria" encuentra a "María"
        filtros.append(func.unaccent(PersonaDesaparecida.nombre).ilike(func.unaccent(f"%{q}%")))
    if estado is not None:
        filtros.append(PersonaDesaparecida.estado_caso == estado)
    if reportado_por is not None:
        filtros.append(PersonaDesaparecida.reportado_por == reportado_por)

    total = db.scalar(select(func.count()).select_from(PersonaDesaparecida).where(*filtros)) or 0
    consulta = (
        select(PersonaDesaparecida)
        .where(*filtros)
        # Primero los casos abiertos, luego los más recientes
        .order_by(
            (PersonaDesaparecida.estado_caso == EstadoCasoPersona.ENCONTRADO),
            PersonaDesaparecida.creado_en.desc(),
            PersonaDesaparecida.id,
        )
        .offset(pag.offset)
        .limit(pag.por_pagina)
    )
    return list(db.scalars(consulta).all()), total


def actualizar(db: Session, persona: PersonaDesaparecida, **campos) -> PersonaDesaparecida:
    for campo, valor in campos.items():
        setattr(persona, campo, valor)
    db.flush()
    db.refresh(persona)
    return persona
