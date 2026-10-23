# Contexto del proyecto

Trabajo Final de Grado de Ingeniería en Software, Universidad Siglo 21: **Plataforma de acompañamiento en la inserción laboral de jóvenes en tecnología**, de Marcos Alexis Bruno Urquiza. La referencia funcional es el PDF del TFG aportado por el autor; desarrollar de manera incremental (Scrum), tomando las HU-001 a HU-013 como guía. Público objetivo: candidatos jóvenes con poca o ninguna experiencia profesional en IT. Idioma de la interfaz y mensajes: español.

## Arquitectura y organización

- `frontend/`: React + TypeScript creado con Vite; rutas en `src/App.tsx`, módulos en `src/features/`, pantallas en `src/pages/`, cliente HTTP en `src/services/`. Interfaz responsive siguiendo las pantallas del documento (sesión, dashboard, CV, vacantes, análisis y entrevistas).
- `backend/`: Python 3.13 + FastAPI; rutas HTTP bajo `/api/v1` en `app/api/`, lógica en `app/modules/{auth,resumes,vacancies,comparisons,learning,interviews}`, configuración en `app/core/`, modelos y sesión SQLAlchemy en `app/db/`.
- PostgreSQL con pgvector: servicio local en `compose.yaml`; migraciones en `backend/alembic/`. Las tablas iniciales son `candidates`, `resumes`, `vacancies`, `vacancy_analyses`, `competencies`, `comparisons`, `interviews`, `interview_responses` y `learning_resources`. `competencies.embedding` admite vectores sin dimensión fija hasta seleccionar un modelo de embeddings; definir dimensión e índice de similitud al integrarlo. El CV tendrá metadatos y clave de almacenamiento en DB; no almacenar archivos binarios en la tabla.
- Servicio LLM externo: previsto para análisis, comparación, entrevista y feedback. Aún no hay proveedor elegido ni SDK/credenciales configurados. Los datos del candidato se envían a servicios externos solo cuando la funcionalidad se implemente y su tratamiento esté definido.
- Fase actual: andamiaje ejecutable, rutas de módulos como marcadores; **las historias de usuario aún no están implementadas**. No confundir tablas o páginas preparadas con funcionalidades terminadas.

## Historias y reglas funcionales

- HU-001: interfaz principal responsive para escritorio y celular.
- HU-002/003/004: registro y sesión de candidato por email y contraseña, diseño con navegación entre login y registro. Google aparece en HU-002 como opción futura y requiere configuración OAuth independiente; rol único: candidato.
- HU-005: subir CV **PDF, máximo 5 MB**; validar extensión, tipo real y tamaño en backend, no confiar en el navegador.
- HU-006/007/008: ingreso de vacante como **texto plano**; identificar competencias, tecnologías y seniority; mostrar lista de inconsistencias, señales de riesgo y porcentaje orientativo. El análisis de vacantes debe ser accesible sin registrarse; definir política de persistencia anónima antes de exponer datos privados.
- HU-009/010: comparar CV propio con vacante, exigir ambos insumos; listar brechas, porcentaje de diferencia y caso sin brechas. Controlar propiedad de CV y vacante por usuario.
- HU-011: sugerir recursos de aprendizaje priorizando los gratuitos y verificables.
- HU-012/013: entrevista técnica contextualizada por vacante y opcionalmente CV, finalizar con confirmación; cancelación abrupta sin feedback; finalización normal genera puntuación 0–100 y competencias a reforzar. La pantalla del PDF ilustra voz; definir soporte de audio antes de implementarlo.

## Seguridad y decisiones por resolver

- El PDF **se contradice**: HU-002 exige al menos 6 caracteres y uno especial; la sección Seguridad exige al menos 8, una mayúscula y un número. Para implementación futura aplicar el criterio combinado más exigente: **mínimo 8, mayúscula, número y carácter especial**, y reflejarlo en UI/API. La validez de 200 días y cambio de contraseña distinto al anterior también figuran en Seguridad: planificar flujo de renovación antes de anunciarlo como funcional.
- El PDF menciona SHA-256 para contraseñas; usar **Argon2id con sal por contraseña**, no SHA-256 directo, al implementar auth. No persistir contraseñas ni tokens en texto plano. Google OAuth no se considera implementado por existir una columna nullable de hash.
- Los porcentajes de riesgo y brecha son orientativos, no garantías sobre una vacante ni un candidato. Verificar entradas, respuestas LLM y límites de costo; nunca exponer claves del proveedor en el frontend.
- Proteger CV, análisis, comparaciones y entrevistas con autorización por propietario. No registrar CV ni secretos en logs. Variables sensibles en `.env` local (ignorado por Git); ejemplos en `.env.example`.
- El documento propone respaldos diarios PostgreSQL con `pg_dump`, control de versiones remoto y copia física quincenal: son tareas operativas futuras, no automatizadas por este andamiaje.

## Trabajo y verificación

- En `backend/`: `uv sync`, `uv run alembic upgrade head`, `uv run uvicorn app.main:app --reload`, `uv run ruff check .`, `uv run pytest` (cuando haya tests).
- En `frontend/`: `npm install`, `npm run dev`, `npm run lint`, `npm run build`.
- Desde la raíz: `docker compose up -d db`; usar el `README.md` para orden de arranque. No alterar migraciones ya aplicadas: crear una nueva por cada cambio de esquema.
- Mantener API, tipos y pantallas alineados con criterios de aceptación; probar flujos principales al implementarlos. Actualizar este archivo cuando haya decisiones de dominio o cambios de estado de HU.
