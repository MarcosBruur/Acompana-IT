import { expect, test } from '@playwright/test'

const candidate = {
  id: 1, email: 'ana@example.com', first_name: 'Ana', last_name: 'Prueba',
  nickname: null, avatar_url: null, password_expired: false, role: 'candidato',
}

test('los historiales paginados permiten consultar más vacantes', async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill({ json: candidate }))
  await page.route('**/api/v1/vacancies?*', route => {
    const before = new URL(route.request().url()).searchParams.get('before')
    const ids = before ? [2, 1] : Array.from({ length: 20 }, (_, index) => 22 - index)
    return route.fulfill({ json: ids.map(id => ({
      id, title: `Oferta ${id}`, company: null, created_at: '2026-11-09T12:00:00Z', risk_percentage: 0,
    })) })
  })
  await page.goto('/vacantes')
  await expect(page.getByRole('listitem')).toHaveCount(20)
  await page.getByRole('button', { name: 'Ver más vacantes' }).click()
  await expect(page.getByRole('listitem')).toHaveCount(22)
  await expect(page.getByRole('button', { name: 'Ver más vacantes' })).toHaveCount(0)
})

test('si el navegador bloquea el audio la corrección avanza por texto', async ({ page }) => {
  await page.addInitScript(() => {
    // Simula una política de autoplay que impide arrancar AudioContext.
    const blocked = class {
      state = 'suspended'
      currentTime = 0
      destination = {}
      resume() { return Promise.reject(new Error('Autoplay bloqueado')) }
      close() { return Promise.resolve() }
      createBuffer(_channels: number, length: number) {
        return { duration: length / 24000, getChannelData: () => new Float32Array(length) }
      }
      createBufferSource() {
        return { buffer: null, onended: null, connect() {}, start() {}, stop() {} }
      }
    }
    Object.defineProperty(window, 'AudioContext', { value: blocked })
  })
  await page.route('**/api/v1/auth/me', route => route.fulfill({ json: candidate }))
  const questions = [
    { id: 1, position: 1, topic: 'Python', question: '¿Qué es Python?', options: null, answer: null, verdict: null, explanation: null, correct_index: null },
    { id: 2, position: 2, topic: 'SQL', question: '¿Qué es SQL?', options: null, answer: null, verdict: null, explanation: null, correct_index: null },
  ]
  const initial = { id: 11, vacancy_title: 'Desarrollo', mode: 'conversation', status: 'in_progress', using_resume: false, questions }
  await page.route('**/api/v1/interviews/11/session', route => route.fulfill({ json: initial }))
  await page.route('**/api/v1/interviews/11/questions/1/answer', route => route.fulfill({ json: {
    ...initial, questions: [{ ...questions[0], answer: 'No sé', verdict: 'incorrecta', explanation: 'Repasá los fundamentos de Python.' }, questions[1]],
  } }))
  const spoken: string[][] = []
  await page.routeWebSocket('**/api/v1/interviews/11/voice', ws => {
    ws.send(JSON.stringify({ type: 'ready' }))
    ws.onMessage(message => {
      const payload = JSON.parse(message.toString()) as { type: string; keys?: string[] }
      if (payload.type !== 'speak') return
      spoken.push(payload.keys ?? [])
      if (payload.keys?.includes('e-1')) ws.send(JSON.stringify({ type: 'audio', delta: 'AAAAAA==' }))
      ws.send(JSON.stringify({ type: 'done', failed: false }))
    })
  })
  await page.goto('/entrevistas/11/simulacion')
  await page.getByRole('textbox', { name: 'Escribí o dictá tu respuesta' }).fill('No sé')
  await page.getByRole('button', { name: 'Enviar respuesta' }).click()
  await expect(page.getByText('¿Qué es SQL?')).toBeVisible({ timeout: 15000 })
  expect(spoken.some(keys => keys.includes('e-1'))).toBeTruthy()
  await expect(page.getByText(/bloqueó el audio/i)).toBeVisible()
})
