const BASE = import.meta.env.VITE_API_URL ?? '/api/v1'

export type InterviewSummary = {
  id: number
  vacancy_title: string
  created_at: string
  score: number
}

export type InterviewResult = InterviewSummary & {
  feedback: string | null
  skills_to_improve: string[]
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}/interviews${path}`, { ...options, credentials: 'include' })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : 'No se pudo completar la solicitud. Intentá de nuevo.')
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}

export const getInterviews = () => request<InterviewSummary[]>('')
export const getInterview = (id: number) => request<InterviewResult>(`/${id}`)
export const hideInterview = (id: number) => request<void>(`/${id}/hide`, { method: 'PATCH' })
