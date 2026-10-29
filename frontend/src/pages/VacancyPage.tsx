import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Header, Modal } from '../components/Design'

export function VacancyPage() {
  const [message, setMessage] = useState(false)
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setMessage(true)
  }
  return (
    <>
      <Header title="Analizar nueva vacante" screen="vacancy" />
      <div className="vacancy-content">
        <p className="intro">
          Pegá la oferta laboral para conocer qué busca la empresa antes de
          postularte.
        </p>
        <form className="panel vacancy-form" onSubmit={submit}>
          <h2>Datos de la vacante</h2>
          <div className="two-fields">
            <label className="field">
              Título de la vacante
              <input
                name="title"
                required
                maxLength={200}
                placeholder="Ej.: Desarrollador/a Frontend React"
              />
            </label>
            <label className="field">
              Empresa (opcional)
              <input
                name="company"
                maxLength={200}
                placeholder="Ej.: Nombre de la empresa"
              />
            </label>
          </div>
          <label className="field">
            Descripción completa de la oferta
            <textarea
              name="description"
              required
              maxLength={20000}
              placeholder="Pegá aquí la descripción completa de la vacante, incluyendo responsabilidades, requisitos y beneficios…"
            />
          </label>
          <div className="analysis-explanation">
            <strong>¿Qué vamos a analizar?</strong>
            <p>
              Requisitos, tecnologías, experiencia, seniority y posibles señales
              de riesgo de la oferta.
            </p>
          </div>
          <div className="form-actions">
            <p className="helper">
              Completá el título y la descripción para iniciar el análisis.
            </p>
            <button className="primary" type="submit">
              Analizar vacante
            </button>
          </div>
        </form>
        <Link className="example-link" to="/vacantes/ejemplo/analisis">
          Ver el análisis de ejemplo del mockup
        </Link>
      </div>
      {message && (
        <Modal
          title="Análisis pendiente de integración"
          onClose={() => setMessage(false)}
        >
          <p>
            El formulario es válido. El servicio de análisis todavía no está
            implementado; tu texto no se envió ni se guardó.
          </p>
          <Link className="primary" to="/vacantes/ejemplo/analisis">
            Ver análisis de ejemplo
          </Link>
        </Modal>
      )}
    </>
  )
}
export function AnalysisPage() {
  return (
    <>
      <Header title="Análisis de vacante" screen="analysis" />
      <div className="analysis-content">
        <h2 className="vacancy-title">Desarrollador/a Frontend React</h2>
        <div className="result-grid">
          <section className="panel result-card">
            <h2>Seniority detectado</h2>
            <strong className="result-value">Semi Senior</strong>
          </section>
          <section className="panel result-card">
            <h2>Experiencia requerida</h2>
            <strong className="result-value">3+ años</strong>
          </section>
          <section className="panel result-card">
            <h2>Tecnologías</h2>
            <div className="tags">
              {['React', 'TypeScript', 'Git'].map((tag) => (
                <span key={tag}>{tag}</span>
              ))}
            </div>
            <p>HTML · CSS · APIs REST · Testing</p>
          </section>
          <section className="panel result-card">
            <h2>Competencias requeridas</h2>
            <ul>
              <li>Comunicación y trabajo en equipo</li>
              <li>Resolución de problemas</li>
              <li>Autonomía y atención al detalle</li>
              <li>Manejo de hooks</li>
              <li>Apoyo con herramientas de generación de código</li>
            </ul>
          </section>
          <section className="panel result-card">
            <h2>Responsabilidades</h2>
            <ul>
              <li>Desarrollar interfaces con React</li>
              <li>Integrar APIs y escribir pruebas</li>
              <li>Colaborar con Diseño y Backend</li>
            </ul>
          </section>
          <section className="panel result-card">
            <h2>Resumen</h2>
            <p>
              Rol frontend orientado a producto, con foco en React y calidad de
              código. Requiere autonomía y colaboración con un equipo
              multidisciplinario.
            </p>
          </section>
        </div>
        <section className="risk-panel">
          <h2>Inconsistencias y señales de riesgo</h2>
          <p>Puntos a validar con la empresa antes de avanzar en el proceso.</p>
          <div className="risk-row">
            <div>
              <h3>Seniority inconsistente</h3>
              <p>
                La oferta se presenta como Junior, pero exige 3+ años de
                experiencia y autonomía.
              </p>
            </div>
            <span className="pill red">Relevancia alta</span>
          </div>
          <div className="risk-row">
            <div>
              <h3>Disponibilidad fuera de horario</h3>
              <p>
                Se mencionan guardias ocasionales sin detallar frecuencia ni
                compensación.
              </p>
            </div>
            <span className="pill amber">Relevancia media</span>
          </div>
        </section>
        <div className="analysis-actions">
          <Link className="secondary" to="/vacantes">
            Volver a mis vacantes
          </Link>
          <Link className="primary" to="/comparaciones">
            Comparar con mi perfil
          </Link>
        </div>
      </div>
    </>
  )
}
