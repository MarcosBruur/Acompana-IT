export type PlatformModule = {
  path: string
  label: string
  description: string
  stories: string
}

// Únicamente los módulos que aún muestran una vista de preparación.
export const modules: PlatformModule[] = [
  { path: '/comparaciones', label: 'Comparar perfil', description: 'Coincidencias y brechas entre CV y vacante.', stories: 'HU-009 y HU-010' },
  { path: '/aprendizaje', label: 'Aprendizaje', description: 'Recursos para reforzar competencias, preferentemente gratuitos.', stories: 'HU-011' },
]
