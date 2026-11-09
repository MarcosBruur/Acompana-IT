import { API_BASE_URL, ApiRequestError, apiRequest } from './api'

export type Candidate = {
  id: number
  email: string
  first_name: string
  last_name: string
  nickname: string | null
  avatar_url: string | null
  password_expired: boolean
  role: 'candidato'
}

export function googleLoginUrl() {
  return `${API_BASE_URL}/auth/google`
}

export class AuthRequestError extends Error {
  status: number
  fieldErrors: Record<string, string>

  constructor(message: string, status: number, fieldErrors: Record<string, string> = {}) {
    super(message)
    this.name = 'AuthRequestError'
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

export async function authRequest<T>(path: string, options?: RequestInit): Promise<T> {
  try {
    return await apiRequest<T>(`/auth${path}`, {
      ...options, headers: { 'Content-Type': 'application/json', ...options?.headers },
    })
  } catch (error) {
    if (!(error instanceof ApiRequestError)) throw error
    const detail = error.detail
    if (Array.isArray(detail)) {
      const fieldErrors: Record<string, string> = {}
      for (const item of detail) {
        const field = item?.loc?.at(-1)
        if (typeof field !== 'string' || typeof item?.msg !== 'string') continue
        if (item.type === 'missing' || item.type === 'string_too_short') {
          fieldErrors[field] = 'Este campo es obligatorio.'
        } else if (field === 'email') {
          fieldErrors[field] = 'Ingresá un correo electrónico válido.'
        } else if (item.type === 'string_too_long') {
          fieldErrors[field] = field === 'password' || field === 'new_password'
            ? 'La contraseña supera la longitud permitida.' : 'Ingresá hasta 100 caracteres.'
        } else {
          fieldErrors[field] = item.msg.replace(/^Value error, /, '')
        }
      }
      throw new AuthRequestError('Revisá los campos marcados.', error.status, fieldErrors)
    }
    throw new AuthRequestError(error.message, error.status)
  }
}
