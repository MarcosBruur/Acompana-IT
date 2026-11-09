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
  mode: InterviewMode
  correct_count: number
  partial_count: number
  incorrect_count: number
  unanswered_count: number
  resources: { title: string; url: string }[]
  questions: InterviewQuestion[]
}

export type InterviewMode = 'conversation' | 'multiple_choice'
export type InterviewQuestion = {
  id: number
  position: number
  topic: string | null
  question: string
  options: string[] | null
  answer: string | null
  verdict: 'correcta' | 'parcial' | 'incorrecta' | null
  explanation: string | null
  correct_index: number | null
}
export type InterviewSession = {
  id: number
  vacancy_title: string
  mode: InterviewMode
  status: 'in_progress'
  using_resume: boolean
  questions: InterviewQuestion[]
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
export const getActiveInterview = () => request<InterviewSession | null>('/active')
export const getInterviewSession = (id: number) => request<InterviewSession>(`/${id}/session`)
export const startInterview = (data: { vacancy_id: number; mode: InterviewMode; use_resume: boolean }) =>
  request<InterviewSession>('', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
export const saveInterviewChoice = (id: number, questionId: number, selected_index: number | null) =>
  request<InterviewSession>(`/${id}/questions/${questionId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ selected_index }) })
export const sendInterviewAnswer = (id: number, questionId: number, answer: string) =>
  request<InterviewSession>(`/${id}/questions/${questionId}/answer`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answer }) })
export const finishInterview = (id: number) => request<InterviewResult>(`/${id}/finish`, { method: 'POST' })
export const cancelInterview = (id: number) => request<void>(`/${id}/cancel`, { method: 'POST' })
export const getInterviewVoiceToken = (id: number) => request<{ value: string }>(`/${id}/voice-token`, { method: 'POST' })
