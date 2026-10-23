const API_BASE_URL = import.meta.env.VITE_API_URL ?? '/api/v1'

export type HealthResponse = { status: string }

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`)
  if (!response.ok) throw new Error('La API no respondió correctamente')
  return response.json() as Promise<HealthResponse>
}
