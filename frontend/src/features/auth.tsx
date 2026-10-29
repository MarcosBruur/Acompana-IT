import { useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { authRequest, type Candidate } from '../services/auth'
import { AuthContext } from './auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const [candidate, setCandidate] = useState<Candidate | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    authRequest<Candidate>('/me')
      .then((result) => {
        if (!active) return
        setCandidate(result)
        const destination = sessionStorage.getItem('auth_return_to')
        sessionStorage.removeItem('auth_return_to')
        if (destination === '/comparaciones' || destination === '/entrevistas') navigate(destination, { replace: true })
      })
      .catch(() => { if (active) setCandidate(null) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [navigate])

  async function logout() {
    await authRequest<void>('/logout', { method: 'POST' })
    setCandidate(null)
  }

  return (
    <AuthContext.Provider value={{ candidate, loading, setCandidate, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
