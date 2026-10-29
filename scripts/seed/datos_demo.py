"""Datos de demostración en Valledupar: organizaciones, un usuario de cada rol, casos y la guía.

    docker compose exec api python -m scripts.seed.datos_demo

La contraseña de los usuarios de demo sale del .env (SEED_DEMO_PASSWORD), nunca del repo.
Es idempotente: lo que ya existe (por correo o por nombre) no se vuelve a crear. El super admin
se crea aparte con scripts.seed.crear_super_admin.
"""

import sys
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.alerta import Alerta
from app.models.campana import Campana
from app.models.centro_ayuda import CentroAyuda
from app.models.enums import (
    EstadoUsuario,
    EstadoZona,
    NivelAlerta,
    NivelZona,
    PrioridadSolicitud,
    RolUsuario,
    TipoOrganizacion,
    TipoSolicitud,
)
from app.models.organizacion import Organizacion
from app.models.persona_desaparecida import PersonaDesaparecida
from app.models.reporte import Reporte
from app.models.solicitud_ayuda import SolicitudAyuda
from app.models.usuario import Usuario
from app.models.zona_peligrosa import ZonaPeligrosa
from app.services import guia_emergencia_service
from app.utils.geo import circulo_a_poligono, punto_desde_latlng

DOMINIO = "demo.rescate360.co"
CENTRO = (10.4631, -73.2532)  # Plaza Alfonso López, Valledupar


def _cerca(dlat: float, dlng: float):
    return punto_desde_latlng(CENTRO[0] + dlat, CENTRO[1] + dlng)


def _organizacion(db: Session, nombre: str, tipo: TipoOrganizacion, telefono: str) -> Organizacion:
    org = db.scalar(select(Organizacion).where(Organizacion.nombre == nombre))
    if org is None:
        org = Organizacion(nombre=nombre, tipo=tipo, telefono_contacto=telefono)
        db.add(org)
        db.flush()
    return org


def _usuario(db: Session, correo: str, nombre: str, rol: RolUsuario, password: str, org=None, tel=None) -> Usuario:
    email = f"{correo}@{DOMINIO}"
    usuario = db.scalar(select(Usuario).where(Usuario.email == email))
    if usuario is None:
        usuario = Usuario(
            nombre=nombre,
            email=email,
            telefono=tel,
            password_hash=hash_password(password),
            rol=rol,
            estado=EstadoUsuario.ACTIVO,
            organizacion_id=org.id if org else None,
            ubicacion_actual=_cerca(0.002, 0.001),
            ubicacion_actualizada_en=datetime.now(UTC),
        )
        db.add(usuario)
        db.flush()
    return usuario


def _si_no_hay(db: Session, modelo, *filtros) -> bool:
    return db.scalar(select(modelo.id).where(*filtros).limit(1)) is None


