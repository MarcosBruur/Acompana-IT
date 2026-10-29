import { createContext, useContext } from 'react'
import type { Candidate } from '../services/auth'

export type AuthState = {
  candidate: Candidate | null
  loading: boolean
  setCandidate: (candidate: Candidate | null) => void
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider no configurado')
  return value
}
