import { expect, test } from '@playwright/test'

test('el visitante elige registrarse o iniciar sesión antes de entrar a entrevistas', async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill({ status: 401, json: { detail: 'Sin sesión' } }))
  const dialog = page.getByRole('dialog', { name: 'Accedé a las entrevistas' })

  await page.goto('/')
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('link', { name: 'Simular Entrevista' }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(dialog).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Simular entrevista', exact: true })).toHaveCount(0)
  await dialog.getByRole('link', { name: 'Crear cuenta' }).click()
  await expect(page).toHaveURL(/\/registro$/)

  await page.goto('/')
  await page.getByRole('link', { name: 'Iniciar simulación' }).click()
  await expect(page).toHaveURL(/\/$/)
  await dialog.getByRole('link', { name: 'Iniciar sesión' }).click()
  await expect(page).toHaveURL(/\/sesion$/)

  await page.goto('/entrevistas/nueva')
  await expect(page).toHaveURL(/\/$/)
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Volver' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByText(/algunas vistas aún contienen datos de ejemplo/i)).toHaveCount(0)
})
