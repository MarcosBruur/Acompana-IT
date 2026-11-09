# Auditoría técnica del proyecto

**Fecha de auditoría y revisión:** 2026-11-09. **Alcance original:** aplicación FastAPI y React, clientes HTTP, modelos, migraciones, configuración y pruebas. Se contrastó el comportamiento con `AGENTS.md` y `README.md`. No se inspeccionaron secretos locales ni contenido de CV privados. Los módulos de comparación y aprendizaje todavía son incrementos pendientes. **Los hallazgos A-01 a A-28 describen el estado ANTERIOR a las correcciones**: consultar la tabla de seguimiento para su estado vigente.

**Verificación posterior:** `uv run ruff check .`, `uv run pytest -q` (54 aprobadas y una integración PostgreSQL omitida sin variable de entorno), `npm run lint` y `npm run build` correctos. La integración PostgreSQL se ejecutó aparte con `TEST_DATABASE_URL` (1 aprobada) en la base temporal `tfg_audit_test`; `alembic upgrade head` y `alembic check` también pasaron allí, y se eliminó esa base de prueba. No se aplicaron migraciones a la base principal. **Criterio:** «Confirmado» significa deducible directamente del código o de las pruebas; «Riesgo» señala una situación cuya manifestación precisa necesita ensayo o condiciones adicionales. Gravedades: **Alta** (seguridad, integridad o disponibilidad significativa), **Media** (funcionalidad, privacidad o escalabilidad con impacto concreto), **Baja** (mantenibilidad, documentación o UX localizada).

## Seguimiento de correcciones

| Estado | Incidencias | Qué se hizo / qué falta |
| --- | --- | --- |
| Corregidas | A-02, A-04, A-06, A-07, A-08, A-10, A-15, A-16, A-20 a A-26 | Se verifican cuentas activas, se reembolsa cupo local ante fallos técnicos, se limpia el análisis anónimo al cambiar/cerrar sesión, se añaden transacciones cortas y unicidad de entrevistas en `0011`, se filtran temas con código y alertas duplicadas, se agrega `/ready` y se alinea la interfaz y el cliente HTTP. A-07 depende de ejecutar `uv run alembic upgrade head` en el entorno destino. |
| Parciales | A-01, A-03, A-11, A-13, A-18, A-19, A-27 | A-01/A-03: límites locales por IP/cuenta, limpieza y tope de memoria, todavía sin limitador distribuido. A-11: índices agregados, todavía sin `EXPLAIN` con volumen real. A-13/A-19: limitaciones documentadas, no pueden hacerse retroactivamente reversibles los UUID ni imponer texto enviado por token directo. A-18: fallback textual implementado, falta prueba de autoplay en navegador. A-27: migraciones y restricción probadas en PostgreSQL vacío, no sobre datos legados. |
| Pendientes por diseño/alcance | A-05, A-09, A-12, A-14, A-17, A-28 | A-05 exige mediar el canal de voz o aceptar expresamente el límite de confianza del token. A-09 se aborda al construir comparaciones. A-12 requiere paginación **con navegación frontend** de historiales y CV, no solo truncar la API. A-14 exige reconciliación segura de archivos y respaldos. A-17 requiere aislamiento/presupuestos de CPU para PDF sin reducir el requisito de 5 MB. A-28 precisa una infraestructura de pruebas de navegador y verificación de WebRTC/dictado. |

**Siguiente despliegue:** verificar/depurar datos incompatibles antes de aplicar `0011_audit_integrity` en una base existente (entrevistas en curso duplicadas, posiciones duplicadas o valores fuera de rango). Respaldar DB y medios. Evitar modificar migraciones anteriores.

## Resumen ejecutivo

Se corrigieron en el código los problemas de acceso de cuentas inactivas, cupos locales, integridad y transacciones durante llamadas de IA, respuestas con código y UI incoherente. Para un despliegue de varios procesos sigue siendo prioritaria la limitación compartida; también quedan paginación integral, resiliencia del procesamiento de PDF, conciliación de archivos y pruebas en navegador. Se conservan cookies HttpOnly, contraseñas Argon2id, comprobación de propietario en descargas, controles de origen para operaciones mutantes y separación de análisis anónimos de historiales privados.

