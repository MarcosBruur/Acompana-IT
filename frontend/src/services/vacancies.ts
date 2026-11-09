const BASE = import.meta.env.VITE_API_URL ?? '/api/v1'

export type Finding = {
  title: string
  explanation: string
  relevance: 'alta' | 'media' | 'baja'
  evidence: string
}
export type VacancyResult = {
  id: number | null
  title: string
  company: string | null
  created_at: string | null
  seniority: string
  experience_required: string
  technologies: string[]
  required_skills: string[]
  responsibilities: string[]
  summary: string
  inconsistencies: Finding[]
  risk_signals: Finding[]
  risk_percentage: number
}
export type VacancySummary = Pick<VacancyResult, 'id' | 'title' | 'company' | 'created_at' | 'risk_percentage'> & { id: number; created_at: string; risk_percentage: number | null }

// La oferta anónima vive solo en memoria: ni PostgreSQL, ni sessionStorage, ni history.state.
let transientAnalysis: VacancyResult | null = null
export function setTransientAnalysis(result: VacancyResult) { transientAnalysis = result }
export function getTransientAnalysis() { return transientAnalysis }

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}/vacancies${path}`, { ...options, credentials: 'include' })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const detail = body.detail
    throw new Error(typeof detail === 'string' ? detail : 'No se pudo completar el análisis. Intentá de nuevo.')
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}

export function analyzeVacancy(data: { title: string; company: string | null; description: string }) {
  return request<VacancyResult>('/analyze', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
    signal: AbortSignal.timeout(45000),
  })
}
export const getVacancy = (id: number) => request<VacancyResult>(`/${id}`)
export const getVacancies = () => request<VacancySummary[]>('')
export const hideVacancy = (id: number) => request<void>(`/${id}/hide`, { method: 'PATCH' })
