export const API_BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1'

export class ApiRequestError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === 'string' ? detail : fallback)
    this.status = status
    this.detail = detail
  }
}

export async function apiRequest<T>(path: string, options?: RequestInit, fallback = 'No se pudo completar la solicitud. Intentá de nuevo.'): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { credentials: 'include', ...options })
  if (!response.ok) {
    const body: { detail?: unknown } = await response.json().catch(() => ({}))
    throw new ApiRequestError(response.status, body.detail, fallback)
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}