## Seguridad y privacidad

### A-01 · Falta control de intentos para contraseña y registro — Alta · Confirmado
- **Evidencia:** `backend/app/modules/auth/router.py:169-200,219-240` expone registro, login y cambio de contraseña sin límite por cuenta/IP; `backend/app/modules/vacancies/router.py:91-99` sí incorpora un control similar para análisis.
- **Afecta:** facilita fuerza bruta y enumeración masiva de credenciales; además, cada comprobación Argon2 consume recursos del servidor. El registro sin límite permite altas automatizadas y crecimiento de la base.
- **Recomendación:** limitar por cuenta y por origen, con ventanas y penalización gradual para login/cambio de contraseña; limitar también registros. Usar almacenamiento compartido al desplegar varios procesos, sin registrar ni revelar contraseñas.

### A-02 · La cuenta inactiva sigue pudiendo autenticarse y operar — Alta · Confirmado
- **Evidencia:** existe `Candidate.active` (`backend/app/db/models.py:35`; migración `backend/alembic/versions/0007_candidate_active.py:17-19`), pero `login`, `current_session`, `active_candidate`, `optional_candidate` y el callback Google no comprueban ese campo (`backend/app/modules/auth/router.py:148-163,190-200,272-320`; `backend/app/modules/vacancies/router.py:72-85`).
- **Afecta:** poner `active=false` en la base no revoca acceso, historial ni emisión de tokens de voz. El nombre `ActiveCandidate` induce a creer que sí lo hace.
- **Recomendación:** decidir la semántica de desactivación; si impide acceso, comprobarla de forma centralizada en sesiones, login y OAuth, revocar sesiones existentes y añadir pruebas de cuentas desactivadas.

### A-03 · Los limitadores públicos no son compartidos y pueden crecer indefinidamente — Media · Confirmado
- **Evidencia:** `_requests` en `backend/app/modules/vacancies/router.py:24-26,91-99` guarda una entrada por IP/cuenta y solo depura la cola cuando vuelve a solicitarse **esa misma clave**. `_attempts` y `_voice_attempts` tienen el mismo patrón (`backend/app/modules/interviews/router.py:34-38,210-217,259-266`). Todos son diccionarios por proceso; `AGENTS.md` ya reconoce la limitación multiproceso.
- **Afecta:** múltiples IP distintas dejan claves residentes incluso después de caducar sus ventanas; con varias instancias los límites se multiplican y no constituyen un presupuesto de proveedor global.
- **Recomendación:** caducar claves vacías y limitar memoria; para despliegue multiproceso utilizar almacenamiento/limitación compartida y presupuesto de consumo centralizado. Probar ventanas, cambios de IP y múltiples trabajadores.

### A-04 · El cupo local de solicitudes de IA se consume también con fallos — Media · Confirmado
- **Evidencia:** `check_limit` agrega la marca **antes** de llamar al modelo (`backend/app/modules/vacancies/router.py:91-99,119-153`); `start` consume un intento antes de `generate_questions` y `voice_token` antes de solicitar el secreto (`backend/app/modules/interviews/router.py:205-226,259-285`).
- **Afecta:** una caída del proveedor, falta de saldo, error de modelo o saturación agotan el límite local del candidato aun sin recibir resultado; el cupo de análisis también se consume cuando el semáforo está ocupado. Esto no equivale necesariamente a haber consumido créditos facturables de OpenAI.
- **Recomendación:** diferenciar solicitudes realizadas de solicitudes exitosas o devolver el cupo ante errores técnicos/saturación, manteniendo protección frente a abuso; documentar la política elegida.

