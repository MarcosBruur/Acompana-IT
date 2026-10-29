# Mockups de Acompañamiento laboral

Fuente: [archivo de Figma](https://www.figma.com/design/Uw6pgUZ1QNA6yE7c2ZOIyL/Acompa%C3%B1amiento-laboral).

| Pantalla                        | Nodo de Figma | Ruta local                            |
| ------------------------------- | ------------- | ------------------------------------- |
| Login                           | `5:5`         | `/sesion` (alias `/login`)            |
| Registro                        | `5:69`        | `/registro` (alias `/register`)       |
| Inicio                          | `7:4`         | `/`                                   |
| Mi currículum                   | `12:2`        | `/curriculum`                         |
| Analizar nueva vacante          | `16:2`        | `/vacantes` (alias `/vacantes/nueva`) |
| Análisis de ejemplo             | `18:2`        | `/vacantes/ejemplo/analisis`          |
| Simulación visual de entrevista | `21:2`        | `/entrevistas`                        |

Las vistas usan React, TypeScript, React Router y CSS, con componentes comunes en `src/components/Design.tsx`. Los SVG originales exportados de cada pantalla y las fuentes Outfit y Geist se sirven desde `public/figma/`, sin depender de URLs temporales de Figma. Los nombres de los SVG conservan la pantalla y el identificador de la exportación para rastrear su uso. Las tipografías proceden de Google Fonts; sus licencias están en el mismo directorio.

El diseño de escritorio toma como referencia frames de 1440 × 900. La composición se adapta a tablet y celular, con navegación superior en pantallas pequeñas, formularios apilados y tarjetas en una columna.

## Alcance de la maqueta

- El dashboard, los resultados y la entrevista contienen los datos de ejemplo de los diseños; no son datos del candidato ni resultados calculados.
- Login y registro validan campos y permiten mostrar/ocultar contraseñas. El registro aplica mínimo 8 caracteres, mayúscula, número, carácter especial y confirmación coincidente. No se crean cuentas, sesiones ni tokens. Google, renovación y recuperación de contraseña están pendientes.
- El CV se selecciona con botón o arrastrando un archivo. Se revisan extensión, MIME, máximo 5 MB y cabecera `%PDF-` para la vista previa local; estas comprobaciones no reemplazan la validación y autorización futuras en backend. Solo se retienen nombre y fecha en memoria. No se sube ni persiste el archivo.
- La oferta se ingresa como texto plano. El envío del formulario muestra el estado pendiente de integración. El análisis estático se abre mediante un enlace explícito al ejemplo, sin atribuirlo al texto ingresado. El formulario y el ejemplo son accesibles sin autenticación; no existe persistencia anónima.
- La entrevista reproduce la pantalla de voz. Silenciar cambia el estado visual; no se solicita acceso al micrófono ni se graba audio. Finalizar requiere confirmación, permite volver y no genera puntuación ni feedback.
- Comparaciones y aprendizaje conservan sus marcadores, porque el archivo no contiene mockups de esas pantallas.

## Verificación

Desde `frontend/`: `npm run lint`, `npm run build` y `npm run dev`.

Recorrer las siete rutas a 1440 px y en móvil, verificar que no haya desbordamiento horizontal ni imágenes sin cargar, probar validación de formularios, mostrar contraseñas, selección/reemplazo de PDF y cancelación/confirmación de cierre de entrevista. El pie de cada vista identifica el alcance de la maqueta.

Verificación realizada el 29 de octubre de 2026: build y lint correctos; revisión visual de las siete pantallas en escritorio y móvil; sin desbordamiento horizontal a 320, 390, 768 y 1440 px. Se probaron contraseña débil, confirmaciones distintas y formulario válido; rechazo de cabecera PDF falsa y selección local de un archivo con cabecera PDF; envío de vacante sin ejecutar análisis; silencio visual y ambos caminos del diálogo de finalización. Estas comprobaciones de interfaz no prueban servicios del backend.
