# Acompañamiento IT

Base del prototipo de la **Plataforma de acompañamiento en la inserción laboral de jóvenes en tecnología** (TFG, Universidad Siglo 21). Esta entrega prepara frontend, API y esquema de datos; las funcionalidades de las HU-001 a HU-013 se incorporarán por iteraciones.

## Requisitos

- Python 3.13 y [`uv`](https://docs.astral.sh/uv/)
- Node.js 20.19+ o 22.12+ y npm (Vite latest)
- Docker Desktop con motor iniciado para PostgreSQL + pgvector

## Inicio local

En tres terminales, desde la raíz del proyecto:

```powershell
docker compose up -d db
```

El PostgreSQL del contenedor se publica en `127.0.0.1:5433` para no interferir con una instalación local que utilice el puerto `5432`.

```powershell
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

```powershell
cd frontend
npm install
npm run dev
```

Abrir http://localhost:5173. La API está en http://localhost:8000/docs y su prueba de disponibilidad en http://localhost:8000/api/v1/health. Vite redirige `/api` al backend local; el frontend indica el estado de conexión en la pantalla principal.

Para configurar otros puertos o credenciales, copiar `backend/.env.example` a `backend/.env` y ajustar `DATABASE_URL` y `FRONTEND_ORIGIN`. Para apuntar el frontend a otro servidor, copiar `frontend/.env.example` a `frontend/.env` y definir `VITE_API_URL`. No subir archivos `.env` al repositorio.

## Estructura

```text
.
├── AGENTS.md              # Requisitos del TFG, convenciones y decisiones
├── compose.yaml           # PostgreSQL con pgvector (solo entorno local)
├── backend/
│   ├── app/api/           # Endpoints FastAPI
│   ├── app/core/          # Configuración
│   ├── app/db/            # Modelos SQLAlchemy y conexión
│   ├── app/modules/       # Dominios funcionales del proyecto
│   ├── alembic/           # Migraciones versionadas
│   ├── pyproject.toml     # Dependencias uv
│   └── uv.lock
└── frontend/
    ├── src/features/      # Catálogo de módulos
    ├── src/pages/         # Vistas iniciales
    ├── src/services/      # Acceso a la API
    ├── package.json
    └── package-lock.json
```

El backend incluye modelos iniciales para candidato, CV, vacante, análisis, competencias, comparaciones, entrevistas y recursos; el esquema se aplica con Alembic. El endpoint de salud no requiere base de datos. Las vistas de módulos son marcadores y **no efectúan registro, cargas, análisis ni simulaciones** todavía. No se ha elegido proveedor de IA.

## Comprobaciones

```powershell
cd backend
uv run ruff check .
uv run python -c "from app.main import app; print(app.title)"
```

```powershell
cd frontend
npm run lint
npm run build
```