### A-05 · El token efímero delega al navegador el control de qué texto envía a Realtime — Media · Riesgo de arquitectura
- **Evidencia:** `backend/app/modules/interviews/router.py:248-287` entrega un secreto de sesión de audio al cliente; `frontend/src/services/realtime-voice.ts:124-149` decide localmente el contenido de `response.create`. La API valida propietario y entrevista en curso **al emitir el token**, pero no puede comprobar el texto enviado directamente al proveedor con ese secreto.
- **Afecta:** la promesa de que Realtime recibe únicamente texto visible depende de que el cliente sea confiable; una modificación del navegador podría usar el token para otras entradas y consumir cuota durante su vigencia. No implica que el cliente actual envíe el CV por esta vía.
- **Recomendación:** tratar la restricción como garantía del cliente, no del backend; limitar alcance/duración y gasto de las sesiones efímeras, y considerar mediación del servidor si se requiere imponer esa garantía técnicamente.

### A-06 · Resultado anónimo persiste en memoria al cambiar de cuenta en la misma pestaña — Media · Confirmado
- **Evidencia:** `transientAnalysis` es una variable de módulo sin borrado explícito (`frontend/src/services/vacancies.ts:26-29`); `/vacantes/analisis` la lee aun después de cambios de sesión (`frontend/src/pages/VacancyPage.tsx:119-124`).
- **Afecta:** en un equipo compartido, otra persona puede ver un análisis anónimo previo mientras la pestaña siga abierta, aunque no esté persistido en PostgreSQL.
- **Recomendación:** limpiar el análisis al salir de la página, al cambiar/cerrar sesión o al iniciar un nuevo análisis; explicitar su alcance de vida y probar el cambio de usuario.

## Concurrencia e integridad de base de datos

### A-07 · No se garantiza una única entrevista en curso por candidato — Alta · Riesgo de concurrencia sustentado por código
- **Evidencia:** `backend/app/modules/interviews/router.py:192-195` comprueba la ausencia de entrevistas antes de la llamada asíncrona al modelo y `:228-240` inserta después, sin bloqueo por candidato ni índice único parcial en `backend/app/db/models.py:129-147` o `backend/alembic/versions/0010_interview_simulation.py`. El endpoint `/active` devuelve solo una (`router.py:175-180`).
- **Afecta:** dos inicios simultáneos pueden crear dos sesiones en curso, pagar dos generaciones y dejar una sesión fuera del flujo normal de recuperación.
- **Recomendación:** índice único parcial `(candidate_id) WHERE status='in_progress'`, manejo de colisión y coordinación transaccional por candidato; probar inicios concurrentes sobre PostgreSQL.

### A-08 · Se retiene una transacción mientras se espera a OpenAI — Alta · Riesgo de disponibilidad sustentado por código
- **Evidencia:** `Database` abre la misma sesión para toda la solicitud (`backend/app/modules/auth/router.py:32-37`). `start` ejecuta `select` antes de `await generate_questions` (`backend/app/modules/interviews/router.py:187-223`); `answer_conversation` lee entrevista y respuestas antes de `await evaluate_answer` (`:310-332`); `analyze` consulta candidato en la dependencia opcional antes de `await analyze_offer` (`backend/app/modules/vacancies/router.py:72-85,119-130`).
- **Afecta:** SQLAlchemy inicia transacción al consultar; conexiones y transacciones pueden permanecer ocupadas decenas de segundos durante espera de red, aumentando presión del pool y latencia con concurrencia real.
- **Recomendación:** cargar contexto mínimo y cerrar/finalizar la transacción antes de invocar el modelo; abrir otra transacción corta para validar estado y guardar. Medir pool y contención en PostgreSQL.

### A-09 · Referencias cruzadas de comparación no aseguran mismo propietario — Media · Confirmado (riesgo al implementar el módulo)
- **Evidencia:** `Comparison` tiene FKs independientes a candidato, CV y vacante (`backend/app/db/models.py:116-125`; `backend/alembic/versions/0001_initial.py:68-76`), sin restricción que compruebe que el CV y la vacante pertenecen al mismo candidato. Aún no hay endpoint de comparación (`backend/app/api/router.py:3-12`).
- **Afecta:** un futuro error de autorización podría persistir asociaciones entre candidatos distintos; las FKs actuales solo prueban existencia, no propiedad.
- **Recomendación:** al implementar HU-009/010 comprobar propiedad y estado activo de ambos insumos en la misma transacción; considerar FKs compuestas/índices únicos auxiliares si se requiere defensa adicional desde la base.

