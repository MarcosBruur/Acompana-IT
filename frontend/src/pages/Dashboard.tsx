import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Asset, Header } from '../components/Design'
import { useAuth } from '../features/auth-context'
import { getVacancies, type VacancySummary } from '../services/vacancies'

export function Dashboard() {
  const { candidate } = useAuth()
  const [recent, setRecent] = useState<VacancySummary[]>([])
  useEffect(() => {
    if (!candidate || candidate.password_expired) return
    let active = true
    getVacancies().then((items) => { if (active) setRecent(items.slice(0, 3)) }).catch(() => {})
    return () => { active = false }
  }, [candidate])
  const cards = [
    {
      title: 'Analizar vacante',
      description:
        'Pegá la descripción de un puesto para identificar requisitos y posibles alertas de la oferta.',
      action: 'Comenzar análisis',
      icon: 'imgSearch',
      to: '/vacantes',
    },
    {
      title: 'Comparar curriculum-vacante',
      description:
        'Obtén feedback impulsado por IA para mejorar tus habilidades acorde con una vacante de interés',
      action: 'Comenzar comparación',
      icon: 'imgFile1',
      to: '/comparaciones',
    },
    {
      title: 'Practicar entrevista',
      description:
        'Entrena con un simulador interactivo adaptado a tu perfil y la vacante a la que aplicas',
      action: 'Iniciar simulación',
      icon: 'imgMic',
      to: '/entrevistas',
    },
  ]
  return (
    <>
      <Header title={`Bienvenido${candidate ? `, ${candidate.nickname || candidate.first_name}` : ''}`} screen="dashboard" />
      <div className="action-cards">
        {cards.map((card, i) => (
          <article className="action-card" key={card.title}>
            <div
              className={i === 0 ? 'icon-badge primary-badge' : 'icon-badge'}
            >
              <Asset screen="dashboard" name={card.icon} />
            </div>
            <h2>{card.title}</h2>
            <p>{card.description}</p>
            <Link className="card-action" to={card.to}>
              {card.action}
              <Asset screen="dashboard" name="imgChevronRight" />
            </Link>
          </article>
        ))}
      </div>
      <div className="dashboard-split">
        <section>
          <h2 className="section-title">Vacantes analizadas recientemente</h2>
          <div className="jobs-list">
            {recent.map((vacancy) => (
              <Link
                className="job-row"
                key={vacancy.id}
                to={`/vacantes/${vacancy.id}/analisis`}
              >
                <div>
                  <h3>{vacancy.title}</h3>
                  <p>{vacancy.company || 'Empresa no indicada'}</p>
                </div>
                <div className="job-match">
                  <span className="pill cyan">
                    {vacancy.risk_percentage ?? 0}% Riesgo orientativo
                  </span>
                  <span className="muted">
                    {new Date(vacancy.created_at).toLocaleDateString('es-AR')}
                  </span>
                </div>
              </Link>
            ))}
            {!recent.length && <p>Los análisis que guardes aparecerán aquí. <Link to="/vacantes">Analizar una vacante</Link></p>}
          </div>
        </section>
        <section className="interviews-card">
          <h2>Entrevistas recientes</h2>
          <p>Historial de tus sesiones de simulación IA</p>
          <div className="interviews-list">
            {[
              'Entrevista técnica - React',
              'Introducción de Fit Cultural',
              'Algoritmos y Estructuras',
            ].map((title, i) => (
              <Link className="interview-row" key={title} to="/entrevistas">
                <div>
                  <h3>{title}</h3>
                  <span className={i < 2 ? 'pill green' : 'pill neutral'}>
                    {['Score: 8.5/10', 'Score: 9.0/10', 'Por revisar'][i]}
                  </span>
                </div>
                <div>
                  <span>
                    {
                      [
                        'Simulación de Rol Sr.',
                        'Práctica general',
                        'Práctica técnica',
                      ][i]
                    }
                  </span>
                  <span className="muted">
                    {
                      ['Hace un día, 18:30', 'Ene 14, 15:00', 'Ene 10, 11:20'][
                        i
                      ]
                    }
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </>
  )
}
