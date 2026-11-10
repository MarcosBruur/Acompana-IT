import { useEffect, useState } from 'react'
import { EyeIcon, TrashIcon } from '@heroicons/react/24/outline'
import { Link, useParams } from 'react-router-dom'
import { Header, Modal } from '../components/Design'
import { useAuth } from '../features/auth-context'
import { useNotifications } from '../features/notifications-context'
import { getInterview, getInterviews, hideInterview, PAGE_SIZE, type InterviewResult, type InterviewSummary } from '../services/interviews'

function formatDate(value: string) {
  return new Intl.DateTimeFormat('es-AR', { day: '2-digit', month: 'long', year: 'numeric' }).format(new Date(value))
}

export function InterviewHistoryPage() {
  const { candidate } = useAuth()
  const notifications = useNotifications()
  const [history, setHistory] = useState<{ ownerId: number; items: InterviewSummary[]; hasMore: boolean } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<InterviewSummary | null>(null)
  const [hiding, setHiding] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)

  useEffect(() => {
    let active = true
    getInterviews()
      .then((items) => { if (active && candidate) setHistory({ ownerId: candidate.id, items, hasMore: items.length === PAGE_SIZE }) })
      .catch((reason: Error) => { if (active) setError(reason.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [candidate])

  const items = history && history.ownerId === candidate?.id ? history.items : []

  async function loadMore() {
    if (!candidate || !history?.hasMore || loadingMore) return
    setLoadingMore(true)
    try {
      const next = await getInterviews(items.at(-1)?.id)
      setHistory((current) => current?.ownerId === candidate.id ? {
        ...current, items: [...current.items, ...next.filter((item) => !current.items.some((old) => old.id === item.id))],
        hasMore: next.length === PAGE_SIZE,
      } : current)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudieron cargar más entrevistas.') }
    finally { setLoadingMore(false) }
  }

  async function confirmHide() {
    if (!selected || hiding) return
    setHiding(true)
    setError('')
    try {
      await hideInterview(selected.id)
      setHistory((current) => current && candidate?.id === current.ownerId
        ? { ...current, items: current.items.filter((item) => item.id !== selected.id) }
        : current)
      setSelected(null)
      notifications.success('Entrevista quitada del listado. El resultado permanece guardado.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No se pudo ocultar la entrevista.')
    } finally {
      setHiding(false)
    }
  }

  return <>
    <Header title="Simular entrevista" screen="interview" />
    <div className="interview-history-heading">
      <p>Revisá tus resultados y seguí practicando a tu ritmo.</p>
      {items.length > 0 && <Link className="primary" to="/entrevistas/nueva">Comenzar entrevista simulada</Link>}
    </div>
    {loading ? <p role="status">Cargando entrevistas…</p> : error && !history ? (
      <p className="field-error" role="alert">{error}</p>
    ) : items.length === 0 ? (
      <section className="panel interview-history-empty">
        <h2>Aun no hay entrevistas simuladas</h2>
        <p>Cuando completes una entrevista, vas a encontrar acá su nota y recomendaciones.</p>
        <Link className="primary" to="/entrevistas/nueva">Comenzar entrevista simulada</Link>
      </section>
    ) : (
      <section className="panel interview-history-panel" aria-label="Entrevistas realizadas">
        <h2>Entrevistas realizadas</h2>
        <ul className="interview-history-list">
          {items.map((item) => <li className="interview-history-item" key={item.id}>
            <div className="interview-history-description">
              <time dateTime={item.created_at}>{formatDate(item.created_at)}</time>
              <h3>{item.vacancy_title}</h3>
            </div>
            <span className="interview-score">Nota <strong>{item.score}/100</strong></span>
            <div className="interview-history-actions">
              <Link className="interview-icon-action" to={`/entrevistas/${item.id}`} aria-label={`Ver resultado de ${item.vacancy_title}`} title="Ver resultado">
                <EyeIcon aria-hidden="true" />
              </Link>
              <button className="interview-icon-action interview-hide-action" type="button" aria-label={`Ocultar entrevista de ${item.vacancy_title}`} title="Ocultar entrevista" onClick={() => { setError(''); setSelected(item) }}>
                <TrashIcon aria-hidden="true" />
              </button>
            </div>
          </li>)}
        </ul>
        {history?.hasMore && <button className="secondary" type="button" disabled={loadingMore} onClick={() => void loadMore()}>{loadingMore ? 'Cargando…' : 'Ver más entrevistas'}</button>}
      </section>
    )}
    {error && history && !selected && <p className="field-error interview-history-error" role="alert">{error}</p>}
    {selected && <Modal title="¿Ocultar entrevista?" onClose={() => { if (!hiding) setSelected(null) }}>
      <p>«{selected.vacancy_title}» dejará de aparecer en tu listado. El resultado y las respuestas permanecerán guardados.</p>
      {error && <p className="field-error" role="alert">{error}</p>}
      <button className="primary" type="button" disabled={hiding} onClick={() => void confirmHide()}>
        {hiding ? 'Ocultando…' : 'Sí, ocultar entrevista'}
      </button>
    </Modal>}
  </>
}

export function InterviewResultPage() {
  const { id } = useParams()
  const [result, setResult] = useState<InterviewResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    const interviewId = Number(id)
    if (!Number.isSafeInteger(interviewId) || interviewId <= 0) {
      queueMicrotask(() => { if (active) { setError('Entrevista no encontrada.'); setLoading(false) } })
      return () => { active = false }
    }
    getInterview(interviewId)
      .then((item) => { if (active) setResult(item) })
      .catch((reason: Error) => { if (active) setError(reason.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id])

  return <>
    <Header title="Resultado de entrevista" screen="interview" />
    <Link className="example-link interview-back" to="/entrevistas">← Volver a mis entrevistas</Link>
    {loading && id && Number.isSafeInteger(Number(id)) && Number(id) > 0 ? <p role="status">Cargando resultado…</p>
      : error || !result ? <p className="field-error" role="alert">{error || 'Entrevista no encontrada.'}</p>
        : <div className="interview-result-content">
          <section className="panel interview-result-hero">
            <div><span className="eyebrow">ENTREVISTA REALIZADA</span><h2>{result.vacancy_title}</h2><p>{formatDate(result.created_at)}</p></div>
            <div className="interview-result-score"><strong>{result.score}</strong><span>sobre 100</span></div>
          </section>
          <section className="panel"><h2>Recomendaciones</h2><p>{result.feedback || 'No hay recomendaciones registradas para esta entrevista.'}</p></section>
          <section className="panel"><h2>Competencias a reforzar</h2>
            {result.skills_to_improve.length ? <ul className="interview-skills">{result.skills_to_improve.map((skill, index) => <li key={`${skill}-${index}`}>{skill}</li>)}</ul> : <p>No se registraron competencias a reforzar.</p>}
          </section>
          {result.questions.some((question) => question.verdict !== null) && <section className="panel"><h2>Respuestas: {result.correct_count} correctas · {result.partial_count} parciales · {result.incorrect_count} incorrectas</h2>
            <p>Cada parcial suma medio punto. {result.unanswered_count} sin responder (incluidas entre las incorrectas). La nota contempla todas las preguntas.</p>
            <ol className="interview-result-questions">{result.questions.map((question) => <li key={question.id}>
              <h3>{question.question}</h3><p><strong>{question.answer === null ? 'Sin respuesta' : question.verdict === 'correcta' ? 'Correcta' : question.verdict === 'parcial' ? 'Parcial (0,5 puntos)' : 'Incorrecta'}</strong> · Tu respuesta: {question.answer === null ? 'No respondida' : question.options ? question.options[Number(question.answer)] : question.answer}</p>
              {question.options && question.correct_index !== null && <p>Respuesta correcta: {question.options[question.correct_index]}</p>}
              {question.explanation && <p>{question.explanation}</p>}
            </li>)}</ol>
          </section>}
          {result.resources.length > 0 && <section className="panel"><h2>Recursos gratuitos para seguir aprendiendo</h2><ul className="interview-resources">{result.resources.map((resource) => <li key={resource.url}><a href={resource.url} target="_blank" rel="noopener noreferrer">{resource.title} ↗</a></li>)}</ul></section>}
        </div>}
  </>
}
