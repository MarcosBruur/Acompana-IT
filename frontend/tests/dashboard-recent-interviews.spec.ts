import { expect, test } from '@playwright/test'

const candidate = {
  id: 1, email: 'ana@example.com', first_name: 'Ana', last_name: 'Prueba',
  nickname: null, avatar_url: null, password_expired: false, role: 'candidato',
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill({ json: candidate }))
  await page.route('**/api/v1/vacancies?*', route => route.fulfill({ json: [] }))
})

test('el dashboard muestra entrevistas completadas con nota y acceso al resultado', async ({ page }) => {
  await page.route('**/api/v1/interviews?*', route => route.fulfill({ json: [
    { id: 12, vacancy_title: 'Desarrollador/a frontend', score: 85, created_at: '2026-11-09T12:00:00Z' },
    { id: 11, vacancy_title: 'Analista de datos', score: 70, created_at: '2026-11-08T12:00:00Z' },
  ] }))

  await page.goto('/')
  const section = page.getByRole('heading', { name: 'Entrevistas recientes' }).locator('..')
  await expect(section.getByRole('link', { name: /Desarrollador\/a frontend/ })).toHaveAttribute('href', '/entrevistas/12')
  await expect(section.getByText('85/100')).toBeVisible()
  await expect(section.getByText('Analista de datos')).toBeVisible()
  await expect(section.getByText('Tu práctica empieza acá')).toHaveCount(0)
})

test('un fallo al cargar entrevistas no se presenta como historial vacío', async ({ page }) => {
  await page.route('**/api/v1/interviews?*', route => route.fulfill({ status: 503, json: { detail: 'Servicio temporalmente no disponible.' } }))

  await page.goto('/')
  const section = page.getByRole('heading', { name: 'Entrevistas recientes' }).locator('..')
  await expect(section.getByRole('alert')).toContainText('No se pudieron cargar las entrevistas recientes.')
  await expect(section.getByText('Tu práctica empieza acá')).toHaveCount(0)
})
