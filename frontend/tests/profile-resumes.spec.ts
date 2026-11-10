import { expect, test } from '@playwright/test'

test('los CV comparten listado y el cambio de principal requiere confirmación', async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill({ json: {
    id: 1, email: 'ana@example.com', first_name: 'Ana', last_name: 'Prueba',
    nickname: null, avatar_url: null, password_expired: false, role: 'candidato',
  } }))
  await page.route('**/api/v1/profile/resumes?*', route => route.fulfill({ json: [
    { id: 2, filename: 'nuevo.pdf', uploaded_at: '2026-11-09T12:00:00Z', is_primary: false },
    { id: 1, filename: 'anterior.pdf', uploaded_at: '2026-11-08T12:00:00Z', is_primary: true },
  ] }))
  let changes = 0
  await page.route('**/api/v1/profile/resumes/2/primary', route => {
    changes++
    return route.fulfill({ json: { id: 2, filename: 'nuevo.pdf', uploaded_at: '2026-11-09T12:00:00Z', is_primary: true } })
  })

  await page.goto('/perfil')
  const cards = page.locator('.profile-cv-card')
  await expect(page.getByRole('heading', { name: 'Mis currículums' })).toBeVisible()
  await expect(cards).toHaveCount(2)
  await expect(cards.nth(1).getByText('Principal')).toBeVisible()

  await cards.first().hover()
  await expect(cards.first()).toHaveCSS('border-color', 'rgb(142, 181, 160)')
  await cards.first().getByRole('link', { name: 'Descargar PDF' }).hover()
  await expect(page.getByRole('dialog', { name: '¿Establecer como principal?' })).toHaveCount(0)
  await cards.first().getByRole('button', { name: 'Eliminar currículum nuevo.pdf' }).click()
  await expect(page.getByRole('dialog', { name: '¿Eliminar currículum del perfil?' })).toBeVisible()
  await page.getByRole('dialog').getByRole('button', { name: 'Volver' }).click()

  await cards.first().getByRole('button', { name: 'Establecer nuevo.pdf como currículum principal' }).click()
  const dialog = page.getByRole('dialog', { name: '¿Establecer como principal?' })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Volver' }).click()
  expect(changes).toBe(0)
  await cards.first().getByRole('button', { name: 'Establecer nuevo.pdf como currículum principal' }).click()
  await dialog.getByRole('button', { name: 'Sí, establecer como principal' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(cards.first().getByText('Principal')).toBeVisible()
  await expect(cards.nth(1).getByText('Principal')).toHaveCount(0)
  expect(changes).toBe(1)

  await page.setViewportSize({ width: 375, height: 812 })
  const cardBox = await cards.first().boundingBox()
  const badgeBox = await cards.first().getByText('Principal').boundingBox()
  expect(cardBox).not.toBeNull()
  expect(badgeBox).not.toBeNull()
  expect(badgeBox!.y).toBeLessThan(cardBox!.y)
  expect(badgeBox!.x + badgeBox!.width).toBeLessThanOrEqual(cardBox!.x + cardBox!.width)
})
