"""HTTP de los derechos del titular: arma la respuesta y llama al service. Sin SQL ni reglas."""

from fastapi import Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.middlewares.auth_middleware import get_current_user
from app.models.usuario import Usuario
from app.schemas.datos_personales_schema import EliminarCuentaIn, MisDatosOut
from app.services import datos_personales_service as service


def exportar_mis_datos(usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)) -> MisDatosOut:
    return service.exportar(db, usuario)


def eliminar_mi_cuenta(
    datos: EliminarCuentaIn, usuario: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    service.eliminar_cuenta(db, usuario, datos)
    return Response(status_code=204)
