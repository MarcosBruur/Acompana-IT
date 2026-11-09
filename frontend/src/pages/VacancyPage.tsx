import { useEffect, useState, type FormEvent } from 'react'
import { TrashIcon } from '@heroicons/react/24/outline'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { Header, Modal } from '../components/Design'
import { useAuth } from '../features/auth-context'
import { useNotifications } from '../features/notifications-context'
import { analyzeVacancy, getTransientAnalysis, getVacancies, getVacancy, hideVacancy, setTransientAnalysis, type Finding, type VacancyResult, type VacancySummary } from '../services/vacancies'

export function VacancyPage() {
  const { candidate, loading: authLoading } = useAuth()
  const notifications = useNotifications()
  const [history, setHistory] = useState<{ ownerId: number; items: VacancySummary[]; error: string } | null>(null)
  const [selected, setSelected] = useState<VacancySummary | null>(null)
  const [removeError, setRemoveError] = useState('')
  const [removing, setRemoving] = useState(false)
  const candidateId = candidate?.password_expired ? undefined : candidate?.id

  useEffect(() => {
    if (candidateId === undefined) return
    let active = true
    getVacancies()
      .then((items) => { if (active) setHistory({ ownerId: candidateId, items, error: '' }) })
      .catch(() => { if (active) setHistory({ ownerId: candidateId, items: [], error: 'No se pudo consultar el historial.' }) })
    return () => { active = false }
  }, [candidateId])

  const currentHistory = history?.ownerId === candidateId ? history : null

  async function confirmRemove() {
    if (!selected || removing) return
    setRemoving(true)
    setRemoveError('')
    try {
      await hideVacancy(selected.id)
      setHistory((current) => current && current.ownerId === candidateId
        ? { ...current, items: current.items.filter((item) => item.id !== selected.id) }
        : current)
      setSelected(null)
      notifications.success('Vacante quitada de tu listado.')
    } catch (reason) {
      setRemoveError(reason instanceof Error ? reason.message : 'No se pudo quitar la vacante.')
    } finally {
      setRemoving(false)
    }
  }

  return <>
    <Header title="Mis vacantes" screen="vacancy" />
    <div className="vacancy-content">
      <div className="vacancy-list-heading"><Link className="primary" to="/vacantes/nueva">Analizar vacante</Link></div>
      <section className="panel">
        <h2>Vacantes analizadas</h2>
        {authLoading || candidateId !== undefined && !currentHistory ? <p role="status">Cargando vacantes…</p> : currentHistory?.error ? <p className="field-error" role="alert">{currentHistory.error}</p> : currentHistory?.items.length ? <ul className="vacancy-history">{currentHistory.items.map((item) => <li key={item.id}>
          <div className="vacancy-history-details"><Link to={`/vacantes/${item.id}/analisis`}>{item.title}</Link><small>{item.company || 'Empresa no indicada'} · {new Date(item.created_at).toLocaleDateString('es-AR')}{item.risk_percentage !== null ? ` · Riesgo orientativo: ${item.risk_percentage}%` : ''}</small></div>
          <button className="vacancy-remove" type="button" aria-label={`Eliminar vacante ${item.title} del listado`} title="Eliminar del listado" onClick={() => { setRemoveError(''); setSelected(item) }}><TrashIcon aria-hidden="true" /><span>Eliminar</span></button>
        </li>)}</ul> : <p>Aún no tienes vacantes analizadas. Ingresa vacantes para visualizar todas.</p>}
      </section>
    </div>
    {selected && <Modal title="¿Eliminar vacante del listado?" onClose={() => { if (!removing) setSelected(null) }}>
      <p>«{selected.title}» dejará de aparecer en tus vacantes. Los resultados de entrevistas y comparaciones relacionados se conservarán.</p>
      {removeError && <p className="field-error" role="alert">{removeError}</p>}
      <button className="primary" type="button" disabled={removing} onClick={() => void confirmRemove()}>{removing ? 'Eliminando…' : 'Sí, eliminar del listado'}</button>
    </Modal>}
  </>
}

