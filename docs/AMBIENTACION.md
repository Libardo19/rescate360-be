# RESCATE360 — Ambientación del proyecto

Guía para dejar el proyecto corriendo en tu PC. Cubre los dos repositorios:

- **Backend:** [rescate360-be](https://github.com/Libardo19/rescate360-be) (Python + FastAPI, corre en Docker)
- **App móvil:** [rescate360-fe](https://github.com/Libardo19/rescate360-fe) (Flutter, corre en emulador o celular)

---

## 1. Cómo se armó el ambiente (resumen)

**Backend en Docker.** Todo el backend corre en contenedores, así nadie tiene que instalar Python ni PostgreSQL, y todos usamos exactamente las mismas versiones. Un solo `docker compose up` levanta 6 contenedores:

| Contenedor | Qué es |
|---|---|
| `rescate360-db` | PostgreSQL 16 + PostGIS 3.4. Es la imagen `postgis/postgis`, porque la migración 0001 necesita la extensión PostGIS y una imagen `postgres` normal no la trae |
| `rescate360-redis` | Redis 7.4, cola de mensajes para Celery |
| `rescate360-api` | La API FastAPI (Python 3.12). Se recarga sola cuando guardas un archivo |
| `rescate360-worker` | Worker de Celery: ejecuta los jobs en segundo plano (IA, notificaciones) |
| `rescate360-beat` | Celery Beat: dispara los jobs programados (cada hora, cada día) |
| `rescate360-pgadmin` | pgAdmin, para ver las tablas y el diagrama de la base de datos |

**Dependencias de Python fijadas y verificadas.**
- Las 4 versiones de base de datos que acordó el equipo quedaron exactas: `sqlalchemy==2.0.54`, `geoalchemy2==0.20.0`, `alembic==1.20.0` y `psycopg2-binary==2.9.13`.
- Las demás librerías se eligieron y fijaron de forma que no choquen con esas. Se comprobó con `pip check`: *No broken requirements found*.
- Se quitó `passlib`, que no se mantiene desde 2020 y falla con las versiones nuevas de bcrypt. En su lugar se usa `bcrypt` directo.
- Se cambió `python-jose` por `PyJWT` para los tokens.

**Migraciones con Alembic.** Está lista la `0001` (habilita PostGIS). Las demás se crean a medida que se haga cada tabla. Alembic está conectado con GeoAlchemy2 para que `--autogenerate` entienda las columnas geográficas y no intente borrar las tablas internas de PostGIS.

**CI en GitHub.** En cada push, GitHub Actions levanta PostGIS y Redis, instala dependencias, corre `pip check`, aplica las migraciones y ejecuta los tests.

**App móvil.**
- **Mapa:** `flutter_map` + OpenStreetMap. No necesita API key ni tarjeta de crédito como Google Maps, y permite guardar el mapa para usarlo sin conexión.
- **Librerías:** se agregaron con `flutter pub add` (dio, geolocator, sqflite, etc.), así que las versiones son compatibles entre sí.
- **Permisos:** se declararon los de Android e iOS (internet, ubicación, cámara, galería, llamar al 123).
- **Variables:** se leen de un archivo `.env`.
- **Verificación:** el APK de desarrollo compila.

**¿Python y Dart chocan?** No. Son programas separados que solo se hablan por HTTP con JSON. El único cuidado: PostGIS/GeoJSON devuelven las coordenadas como `[longitud, latitud]` y Flutter usa `LatLng(latitud, longitud)`, al revés.

---

## 2. Qué instalar (una sola vez)

| Programa | Para qué | Cómo verificar |
|---|---|---|
| [Git](https://git-scm.com/downloads) | Clonar los repos | `git --version` |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Correr el backend | `docker compose version` |
| [Flutter SDK](https://docs.flutter.dev/get-started/install) (3.44 o superior) | Correr la app | `flutter --version` |
| [Android Studio](https://developer.android.com/studio) | Android SDK y emulador | `flutter doctor` |
| [VS Code](https://code.visualstudio.com/) (opcional) | Editor. Extensiones: *Python*, *Flutter*, *Docker* | — |

> **No hace falta instalar Python ni PostgreSQL.** Vienen dentro de Docker.

Notas para Windows:
- Docker Desktop pide activar **WSL 2** al instalarse. Acepta y reinicia el PC.
- Abre Docker Desktop y espera a que diga *Engine running* antes de usar cualquier comando `docker`.
- Corre `flutter doctor` y resuelve lo que salga en rojo en **Flutter** y **Android toolchain**. La línea de *Visual Studio* se puede ignorar: solo aplica para apps de escritorio Windows.
- Si `flutter doctor` pide aceptar licencias: `flutter doctor --android-licenses`, y responde `y` a todo.

---

## 3. Clonar los repositorios

Crea una carpeta de trabajo y clona los dos repos uno al lado del otro:

```bash
cd Documents
git clone https://github.com/Libardo19/rescate360-be.git
git clone https://github.com/Libardo19/rescate360-fe.git
```

---

## 4. Levantar el backend

```bash
cd rescate360-be
```

**4.1. Crear el archivo `.env`** a partir del ejemplo:

```bash
# Git Bash / macOS / Linux
cp .env.example .env

# PowerShell
Copy-Item .env.example .env
```

Los valores del ejemplo funcionan tal cual para desarrollo local. El `.env` **nunca** se sube a GitHub (ya está en `.gitignore`).

**4.2. Construir y levantar los contenedores.** La primera vez tarda unos minutos porque descarga imágenes e instala dependencias:

```bash
docker compose up -d --build
```

**4.3. Aplicar las migraciones:**

```bash
docker compose exec api alembic upgrade head
```

Debe mostrar `Running upgrade -> 0001, habilitar postgis`.

**4.4. Verificar que todo está bien:**

```bash
docker compose ps
```

Los 6 contenedores deben estar `Up`, y `rescate360-db` y `rescate360-redis` además `(healthy)`.

Luego abre en el navegador:

| URL | Qué debes ver |
|---|---|
| http://localhost:8000/health/ready | `{"status":"ok","postgis":"3.4.3","redis":"ok"}` |
| http://localhost:8000/docs | La documentación interactiva (Swagger) de la API |
| http://localhost:5050 | pgAdmin |

Y corre los tests:

```bash
docker compose exec api pytest
```

Debe decir `1 passed`.

**4.5. Ver la base de datos en pgAdmin**

1. Abre http://localhost:5050. No pide login.
2. En el panel izquierdo: *Servers → RESCATE360 → RESCATE360 (local)*.
3. La primera vez pide la contraseña de la BD: `rescate`. Marca *Save password*.
4. Para ver el diagrama de tablas: clic derecho sobre la base **rescate360** → **ERD For Database**.

Si prefieres otro cliente (DBeaver, DataGrip), la conexión desde tu PC es:

| Campo | Valor |
|---|---|
| Host | `localhost` |
| Puerto | `5435` |
| Base de datos | `rescate360` |
| Usuario / contraseña | `rescate` / `rescate` |

---

## 5. Levantar la app móvil

```bash
cd ../rescate360-fe
```

**5.1. Crear el `.env` e instalar dependencias:**

```bash
cp .env.example .env          # PowerShell: Copy-Item .env.example .env
flutter pub get
```

**5.2. Abrir un emulador.** En Android Studio: *Device Manager* → crea un dispositivo (por ejemplo Pixel, con Android 14 o superior) → ▶. Para comprobar que Flutter lo ve:

```bash
flutter devices
```

**5.3. Correr la app** (con el backend ya levantado):

```bash
flutter run --dart-define-from-file=.env
```

Siempre pasa `--dart-define-from-file=.env`: así la app recibe la URL de la API y la del mapa.

**Con un celular físico en vez del emulador:**
1. Activa *Opciones de desarrollador → Depuración USB* en el celular y conéctalo por USB.
2. En `.env` cambia `API_BASE_URL` por la IP de tu PC en la red WiFi (por ejemplo `http://192.168.1.10:8000`). La IP sale con `ipconfig` en Windows, en *Dirección IPv4*.
3. El PC y el celular deben estar en la misma red WiFi.

> En el emulador, `10.0.2.2` significa "el localhost de mi PC". Por eso el `.env.example` trae `http://10.0.2.2:8000`.

---

## 6. Día a día

| Quiero… | Comando (desde `rescate360-be`) |
|---|---|
| Arrancar el backend | `docker compose up -d` |
| Apagarlo (conserva los datos) | `docker compose down` |
| Ver logs de la API y el worker | `docker compose logs -f api worker` |
| Correr tests | `docker compose exec api pytest` |
| Aplicar migraciones nuevas (después de un `git pull`) | `docker compose exec api alembic upgrade head` |
| Crear una migración nueva | `docker compose exec api alembic revision --autogenerate -m "crear usuarios" --rev-id 0002` |
| Borrar la BD y empezar de cero | `docker compose down -v` y luego `up -d` + `alembic upgrade head` |
| Reconstruir después de cambiar `requirements*.txt` | `docker compose up -d --build` |

- **Backend:** el código se monta dentro del contenedor, así que al guardar un `.py` la API se recarga sola. No hace falta reconstruir.
- **App:** en `flutter run`, presiona `r` para *hot reload* y `R` para *hot restart*.

---

## 7. Reglas del equipo sobre dependencias

1. **No cambiar las versiones de base de datos** (`sqlalchemy`, `geoalchemy2`, `alembic`, `psycopg2-binary`) sin acordarlo con el equipo.
2. **Librería nueva de Python:**
   1. Agrégala fijada con `==` en `requirements.txt`, o en `requirements-dev.txt` si es solo para pruebas.
   2. Reconstruye: `docker compose up -d --build`.
   3. Verifica: `docker compose exec api pip check`. Debe decir *No broken requirements found*.
   4. Súbela en el mismo commit que el código que la usa.
3. **Librería nueva de Flutter:** usa `flutter pub add <paquete>`, que elige una versión compatible, y sube `pubspec.yaml` **y** `pubspec.lock`.
4. **No subir** `.env`, credenciales de Firebase (`google-services.json`, `GoogleService-Info.plist`) ni llaves.

---

## 8. Problemas comunes

| Problema | Solución |
|---|---|
| `docker: command not found` o *Cannot connect to the Docker daemon* | Abre Docker Desktop y espera a *Engine running* |
| `Bind for 0.0.0.0:5435 failed: port is already allocated` (o 6379, 8000, 5050) | Otro programa usa ese puerto. Cambia `DB_PORT`, `REDIS_PORT`, `API_PORT` o `PGADMIN_PORT` en tu `.env` y vuelve a `docker compose up -d` |
| `/health/ready` responde `degraded` | Algún contenedor no está listo. Revisa `docker compose ps` y `docker compose logs db redis` |
| La app no conecta con la API | Verifica que el backend esté arriba (http://localhost:8000/health). En celular físico, usa la IP del PC en `API_BASE_URL`, no `10.0.2.2` |
| El mapa sale en gris | La app no tiene internet, o no se pasó `--dart-define-from-file=.env` |
| `flutter doctor` falla en Android toolchain | Abre Android Studio → *SDK Manager* → instala *Android SDK Command-line Tools*, luego `flutter doctor --android-licenses` |
| Cambié `requirements.txt` y la librería no aparece | Faltó reconstruir: `docker compose up -d --build` |
| pgAdmin no muestra el servidor RESCATE360 | Borra su volumen y vuelve a levantarlo: `docker compose rm -sf pgadmin`, `docker volume rm rescate360_pgadmin_data`, `docker compose up -d` |
