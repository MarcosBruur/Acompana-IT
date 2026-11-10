import { expect, test } from '@playwright/test'

test('cancelar la entrevista activa requiere confirmar en el diálogo del sitio', async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill({ json: {
    id: 1, email: 'ana@example.com', first_name: 'Ana', last_name: 'Prueba',
    nickname: null, avatar_url: null, password_expired: false, role: 'candidato',
  } }))
  await page.route('**/api/v1/vacancies?*', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/profile/resumes?*', route => route.fulfill({ json: [] }))
  await page.route('**/api/v1/interviews/active', route => route.fulfill({ json: {
    id: 12, vacancy_title: 'Desarrollo frontend', mode: 'conversation',
    status: 'in_progress', using_resume: false, questions: [],
  } }))
  let cancellations = 0
  await page.route('**/api/v1/interviews/12/cancel', route => {
    cancellations++
    return route.fulfill({ status: 204, body: '' })
  })

  await page.goto('/entrevistas/nueva')
  await expect(page.getByRole('heading', { name: 'Tenés una entrevista en curso' })).toBeVisible()
  await page.getByRole('button', { name: 'Cancelar y empezar otra' }).click()
  const dialog = page.getByRole('dialog', { name: '¿Cancelar la entrevista en curso?' })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Volver' }).click()
  await expect(dialog).toHaveCount(0)
  expect(cancellations).toBe(0)
  await expect(page.getByRole('heading', { name: 'Tenés una entrevista en curso' })).toBeVisible()

  await page.getByRole('button', { name: 'Cancelar y empezar otra' }).click()
  await dialog.getByRole('button', { name: 'Sí, cancelar y empezar otra' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Elegí una vacante' })).toBeVisible()
  expect(cancellations).toBe(1)
})
