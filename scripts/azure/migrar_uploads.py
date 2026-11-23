from pathlib import Path

from azure.storage.blob import BlobServiceClient
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine


def rutas_locales():
    consultas = (
        "SELECT ruta FROM evidencias_reporte WHERE ruta IS NOT NULL AND ruta NOT LIKE 'http%' AND ruta NOT LIKE '/%'",
        "SELECT foto_ruta FROM personas_desaparecidas WHERE foto_ruta IS NOT NULL AND foto_ruta NOT LIKE 'http%' AND foto_ruta NOT LIKE '/%'",
    )
    with engine.connect() as connection:
        for consulta in consultas:
            for (ruta,) in connection.execute(text(consulta)):
                yield ruta


def main():
    settings = get_settings()
    if settings.storage_backend.lower() != "azure":
        raise SystemExit("Configura STORAGE_BACKEND=azure antes de ejecutar esta migración")
    if not settings.storage_bucket or not settings.azure_storage_connection_string:
        raise SystemExit("Faltan STORAGE_BUCKET o AZURE_STORAGE_CONNECTION_STRING")

    servicio = BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)
    contenedor = servicio.get_container_client(settings.storage_bucket)
    origen = Path(settings.uploads_dir)

    subidos = 0
    omitidos = 0
    for ruta in rutas_locales():
        archivo = origen / ruta
        if not archivo.is_file():
            print(f"NO ENCONTRADO {ruta}")
            omitidos += 1
            continue
        with archivo.open("rb") as contenido:
            contenedor.upload_blob(name=ruta, data=contenido, overwrite=True)
        print(f"SUBIDO {ruta}")
        subidos += 1

    print(f"Listo: {subidos} archivos subidos, {omitidos} omitidos")


if __name__ == "__main__":
    main()
