import { expect, test } from '@playwright/test'

test('el visitante ve las opciones antes de abrir el perfil', async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill({ status: 401, json: { detail: 'Sin sesión' } }))

  await page.goto('/')
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('link', { name: 'Perfil' }).click()
  const dialog = page.getByRole('dialog', { name: 'Accedé a tu perfil' })
  await expect(page).toHaveURL(/\/$/)
  await expect(dialog).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Perfil', exact: true })).toHaveCount(0)
  await expect(dialog.getByRole('link', { name: 'Crear cuenta' })).toBeVisible()
  await expect(dialog.getByRole('link', { name: 'Iniciar sesión' })).toBeVisible()

  await dialog.getByRole('link', { name: 'Crear cuenta' }).click()
  await expect(page).toHaveURL(/\/registro$/)

  await page.goto('/')
  await page.getByRole('link', { name: 'Ir a perfil de visitante' }).click()
  await expect(page).toHaveURL(/\/$/)
  await dialog.getByRole('link', { name: 'Iniciar sesión' }).click()
  await expect(page).toHaveURL(/\/sesion$/)

  await page.goto('/perfil')
  await expect(page).toHaveURL(/\/$/)
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Volver' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page).toHaveURL(/\/$/)
})

test('el candidato autenticado abre su perfil sin diálogo', async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill({ json: {
    id: 1, email: 'ana@example.com', first_name: 'Ana', last_name: 'Prueba',
    nickname: null, avatar_url: null, password_expired: false, role: 'candidato',
  } }))
  await page.route('**/api/v1/profile/resumes*', route => route.fulfill({ json: [] }))
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Navegación principal' }).getByRole('link', { name: 'Perfil' }).click()
  await expect(page).toHaveURL(/\/perfil$/)
  await expect(page.getByRole('heading', { name: 'Perfil', exact: true })).toBeVisible()
  await expect(page.getByRole('dialog', { name: 'Accedé a tu perfil' })).toHaveCount(0)
})