### A-10 · La DB no impone restricciones de estado, nota ni posición de preguntas — Media · Confirmado
- **Evidencia:** `backend/app/db/models.py:136-163` deja `status`, `score`, `position`, `verdict`, `correct_index` y `mode` sin `CHECK`; tampoco existe unicidad `(interview_id, position)` en las migraciones (`backend/alembic/versions/0001_initial.py:78-96`, `backend/alembic/versions/0010_interview_simulation.py:18-30`). El servidor calcula la nota y ordena por `position` (`backend/app/modules/interviews/router.py:119-125,372-384`).
- **Afecta:** inserciones o futuras rutas defectuosas pueden producir preguntas duplicadas, notas fuera de 0–100 y estados imposibles que la API no sabe representar.
- **Recomendación:** nueva migración con `CHECK` para enums/rangos y `UNIQUE(interview_id, position)`; validar datos existentes antes de aplicar restricciones. No modificar migraciones ya aplicadas.

### A-11 · Faltan índices para consultas crecientes de historial y respuestas — Media · Confirmado
- **Evidencia:** índices explícitos de migraciones: correo, sesión por candidato y CV principal (`backend/alembic/versions/0001_initial.py:30`, `0002_auth.py:30`, `0004_profile.py:24`). Los listados ordenan por candidato/fecha y las respuestas por entrevista/posición (`backend/app/modules/vacancies/router.py:186-196`; `backend/app/modules/interviews/router.py:175-180,395-407`; `backend/app/modules/profile/router.py:115-118`; `backend/app/modules/interviews/router.py:119-125`). Las FKs solas no garantizan índices en PostgreSQL.
- **Afecta:** planes menos eficientes al crecer vacantes, entrevistas y CV; paginación futura también requerirá esos accesos.
- **Recomendación:** medir con `EXPLAIN (ANALYZE, BUFFERS)` en PostgreSQL y añadir índices compuestos/parciales para `(candidate_id, active, created_at/id)`, entrevistas por estado, CV por fecha y `(interview_id, position)` según uso real.

### A-12 · Historial sin paginación y carga repetida de relaciones — Media · Confirmado
- **Evidencia:** `.all()` devuelve todas las vacantes y CV (`backend/app/modules/vacancies/router.py:190-196`; `backend/app/modules/profile/router.py:115-118`); el historial de entrevistas también trae todas las filas (`backend/app/modules/interviews/router.py:395-407`). El historial de vacantes consulta `row.analysis` por elemento (`vacancies/router.py:193-196`), sin carga explícita anticipada.
- **Afecta:** respuesta y memoria crecen sin límite; al listar vacantes puede aparecer una consulta SQL adicional por cada oferta.
- **Recomendación:** paginar con orden estable y tope; proyectar/join el porcentaje o usar carga anticipada. Añadir pruebas con varias páginas y comprobar número de consultas.

### A-13 · Reversión de IDs no recupera identificadores originales — Media · Confirmado
- **Evidencia:** el `downgrade` de `backend/alembic/versions/0003_integer_ids.py:40-53,104-105` genera UUID nuevos, como ya reconoce el propio comentario; no restaura los UUID previos.
- **Afecta:** vínculos externos, referencias exportadas o integraciones que conserven IDs antiguos quedan rotos tras una reversión aunque las FKs internas se reconstruyan.
- **Recomendación:** tratar esa migración como irreversible para datos reales, exigir respaldo/plan de restauración y documentarlo en la guía operativa. No reescribir la revisión ya aplicada.

### A-14 · Archivos y transacciones no se recuperan juntos frente a cortes de proceso — Media · Riesgo
- **Evidencia:** el PDF se escribe en disco y luego se confirma en DB; la limpieza solo ocurre en el `except` Python (`backend/app/modules/profile/router.py:138-149`). La foto anterior se borra después de confirmar la nueva (`:89-103`).
- **Afecta:** si el proceso cae entre escritura y commit quedan archivos huérfanos; si falla el borrado posterior quedan medios sin referencia. No existe transacción atómica entre PostgreSQL y filesystem.
- **Recomendación:** reconciliación periódica entre claves de DB y medios con retención segura; almacenar en volumen persistente, incluir ambos en respaldos y registrar métricas de archivos huérfanos sin exponer datos privados.

