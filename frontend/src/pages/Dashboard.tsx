import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { modules } from '../features/modules'
import { getHealth } from '../services/api'

export function Dashboard() {
  const [apiStatus, setApiStatus] = useState('Comprobando conexión…')

  useEffect(() => {
    getHealth()
      .then(() => setApiStatus('API conectada'))
      .catch(() => setApiStatus('API desconectada: iniciá el backend para conectarla'))
  }, [])

  return (
    <>
      <span className="eyebrow">Plataforma de acompañamiento</span>
      <h1>Tu carrera en tecnología comienza aquí</h1>
      <p>Un espacio para entender oportunidades laborales, reconocer tus fortalezas y prepararte para entrevistas técnicas.</p>
      <p className="status" role="status">{apiStatus}</p>
      <div className="cards">
        {modules.map((module) => (
          <Link className="card" key={module.path} to={module.path}>
            <h2>{module.label}</h2>
            <p>{module.description}</p>
            <strong>Explorar →</strong>
          </Link>
        ))}
      </div>
    </>
  )
}
