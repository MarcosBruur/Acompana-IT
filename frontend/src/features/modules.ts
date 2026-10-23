export type PlatformModule = {
  path: string
  label: string
  description: string
  stories: string
}

// Cada ruta es un punto de entrada para implementar el módulo correspondiente.
export const modules: PlatformModule[] = [
  { path: '/sesion', label: 'Mi cuenta', description: 'Registro, inicio de sesión y perfil del candidato.', stories: 'HU-002 a HU-004' },
  { path: '/curriculum', label: 'Mi currículum', description: 'Carga de CV en formato PDF (máximo 5 MB).', stories: 'HU-005' },
  { path: '/vacantes', label: 'Mis vacantes', description: 'Carga de texto, análisis de requisitos y señales de riesgo.', stories: 'HU-006 a HU-008' },
  { path: '/comparaciones', label: 'Comparar perfil', description: 'Coincidencias y brechas entre CV y vacante.', stories: 'HU-009 y HU-010' },
  { path: '/aprendizaje', label: 'Aprendizaje', description: 'Recursos para reforzar competencias, preferentemente gratuitos.', stories: 'HU-011' },
  { path: '/entrevistas', label: 'Entrevistas', description: 'Simulación técnica y feedback de desempeño.', stories: 'HU-012 y HU-013' },
]