export function NewVacancyPage() {
  const { candidate } = useAuth()
  const notifications = useNotifications()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setError(''); setBusy(true)
    try {
      const result = await analyzeVacancy({
        title: String(form.get('title') ?? '').trim(),
        company: String(form.get('company') ?? '').trim() || null,
        description: String(form.get('description') ?? '').trim(),
      })
      notifications.success(result.id ? 'Vacante analizada y guardada en tu cuenta.' : 'Análisis completado. Este resultado temporal no se guardó.')
      if (result.id) navigate(`/vacantes/${result.id}/analisis`, { state: { result } })
      else { setTransientAnalysis(result); navigate('/vacantes/analisis') }
    } catch (reason) { setError(reason instanceof Error && reason.name !== 'TimeoutError' ? reason.message : 'El análisis tardó demasiado. Volvé a intentarlo.') }
    finally { setBusy(false) }
  }

  return <>
    <Header title="Analizar nueva vacante" screen="vacancy" />
    <div className="vacancy-content">
      <p className="intro">Pegá la oferta laboral para conocer qué busca la empresa antes de postularte. No se utiliza tu CV.</p>
      <form className="panel vacancy-form" onSubmit={(event) => void submit(event)}>
        <h2>Datos de la vacante</h2>
        <div className="two-fields">
          <label className="field">Título de la vacante<input name="title" required maxLength={200} placeholder="Ej.: Desarrollador/a Frontend React" /></label>
          <label className="field">Empresa (opcional)<input name="company" maxLength={200} placeholder="Ej.: Nombre de la empresa" /></label>
        </div>
        <label className="field">Descripción completa de la oferta<textarea name="description" required minLength={30} maxLength={12000} placeholder="Pegá aquí la descripción completa de la vacante, incluyendo responsabilidades, requisitos y beneficios…" /></label>
        <div className="analysis-explanation"><strong>¿Qué vamos a analizar?</strong><p>Requisitos, tecnologías, experiencia, seniority y posibles señales de riesgo de la oferta. El porcentaje de riesgo es orientativo.</p></div>
        <p className="helper">{candidate && !candidate.password_expired ? 'El análisis quedará guardado en tu cuenta.' : 'Podés analizar sin cuenta; el resultado no se guardará.'}</p>
        {error && <p className="field-error" role="alert">{error}</p>}
        <div className="form-actions"><p className="helper">Completá el título y la descripción para iniciar el análisis.</p><button className="primary" type="submit" disabled={busy}>{busy ? 'Analizando oferta…' : 'Analizar vacante'}</button></div>
      </form>
    </div>
  </>
}

function ListCard({ title, items }: { title: string; items: string[] }) {
  return <section className="panel result-card"><h2>{title}</h2>{items.length ? <ul>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : <p>No se especifica en la oferta.</p>}</section>
}

function Findings({ title, items }: { title: string; items: Finding[] }) {
  return <section className="risk-panel"><h2>{title}</h2>{items.length ? items.map((item, index) => <div className="risk-row" key={`${item.title}-${index}`}><div><h3>{item.title}</h3><p>{item.explanation}</p><small>Fragmento de la oferta: «{item.evidence}»</small></div><span className={`pill ${item.relevance === 'alta' ? 'red' : 'amber'}`}>Relevancia {item.relevance}</span></div>) : <p>No se detectaron {title.toLowerCase()} respaldadas por el texto de la oferta.</p>}</section>
}

export function AnalysisPage() {
  const { id } = useParams()
  const location = useLocation()
  const state = location.state as { result?: VacancyResult } | null
  const [result, setResult] = useState<VacancyResult | null>(id ? state?.result ?? null : getTransientAnalysis())
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(!!id && !state?.result)

  useEffect(() => {
    if (!id) return
    let active = true
    getVacancy(Number(id)).then((response) => { if (active) { setResult(response); setError('') } })
      .catch((reason: Error) => { if (active) setError(reason.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id])

  return <><Header title="Análisis de vacante" screen="analysis" />
    {loading ? <p role="status">Cargando análisis…</p> : error ? <p className="field-error" role="alert">{error}</p> : !result ? <section className="panel"><p>Este análisis anónimo ya no está disponible. Volvé a pegar la oferta para analizarla de nuevo.</p><Link className="secondary" to="/vacantes/nueva">Analizar una vacante</Link></section> : <div className="analysis-content">
      <h2 className="vacancy-title">{result.title}</h2>
      <p className="helper">{result.company || 'Empresa no indicada'} · Análisis de la oferta, sin comparar con un CV. {result.id ? 'Guardado en tu cuenta.' : 'Resultado temporal: no se guardó.'}</p>
      <div className="result-grid">
        <section className="panel result-card"><h2>Seniority detectado</h2><strong className="result-value">{result.seniority || 'No especificado'}</strong></section>
        <section className="panel result-card"><h2>Experiencia requerida</h2><strong className="result-value">{result.experience_required || 'No especificada'}</strong></section>
        <section className="panel result-card"><h2>Tecnologías</h2>{result.technologies.length ? <div className="tags">{result.technologies.map((tag, index) => <span key={`${tag}-${index}`}>{tag}</span>)}</div> : <p>No se especifican.</p>}</section>
        <ListCard title="Competencias requeridas" items={result.required_skills} />
        <ListCard title="Responsabilidades" items={result.responsibilities} />
        <section className="panel result-card"><h2>Resumen</h2><p>{result.summary || 'La oferta no proporciona detalles suficientes para un resumen.'}</p></section>
      </div>
      <section className="panel"><h2>Riesgo orientativo: {result.risk_percentage}%</h2><p>Indicador basado en alertas con evidencia textual (alta: 30 puntos, media: 15, baja: 5; máximo 100). No mide tu compatibilidad ni garantiza la calidad de la oferta.</p></section>
      <Findings title="Inconsistencias" items={result.inconsistencies} />
      <Findings title="Señales de riesgo" items={result.risk_signals} />
      <div className="analysis-actions"><Link className="secondary" to="/vacantes/nueva">Analizar otra vacante</Link></div>
    </div>}
  </>
}