## IA, reglas funcionales y disponibilidad

### A-15 · Los temas generados pueden introducir código en el feedback final — Media · Confirmado
- **Evidencia:** `Question.topic` solo limita longitud (`backend/app/modules/interviews/simulation.py:14-20`); `finish` incorpora temas no validados a `skills_to_improve` y al texto `feedback` (`backend/app/modules/interviews/router.py:374-382`). El filtro `contains_literal_code` se aplica a correcciones y a la explicación de preguntas omitidas, pero no al feedback agregado (`:363-369`).
- **Afecta:** puede guardarse y mostrarse código o pseudocódigo en el resultado conversacional pese a la regla del proyecto de correcciones narrativas sin código.
- **Recomendación:** normalizar/validar temas del modelo antes de persistirlos; filtrar o reformular también feedback y competencias derivadas, con prueba que inyecte un tema con código.

### A-16 · El porcentaje de riesgo puede inflarse con alertas duplicadas — Media · Confirmado
- **Evidencia:** `supported_findings` solo comprueba que la cita exista (`backend/app/modules/vacancies/router.py:102-105`); el cálculo suma cada hallazgo por separado, sin deduplicar evidencia o motivo (`:155-163`). El modelo puede devolver hasta ocho hallazgos de cada tipo (`backend/app/modules/vacancies/analysis.py:58-63`).
- **Afecta:** la misma frase citada varias veces puede elevar artificialmente el porcentaje orientativo hasta 100.
- **Recomendación:** deduplicar por cita normalizada y categoría/motivo, o fijar máximo por señal; probar resultados repetidos de IA y mantener visible el carácter orientativo.

### A-17 · La validación del PDF no limita complejidad ni tiempo de extracción — Media · Riesgo
- **Evidencia:** se admite hasta 5 MB y se analiza con `PdfReader` al cargar (`backend/app/modules/profile/router.py:121-134`); en entrevistas se extrae texto de hasta 12 páginas sin límite de tiempo por página (`backend/app/modules/interviews/router.py:151-161`).
- **Afecta:** un PDF pequeño pero complejo podría consumir CPU/memoria durante parsing/extracción; el límite de bytes no equivale a un límite de trabajo.
- **Recomendación:** establecer presupuesto de páginas, tiempo y recursos en procesamiento aislado, rechazar documentos problemáticos y medir casos adversos; mantener el límite de 5 MB y la validación real ya presentes.

### A-18 · El proveedor de voz bloqueado puede detener la secuencia conversacional — Media · Riesgo de UX
- **Evidencia:** al fallar `audio.play()` se establece `blocked` (`frontend/src/services/realtime-voice.ts:42-45`); el callback de avance solo se invoca si `output_audio_buffer.stopped` ocurre con `!this.blocked` (`:77-86`). En la transición, `showNext` depende de `onFinished` de la corrección (`frontend/src/pages/InterviewPage.tsx:326-354`).
- **Afecta:** si el navegador impide reproducción y la persona no pulsa «Reproducir audio», una respuesta parcial/incorrecta puede dejar la siguiente pregunta sin mostrarse, pese a que se anuncia continuación por texto.
- **Recomendación:** cuando la reproducción se bloquee, activar una ruta de avance textual con pausa controlada y cancelar la espera de audio; probar rechazo de autoplay durante corrección y transición.

### A-19 · La voz envía la pregunta antes de que su texto esté visible — Baja · Confirmado
- **Evidencia:** `speakParts` inicializa el texto mostrado como vacío e invoca enseguida `voice.current.speak(...)` (`frontend/src/pages/InterviewPage.tsx:213-219`); el texto avanza posteriormente por eventos/temporizador (`:182-211`). `RealtimeVoice.speak` envía la frase completa en `response.create` (`frontend/src/services/realtime-voice.ts:124-149`).
- **Afecta:** la descripción «solo el texto ya visible» de `AGENTS.md`/`README.md` es literalmente incorrecta durante la presentación gradual, aunque sea texto de pregunta/corrección ya disponible en la propia aplicación.
- **Recomendación:** aclarar la documentación como «texto que se presentará al usuario» o mostrarlo íntegro antes de enviar el audio si la visibilidad previa es un requisito estricto.

