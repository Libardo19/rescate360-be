"""Carga el contenido inicial de la guía de emergencia (solo si la tabla está vacía):

    docker compose exec api python -m scripts.seed.guia_emergencia
"""

from app.core.database import SessionLocal
from app.services import guia_emergencia_service


def main() -> None:
    db = SessionLocal()
    try:
        creadas = guia_emergencia_service.cargar_iniciales(db)
        print(f"Guías creadas: {creadas}" if creadas else "La guía ya tenía contenido: no se cambió nada")
    finally:
        db.close()


if __name__ == "__main__":
    main()