def sembrar(db: Session, password: str) -> dict:
    bomberos = _organizacion(db, "Bomberos Valledupar", TipoOrganizacion.BOMBEROS, "+576055700119")
    cruz_roja = _organizacion(db, "Cruz Roja Cesar", TipoOrganizacion.CRUZ_ROJA, "+576055735132")
    _organizacion(db, "Defensa Civil Cesar", TipoOrganizacion.DEFENSA_CIVIL, "+576055744144")

    admin = _usuario(db, "admin.bomberos", "Laura Admin Bomberos", RolUsuario.ADMINISTRADOR, password, bomberos)
    voluntario = _usuario(db, "voluntario.bomberos", "Andrés Voluntario", RolUsuario.VOLUNTARIO, password, bomberos)
    _usuario(db, "admin.cruzroja", "Paola Admin Cruz Roja", RolUsuario.ADMINISTRADOR, password, cruz_roja)
    ciudadano = _usuario(db, "ciudadano", "Carlos Ciudadano", RolUsuario.CIUDADANO, password, tel="+573001112233")

    if _si_no_hay(db, SolicitudAyuda, SolicitudAyuda.usuario_id == ciudadano.id):
        db.add_all([
            SolicitudAyuda(
                usuario_id=ciudadano.id, descripcion="Mi mamá está mareada y no puede caminar",
                tipo=TipoSolicitud.MEDICA, ubicacion=_cerca(0.004, -0.003), direccion="Barrio Los Músicos",
                prioridad_ia=PrioridadSolicitud.ALTA, organizacion_manual_id=cruz_roja.id,
            ),
            SolicitudAyuda(
                usuario_id=ciudadano.id, descripcion="Se nos inundó la casa, necesitamos refugio",
                tipo=TipoSolicitud.REFUGIO, ubicacion=_cerca(-0.006, 0.005), direccion="La Nevada",
                prioridad_ia=PrioridadSolicitud.MEDIA, organizacion_manual_id=bomberos.id,
            ),
        ])
    if _si_no_hay(db, Reporte, Reporte.usuario_id == ciudadano.id):
        db.add_all([
            Reporte(
                usuario_id=ciudadano.id, tipo="incendio", descripcion="Sale humo negro de una bodega",
                ubicacion=_cerca(0.003, 0.004), direccion="Zona industrial", organizacion_manual_id=bomberos.id,
                prioridad_ia=PrioridadSolicitud.ALTA,
            ),
            Reporte(
                usuario_id=ciudadano.id, tipo="arbol caido", descripcion="Árbol caído bloquea la vía",
                ubicacion=_cerca(-0.002, -0.004), direccion="Carrera 9",
            ),
        ])
    if _si_no_hay(db, PersonaDesaparecida, PersonaDesaparecida.reportado_por == ciudadano.id):
        db.add(PersonaDesaparecida(
            reportado_por=ciudadano.id, nombre="Lucía Herrera", edad=34, sexo="femenino", estatura="1.60 m",
            fecha_vista=date.today() - timedelta(days=1), lugar="Mercado de Valledupar",
            descripcion="Cabello rizado oscuro, contextura delgada", vestimenta="Blusa roja y jean",
            contacto_nombre="Marta Herrera", contacto_telefono="+573004445566",
        ))
    if _si_no_hay(db, CentroAyuda, CentroAyuda.organizacion_id == cruz_roja.id):
        db.add(CentroAyuda(
            nombre="Albergue Coliseo Julio Monsalvo", tipo="albergue", direccion="Calle 18 # 19-30",
            ubicacion=_cerca(0.008, 0.002), recursos_disponibles="Colchonetas, agua, alimentos",
            gestionado_por=admin.id, organizacion_id=cruz_roja.id,
        ))
    if _si_no_hay(db, ZonaPeligrosa, ZonaPeligrosa.organizacion_id == bomberos.id):
        db.add(ZonaPeligrosa(
            nombre="Ribera del río Guatapurí", tipo_riesgo="inundacion", nivel=NivelZona.ALTO,
            descripcion="Creciente en temporada de lluvias", estado=EstadoZona.EN_MONITOREO,
            centro=_cerca(0.012, -0.010), radio_m=800, area=circulo_a_poligono(CENTRO[0] + 0.012, CENTRO[1] - 0.010, 800),
            gestionado_por=admin.id, organizacion_id=bomberos.id,
        ))
    if _si_no_hay(db, Alerta, Alerta.organizacion_id == bomberos.id):
        db.add(Alerta(
            titulo="Creciente del río Guatapurí", tipo="inundacion", nivel=NivelAlerta.ALTO,
            mensaje="Aléjate de la ribera y sube a un lugar alto.", centro=_cerca(0.012, -0.010), radio_m=2000,
            zona_afectada=circulo_a_poligono(CENTRO[0] + 0.012, CENTRO[1] - 0.010, 2000),
            expira_en=datetime.now(UTC) + timedelta(hours=24), creado_por=admin.id, organizacion_id=bomberos.id,
        ))
    if _si_no_hay(db, Campana, Campana.organizacion_id == cruz_roja.id):
        db.add(Campana(
            titulo="Mercados para La Nevada", descripcion="Familias afectadas por la creciente",
            categoria="alimentos", meta=200, unidad="mercados", fecha_fin=date.today() + timedelta(days=15),
            organizacion_id=cruz_roja.id, creado_por=admin.id,
        ))
    db.commit()
    guias = guia_emergencia_service.cargar_iniciales(db)
    return {"voluntario": voluntario.email, "ciudadano": ciudadano.email, "guias_nuevas": guias}


def main() -> int:
    password = get_settings().seed_demo_password
    if len(password) < 8:
        print("ERROR: pon SEED_DEMO_PASSWORD (mínimo 8 caracteres) en el .env", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        resultado = sembrar(db, password)
    print(f"Listo. Usuarios @{DOMINIO} (contraseña: SEED_DEMO_PASSWORD). {resultado}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