### A-20 · Healthcheck no detecta fallo de base ni de servicios de IA — Baja · Confirmado
- **Evidencia:** `backend/app/api/router.py:15-17` devuelve `{"status":"ok"}` sin verificar dependencias; `README.md:60` indica expresamente que no necesita DB.
- **Afecta:** un monitor que use exclusivamente `/health` puede declarar saludable una instancia incapaz de registrar cuentas o persistir entrevistas.
- **Recomendación:** conservar un endpoint ligero de *liveness* y añadir *readiness* separado con consulta de DB (y estado de configuración esencial), sin realizar llamadas de pago a OpenAI en cada sondeo.

## Frontend, arquitectura y consistencia

### A-21 · Dashboard anuncia entrevistas como futuras pese a estar implementadas — Media · Confirmado
- **Evidencia:** `frontend/src/pages/Dashboard.tsx:94-101` muestra «La simulación de entrevistas todavía está en preparación»; existen rutas funcionales a preparación, sesión e historial (`frontend/src/App.tsx:120-123`) y endpoints en `backend/app/modules/interviews/router.py`.
- **Afecta:** desinforma a los usuarios y dificulta descubrir una función ya disponible.
- **Recomendación:** conectar esa tarjeta con entrevistas recientes/reanudar la activa o usar un texto de acceso real al módulo.

### A-22 · La página de perfil promete una comparación aún pendiente — Media · Confirmado
- **Evidencia:** `frontend/src/pages/ProfilePage.tsx:195` afirma que el CV «se utilizará para comparar tu perfil ... y evaluar tu compatibilidad»; `/comparaciones` solo presenta `ModulePage` (`frontend/src/App.tsx:124-133`; `frontend/src/pages/ModulePage.tsx:3-12`) y el backend no incluye router de comparaciones (`backend/app/api/router.py:3-12`).
- **Afecta:** crea expectativas de feedback y porcentaje de compatibilidad que no están disponibles actualmente.
- **Recomendación:** aclarar que la comparación llegará en una iteración posterior; al implementarla, alinear interfaz y API antes de volver a prometer el resultado.

### A-23 · Estado de carga no termina con IDs de entrevista inválidos — Baja · Confirmado
- **Evidencia:** `InterviewSessionPage` e `InterviewResultPage` retornan temprano si el parámetro no es un entero positivo (`frontend/src/pages/InterviewPage.tsx:223-241`; `frontend/src/pages/InterviewHistoryPage.tsx:104-113`), sin ejecutar `setLoading(false)`.
- **Afecta:** la ruta inválida muestra un mensaje genérico por la condición del render, pero deja `loading` permanentemente verdadero y el estado interno inconsistente.
- **Recomendación:** validar el ID al inicio y pasar a un estado explícito de error, terminando la carga en todos los caminos.

### A-24 · Clientes HTTP repiten política de errores y base URL — Baja · Confirmado
- **Evidencia:** lógica `fetch`/`credentials`/JSON/errores duplicada en `frontend/src/services/auth.ts:30-60`, `profile.ts:3-14`, `vacancies.ts:1,31-39` e `interviews.ts:1,43-50`; `frontend/src/services/api.ts:1-9` tampoco se utiliza como cliente común.
- **Afecta:** variaciones de mensajes, manejo de expiración y timeouts inconsistentes cuando cambie la API; mayor esfuerzo de mantenimiento.
- **Recomendación:** concentrar base URL, parseo, errores y credenciales en una utilidad pequeña, preservando los mensajes especiales de formularios y las subidas multipart.

