# Frontend

Aplicación React + TypeScript generada con Vite. Consultá el `README.md` de la raíz para iniciarla junto al backend.

Las rutas iniciales de `src/features/modules.ts` corresponden a los módulos del TFG. Se implementaron las siete vistas de los mockups de Figma como una maqueta navegable y responsive; auth, persistencia, análisis por IA y audio siguen pendientes. Consultá `FIGMA.md` para el mapa de pantallas, las interacciones locales y los límites de la vista previa.

Tailwind CSS se integra mediante el plugin de Vite y se carga desde `src/index.css`. Podés usar clases utilitarias directamente en los componentes (por ejemplo, `className="flex gap-4"`). Los estilos existentes de `src/App.css` están en la capa `components`, por lo que las utilidades pueden sobrescribirlos cuando sea necesario.
