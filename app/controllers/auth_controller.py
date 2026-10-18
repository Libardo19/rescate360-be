from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth_schema import LoginIn, RefreshIn, RegistroIn, SesionOut
from app.services import auth_service


def registrar(datos: RegistroIn, request: Request, db: Session = Depends(get_db)) -> SesionOut:
    ip = request.client.host if request.client else None
    return auth_service.registrar(db, datos, ip)


def login(datos: LoginIn, db: Session = Depends(get_db)) -> SesionOut:
    return auth_service.login(db, datos)


def refrescar(datos: RefreshIn, db: Session = Depends(get_db)) -> SesionOut:
    return auth_service.refrescar(db, datos.refresh_token)