### A-25 · La interfaz no ofrece enlace de descarga del CV subido — Baja · Confirmado
- **Evidencia:** la API implementa `GET /profile/resumes/{resume_id}/download` (`backend/app/modules/profile/router.py:192-201`); las filas de CV en `frontend/src/pages/ProfilePage.tsx:204-210` solo presentan nombre, fecha, selección y ocultación.
- **Afecta:** la persona no puede aprovechar desde la UI la descarga privada ya implementada ni comprobar fácilmente el archivo conservado.
- **Recomendación:** añadir acción «Descargar PDF» para CV activos con el endpoint autenticado; probar permisos y nombre del archivo.

### A-26 · Constantes, endpoints de muestra y catálogos redundantes — Baja · Confirmado
- **Evidencia:** `frontend/src/features/modules.ts:9-15` lista rutas ya implementadas pero `frontend/src/App.tsx:124-133` filtra el catálogo para mostrar solo dos; `frontend/src/services/api.ts:3-9` contiene un cliente de salud que no es usado en el dashboard; `backend/app/db/models.py:1` sigue describiendo todo el esquema como inicial.
- **Afecta:** aumenta la distancia entre estructura y estado real del proyecto; dificulta identificar código operativo y código de andamiaje.
- **Recomendación:** limpiar o reutilizar las abstracciones que ya no aportan valor, y actualizar comentarios sin alterar funcionalidades.

## Cobertura y trabajo siguiente

### A-27 · Las pruebas no ejercitan la cadena real de migraciones ni concurrencia PostgreSQL — Media · Confirmado
- **Evidencia:** las pruebas crean tablas con `Base.metadata.create_all` en SQLite y adaptan `JSONB` para ese motor (`backend/tests/test_auth.py:20-29`; `backend/tests/test_interview_simulation.py:36-38,70-75`; `backend/tests/test_vacancies.py:32-41`). No se ejecuta `alembic upgrade head` sobre PostgreSQL en ellas; SQLite tampoco reproduce los bloqueos `with_for_update` de las rutas de CV (`backend/app/modules/profile/router.py:135-166`).
- **Afecta:** 49 pruebas verdes no prueban migraciones sobre datos preexistentes, índices parciales ni carreras concurrentes del motor de producción.
- **Recomendación:** agregar una suite de integración acotada con PostgreSQL/pgvector que actualice una DB desde migraciones, contraste esquema-modelos y pruebe carreras de CV principal e inicio/fin de entrevistas. Mantener las pruebas rápidas actuales para lógica de rutas.

### A-28 · No hay pruebas automatizadas de interacciones clave del navegador — Media · Confirmado
- **Evidencia:** `frontend/package.json:6-11` solo define `dev`, `build`, `lint` y `preview`; no existen pruebas frontend en `frontend/src`. La secuencia de voz/dictado, transiciones y cambio de cuenta reside en `frontend/src/pages/InterviewPage.tsx:139-473`.
- **Afecta:** lint y compilación no detectan bloqueos de autoplay, carreras de efectos ni desincronización de UI/API.
- **Recomendación:** añadir pruebas de comportamiento para flujos críticos (sin voz, voz bloqueada, cambiar cuenta, retomar entrevista, ocultación) con APIs del navegador simuladas; complementar con un recorrido manual móvil/escritorio.

## Orden sugerido para lo pendiente

1. **Antes de aplicar a datos reales:** inspeccionar registros incompatibles, respaldar y ejecutar `0011_audit_integrity`; comprobar con PostgreSQL la carrera entre dos peticiones de inicio.
2. **Antes de escalar:** A-01/A-03 (limitador compartido), A-11 (planes reales), A-12 (paginación completa) y A-14/A-17 (operación de archivos y PDF).
3. **Al ampliar funcionalidades:** A-05 (decisión de confianza en voz), A-09 (comparaciones), A-18/A-28 (pruebas de navegador), A-27 (datos legados).

**Límite de esta intervención:** no se hicieron llamadas a OpenAI real ni pruebas en navegador; se verificó una base PostgreSQL temporal vacía, no la principal ni su historial de datos. No se afirma explotación de un fallo de autorización entre usuarios en los endpoints privados existentes: las rutas revisadas sí filtran por `candidate_id` al consultar recursos.
