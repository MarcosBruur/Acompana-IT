import type { Candidate } from './auth'

const BASE = import.meta.env.VITE_API_URL ?? '/api/v1'

export type Resume = { id: number; filename: string; uploaded_at: string; is_primary: boolean }

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}/profile${path}`, { credentials: 'include', ...options })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : 'No se pudo completar la solicitud.')
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}

export const listResumes = () => request<Resume[]>('/resumes')
export const selectPrimary = (id: number) => request<Resume>(`/resumes/${id}/primary`, { method: 'PATCH' })
export const hideResume = (id: number) => request<void>(`/resumes/${id}/hide`, { method: 'PATCH' })
export const saveNickname = (nickname: string) => request<Candidate>('', {
  method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nickname }),
})
export function uploadFile<T extends Candidate | Resume>(path: '/avatar' | '/resumes', file: File): Promise<T> {
  const form = new FormData()
  form.append('file', file)
  return request<T>(path, { method: 'POST', body: form })
}

export async function validatePdf(file: File) {
  if (!file.name.toLowerCase().endsWith('.pdf') || file.type !== 'application/pdf' || file.size > 5 * 1024 * 1024 || !file.size) {
    throw new Error('Seleccioná un PDF de hasta 5 MB.')
  }
  if ((await file.slice(0, 5).text()) !== '%PDF-') throw new Error('El archivo no tiene una cabecera PDF válida.')
}
