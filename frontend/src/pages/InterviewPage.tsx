import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowLeftIcon, ChatBubbleLeftRightIcon, MicrophoneIcon, SpeakerWaveIcon, SpeakerXMarkIcon } from '@heroicons/react/24/outline'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { Header, Modal } from '../components/Design'
import { useAuth } from '../features/auth-context'
import { analyzeVacancy, getVacancies, type VacancySummary } from '../services/vacancies'
import { listResumes, type Resume } from '../services/profile'
import { cancelInterview, finishInterview, getActiveInterview, getInterviewSession, saveInterviewChoice, sendInterviewAnswer, startInterview, type InterviewMode, type InterviewSession } from '../services/interviews'
import { RealtimeVoice } from '../services/realtime-voice'

type Recognition = {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}
type SpeechWindow = Window & { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition }

function message(error: unknown) { return error instanceof Error ? error.message : 'Ocurrió un error. Intentá de nuevo.' }

const TRANSITION_DELAY_MS = 900
type InterviewTransition = { fromId: number; toId: number; explanation: string | null; question: string; connector: string }
type SpokenPart = { key: string; text: string }
type Presentation = { parts: SpokenPart[]; timer?: ReturnType<typeof setInterval>; visible: number; transcript: number; fallback?: boolean; finish?: () => void }

export function InterviewSetupPage() {
  const { candidate } = useAuth()
  const navigate = useNavigate()
  const [vacancies, setVacancies] = useState<VacancySummary[]>([])
  const [resumes, setResumes] = useState<Resume[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [newVacancy, setNewVacancy] = useState(false)
  const [useResume, setUseResume] = useState(false)
  const [mode, setMode] = useState<InterviewMode>('conversation')
  const [active, setActive] = useState<InterviewSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true
    Promise.all([getVacancies(), listResumes(), getActiveInterview()])
      .then(([offers, cvs, current]) => { if (mounted) { setVacancies(offers); setResumes(cvs); setActive(current) } })
      .catch((reason: Error) => { if (mounted) setError(reason.message) })
      .finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [candidate?.id])

  async function addVacancy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const form = new FormData(event.currentTarget)
    setBusy(true); setError('')
    try {
      const result = await analyzeVacancy({
        title: String(form.get('title') || '').trim(), company: String(form.get('company') || '').trim() || null,
        description: String(form.get('description') || '').trim(),
      })
      if (result.id === null || !result.created_at) throw new Error('Iniciá sesión para guardar la vacante.')
      const saved = { id: result.id, title: result.title, company: result.company, created_at: result.created_at, risk_percentage: result.risk_percentage }
      setVacancies((current) => [saved, ...current]); setSelected(saved.id); setNewVacancy(false)
    } catch (reason) { setError(message(reason)) } finally { setBusy(false) }
  }

  async function begin() {
    if (busy || selected === null) return
    setBusy(true); setError('')
    try {
      let micDenied = false
      if (mode === 'conversation' && ((window as SpeechWindow).SpeechRecognition || (window as SpeechWindow).webkitSpeechRecognition)
        && 'mediaDevices' in navigator && navigator.mediaDevices.getUserMedia) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
          stream.getTracks().forEach((track) => track.stop())
        } catch { micDenied = true }
      }
      const interview = await startInterview({ vacancy_id: selected, mode, use_resume: useResume })
      navigate(`/entrevistas/${interview.id}/simulacion`, { state: { micDenied } })
    } catch (reason) { setError(message(reason)) } finally { setBusy(false) }
  }

  const primary = resumes.find((resume) => resume.is_primary)
  return <>
    <Header title="Nueva entrevista simulada" screen="interview" />
    <Link className="example-link interview-back" to="/entrevistas"><ArrowLeftIcon aria-hidden="true" /> Volver a mis entrevistas</Link>
    {loading ? <p role="status">Cargando tus vacantes y currículums…</p> : <div className="interview-setup">
      {active && <section className="panel interview-resume"><h2>Tenés una entrevista en curso</h2><p>{active.vacancy_title}</p>
        <Link className="primary" to={`/entrevistas/${active.id}/simulacion`}>Retomar entrevista</Link>
        <button className="secondary" type="button" onClick={async () => {
          if (!window.confirm('¿Cancelar esta entrevista? No se generará un resultado.')) return
          try { await cancelInterview(active.id); setActive(null) } catch (reason) { setError(message(reason)) }
        }}>Cancelar y empezar otra</button>
      </section>}
      {!active && <>
        <section className="panel interview-step"><span className="eyebrow">PASO 1 DE 2</span><h2>Elegí una vacante analizada</h2>
          <p>La entrevista se basará en una oferta activa de tu cuenta.</p>
          {vacancies.length > 0 && <div className="interview-offers" role="radiogroup" aria-label="Vacante para la entrevista">
            {vacancies.map((offer) => <label className="interview-option" key={offer.id}>
              <input type="radio" name="vacancy" checked={selected === offer.id && !newVacancy} onChange={() => { setSelected(offer.id); setNewVacancy(false) }} />
              <span><strong>{offer.title}</strong><small>{offer.company || 'Empresa no indicada'}</small></span>
            </label>)}
          </div>}
          <button className="secondary" type="button" onClick={() => { setNewVacancy(!newVacancy); setSelected(null); setError('') }}>
            {newVacancy ? 'Elegir vacante existente' : 'Ingresar una nueva vacante'}
          </button>
          {newVacancy && <form className="interview-new-vacancy" onSubmit={(event) => void addVacancy(event)}>
            <div className="two-fields"><label className="field">Título de la vacante<input name="title" required maxLength={200} placeholder="Ej.: Desarrollador/a frontend" /></label>
              <label className="field">Empresa (opcional)<input name="company" maxLength={200} /></label></div>
            <label className="field">Descripción completa de la oferta<textarea name="description" required minLength={30} maxLength={12000} placeholder="Pegá la oferta laboral en texto plano…" /></label>
            <p className="helper">Primero se analizará y guardará en «Mis vacantes». El análisis no utiliza tu CV.</p>
            <button className="primary" type="submit" disabled={busy}>{busy ? 'Analizando vacante…' : 'Analizar y seleccionar vacante'}</button>
          </form>}
        </section>
        {selected !== null && <section className="panel interview-step"><span className="eyebrow">PASO 2 DE 2</span><h2>Personalizá tu entrevista</h2>
          <label className="interview-option"><input type="checkbox" checked={useResume} disabled={!primary} onChange={(event) => setUseResume(event.target.checked)} />
            <span><strong>Considerar mi currículum principal</strong><small>{primary ? primary.filename : 'No tenés un CV principal activo. Podés continuar solo con la vacante.'}</small></span>
          </label>
          {!primary && <Link className="example-link" to="/perfil">Configurar currículum en mi perfil</Link>}
          <div className="interview-modes" role="radiogroup" aria-label="Modalidad de entrevista">
            <label className="interview-option"><input type="radio" name="mode" checked={mode === 'conversation'} onChange={() => setMode('conversation')} />
              <span><strong>Conversación</strong><small>Respondé por voz o por chat y recibí correcciones breves.</small></span></label>
            <label className="interview-option"><input type="radio" name="mode" checked={mode === 'multiple_choice'} onChange={() => setMode('multiple_choice')} />
              <span><strong>Opción múltiple</strong><small>12 preguntas; podés recorrerlas en cualquier orden.</small></span></label>
          </div>
          {useResume && <p className="helper">Se enviará al proveedor de IA el texto extraído de tu CV principal para personalizar las preguntas. No se envía el archivo.</p>}
          {mode === 'conversation' && <p className="helper">Al comenzar se solicitará permiso para usar el micrófono. El dictado depende del navegador; la voz del entrevistador usa OpenAI Realtime. Podés responder siempre por chat. No guardamos audio.</p>}
          <button className="primary" type="button" disabled={busy} onClick={() => void begin()}>{busy ? <><span className="interview-spinner" aria-hidden="true" /> Preparando simulación…</> : 'Iniciar simulación'}</button>
        </section>}
      </>}
      {error && <p className="field-error" role="alert">{error}</p>}
    </div>}
  </>
}

export function InterviewSessionPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const micDenied = (location.state as { micDenied?: boolean } | null)?.micDenied ?? false
  const [session, setSession] = useState<InterviewSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [draft, setDraft] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [cancelConfirm, setCancelConfirm] = useState(false)
  const [micOn, setMicOn] = useState(!micDenied)
  const [voiceOn, setVoiceOn] = useState(true)
  const [voiceRetry, setVoiceRetry] = useState(0)
  const [voiceStatus, setVoiceStatus] = useState<'connecting' | 'ready' | 'speaking' | 'blocked' | 'error'>('connecting')
  const [micError, setMicError] = useState(micDenied ? 'No se concedió permiso para el micrófono. Podés responder por escrito.' : '')
  const [voiceError, setVoiceError] = useState('')
  const [visibleQuestionId, setVisibleQuestionId] = useState<number | null>(null)
  const [transition, setTransition] = useState<InterviewTransition | null>(null)
  const [connector, setConnector] = useState<{ questionId: number; text: string } | null>(null)
  const [streamedText, setStreamedText] = useState<Record<string, string>>({})
  const recognition = useRef<Recognition | null>(null)
  const voice = useRef<RealtimeVoice | null>(null)
  const micWanted = useRef(!micDenied)
  const speaking = useRef(false)
  const answering = useRef(false)
  const transitioning = useRef(false)
  const transitionRef = useRef<InterviewTransition | null>(null)
  const lastSpoken = useRef<string | null>(null)
  const presentation = useRef<Presentation | null>(null)

  const clearPresentation = useCallback((complete = true) => {
    const current = presentation.current
    if (!current) return
    if (current.timer) clearInterval(current.timer)
    presentation.current = null
    if (complete) setStreamedText((previous) => Object.fromEntries([
      ...Object.entries(previous), ...current.parts.map((part) => [part.key, part.text]),
    ]))
  }, [])

  const advancePresentation = useCallback(() => {
    const current = presentation.current
    if (!current) return
    const total = current.parts.reduce((length, part) => length + part.text.length + 1, 0)
    // Los fragmentos de transcripción orientan el avance; el reloj evita adelantarse al audio.
    current.visible = Math.min(total, current.visible + 2, !current.fallback && current.transcript ? current.transcript + 12 : total)
    let offset = 0
    const updated: Record<string, string> = {}
    for (const part of current.parts) {
      updated[part.key] = part.text.slice(0, Math.max(0, current.visible - offset))
      offset += part.text.length + 1
    }
    setStreamedText((previous) => ({ ...previous, ...updated }))
    if (current.fallback && current.visible >= total) {
      const finish = current.finish
      clearPresentation()
      finish?.()
    }
  }, [clearPresentation])

  const startPresentation = useCallback((fallback = false) => {
    const current = presentation.current
    if (!current) return
    if (current.timer) {
      if (!fallback || current.fallback) return
      clearInterval(current.timer)
    }
    current.fallback = fallback
    current.timer = setInterval(() => advancePresentation(), fallback ? 35 : 65)
  }, [advancePresentation])

  const speakParts = useCallback((parts: SpokenPart[], onFinished?: () => void) => {
    clearPresentation()
    presentation.current = { parts, visible: 0, transcript: 0, finish: onFinished }
    setStreamedText((previous) => ({ ...previous, ...Object.fromEntries(parts.map((part) => [part.key, ''])) }))
    if (voiceOn && voice.current) voice.current.speak(parts.map((part) => part.text).join(' '), onFinished)
    else startPresentation(true)
  }, [clearPresentation, startPresentation, voiceOn])

  useEffect(() => () => { const current = presentation.current; if (current?.timer) clearInterval(current.timer); presentation.current = null }, [])

  useEffect(() => {
    let mounted = true
    const interviewId = Number(id)
    if (!Number.isSafeInteger(interviewId) || interviewId <= 0) return
    getInterviewSession(interviewId)
      .then((data) => { if (mounted) {
        setSession(data)
        setCurrentIndex(data.mode === 'conversation' ? Math.max(0, data.questions.findIndex((q) => q.verdict === null)) : 0)
        setVisibleQuestionId(data.mode === 'conversation' ? data.questions.find((q) => q.verdict === null)?.id ?? null : null)
        const pending = data.questions.find((q) => q.verdict === null)
        if (data.mode === 'conversation' && pending) setStreamedText({ [`q-${pending.id}`]: '' })
        if (data.mode === 'conversation' && !((window as SpeechWindow).SpeechRecognition || (window as SpeechWindow).webkitSpeechRecognition)) {
          micWanted.current = false; setMicOn(false); setMicError('Este navegador no admite dictado. Podés responder por escrito.')
        }
      } })
      .catch((reason: Error) => { if (mounted) setError(reason.message) })
      .finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [id])

  useEffect(() => {
    if (session?.mode !== 'conversation') return
    const speechWindow = window as SpeechWindow
    const Constructor = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition
    if (!Constructor) return
    const instance = new Constructor()
    instance.lang = 'es-AR'; instance.continuous = false; instance.interimResults = false
    instance.onresult = (event) => { const transcript = event.results[0]?.[0]?.transcript; if (transcript) setDraft((previous) => `${previous} ${transcript}`.trim()) }
    instance.onerror = (event) => {
      if (event.error === 'no-speech' || event.error === 'aborted') return
      micWanted.current = false; setMicOn(false)
      setMicError('No se pudo usar el micrófono. Podés responder por escrito o volver a activarlo.')
    }
    instance.onend = () => { if (micWanted.current && !speaking.current && !answering.current) { try { instance.start() } catch { /* Evitar inicio duplicado */ } } }
    recognition.current = instance
    if (micWanted.current) { try { instance.start() } catch { micWanted.current = false; queueMicrotask(() => { setMicOn(false); setMicError('Activá el micrófono manualmente o respondé por escrito.') }) } }
    return () => { micWanted.current = false; instance.onend = null; instance.stop(); recognition.current = null }
  }, [session?.id, session?.mode])

  useEffect(() => {
    if (session?.mode !== 'conversation') return
    let mounted = true
    const realtime = new RealtimeVoice({
      onStatus: (status) => { if (mounted) setVoiceStatus(status) },
      onPlaybackStart: () => { if (mounted) startPresentation() },
      onTranscript: (delta) => { if (mounted && presentation.current) presentation.current.transcript += delta.length },
      onPlaybackEnd: () => { if (mounted) clearPresentation() },
      onSpeaking: (isSpeaking) => {
        speaking.current = isSpeaking
        if (isSpeaking) recognition.current?.stop()
        else if (micWanted.current && !answering.current && !transitioning.current) {
          try { recognition.current?.start() } catch { /* Ya iniciado o permiso pendiente */ }
        }
      },
      onError: () => {
        if (!mounted) return
        voice.current = null
        startPresentation(true)
        setVoiceStatus('error'); setVoiceOn(false)
        setVoiceError('La voz con IA no está disponible. La entrevista continúa por texto; podés reintentar la conexión.')
        if (!transitionRef.current) {
          transitioning.current = false
          if (micWanted.current && !answering.current) { try { recognition.current?.start() } catch { /* Ya iniciado */ } }
        }
      },
    })
    voice.current = realtime
    queueMicrotask(() => { if (mounted) setVoiceError('') })
    void realtime.connect(session.id).catch(() => { if (mounted) {
      realtime.close(); voice.current = null; setVoiceStatus('error'); setVoiceOn(false)
      startPresentation(true)
      setVoiceError('No se pudo conectar la voz con IA. Podés continuar por texto o reintentar.')
      if (!transitionRef.current) {
        transitioning.current = false
        if (micWanted.current && !answering.current) { try { recognition.current?.start() } catch { /* Ya iniciado */ } }
      }
    } })
    return () => { mounted = false; realtime.close(); if (voice.current === realtime) voice.current = null }
  }, [session?.id, session?.mode, voiceRetry, startPresentation, clearPresentation])

  const question = session?.questions[currentIndex]
  const nextQuestion = session?.mode === 'conversation' ? session.questions.find((q) => q.verdict === null) : null
  useEffect(() => {
    if (session?.mode !== 'conversation' || transition || nextQuestion && nextQuestion.id !== visibleQuestionId) return
    const previous = session.questions.find((q) => q.position === (nextQuestion?.position ?? session.questions.length + 1) - 1)
    const spokenId = nextQuestion ? `q-${nextQuestion.id}` : `end-${previous?.id}`
    if (lastSpoken.current === spokenId) return
    let active = true
    queueMicrotask(() => {
      if (!active || lastSpoken.current === spokenId) return
      lastSpoken.current = spokenId
      if (nextQuestion) speakParts([
        ...(connector?.questionId === nextQuestion.id ? [{ key: `c-${nextQuestion.id}`, text: connector.text }] : []),
        { key: `q-${nextQuestion.id}`, text: nextQuestion.question },
      ])
      else if (previous) speakParts([
        ...(previous.explanation ? [{ key: `e-${previous.id}`, text: previous.explanation }] : []),
        { key: `end-${previous.id}`, text: 'Terminaste las preguntas. Finalizá para ver tus resultados.' },
      ])
    })
    return () => { active = false }
  }, [session, nextQuestion, voiceRetry, visibleQuestionId, transition, connector, speakParts])

  useEffect(() => {
    if (!transition) return
    let active = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const resumeMic = () => {
      transitioning.current = false
      if (micWanted.current && !answering.current) {
        try { recognition.current?.start() } catch { /* Ya iniciado */ }
      }
    }
    const showNext = () => {
      timer = setTimeout(() => {
        if (!active) return
        transitionRef.current = null
        lastSpoken.current = `q-${transition.toId}`
        setConnector({ questionId: transition.toId, text: transition.connector })
        setVisibleQuestionId(transition.toId)
        setTransition(null)
        speakParts([{ key: `c-${transition.toId}`, text: transition.connector },
          { key: `q-${transition.toId}`, text: transition.question }], resumeMic)
      }, TRANSITION_DELAY_MS)
    }
    const explanation = transition.explanation
    if (explanation) queueMicrotask(() => {
      if (active) speakParts([{ key: `e-${transition.fromId}`, text: explanation }], showNext)
    })
    else showNext()
    return () => { active = false; if (timer) clearTimeout(timer) }
  }, [transition, voiceRetry, speakParts])

  function toggleMic() {
    if (micOn) { micWanted.current = false; recognition.current?.stop(); setMicOn(false) }
    else if (recognition.current) {
      micWanted.current = true
      try { if (!speaking.current && !transitioning.current) recognition.current.start(); setMicOn(true); setMicError('') }
      catch { micWanted.current = false; setMicError('No se pudo activar el micrófono. Revisá los permisos del navegador.') }
    }
  }

  async function submitAnswer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!session || !nextQuestion || !draft.trim() || busy) return
    answering.current = true
    setBusy(true); setError(''); recognition.current?.stop(); voice.current?.stop(); clearPresentation(); setVoiceStatus('ready')
    let waitForVoice = false
    try {
      const updated = await sendInterviewAnswer(session.id, nextQuestion.id, draft.trim())
      const following = updated.questions.find((item) => item.verdict === null)
      const answered = updated.questions.find((item) => item.id === nextQuestion.id)
      setConnector(null)
      setStreamedText((previous) => ({ ...previous, [`e-${nextQuestion.id}`]: '', ...(following ? { [`q-${following.id}`]: '', [`c-${following.id}`]: '' } : {}) }))
      if (following && answered) {
        const nextTransition = {
          fromId: answered.id, toId: following.id, explanation: answered.explanation, question: following.question,
          connector: answered.verdict === 'correcta'
            ? 'Bien, sigamos con la siguiente pregunta.'
            : 'Pasemos a la siguiente pregunta.',
        }
        transitioning.current = true
        transitionRef.current = nextTransition
        setVisibleQuestionId(null)
        setTransition(nextTransition)
        waitForVoice = true
      } else {
        setVisibleQuestionId(null)
        waitForVoice = voiceOn && voice.current !== null
      }
      setSession(updated); setDraft(''); setCurrentIndex(Math.min(updated.questions.length - 1, nextQuestion.position))
    } catch (reason) { setError(message(reason)) } finally {
      answering.current = false; setBusy(false)
      if (!waitForVoice && micWanted.current && !speaking.current) { try { recognition.current?.start() } catch { /* Ya iniciado */ } }
    }
  }

  async function choose(index: number | null) {
    if (!session || !question || busy) return
    setBusy(true); setError('')
    try { setSession(await saveInterviewChoice(session.id, question.id, index)) }
    catch (reason) { setError(message(reason)) } finally { setBusy(false) }
  }

  async function finish() {
    if (!session || busy) return
    setBusy(true); setError('')
    try { await finishInterview(session.id); transitionRef.current = null; setTransition(null); voice.current?.stop(); clearPresentation(); navigate(`/entrevistas/${session.id}`, { replace: true }) }
    catch (reason) { setError(message(reason)); setConfirm(false) } finally { setBusy(false) }
  }

  async function cancel() {
    if (!session || busy) return
    setBusy(true); setError('')
    try { await cancelInterview(session.id); transitionRef.current = null; setTransition(null); voice.current?.stop(); clearPresentation(); navigate('/entrevistas', { replace: true }) }
    catch (reason) { setError(message(reason)); setCancelConfirm(false) } finally { setBusy(false) }
  }

  return <>
    <Header title="Simulación de entrevista técnica" screen="interview" />
    {loading && id && Number.isSafeInteger(Number(id)) && Number(id) > 0 ? <p role="status" className="interview-loading"><span className="interview-spinner" aria-hidden="true" /> Cargando simulación…</p>
      : !session ? <p className="field-error" role="alert">{error || 'Entrevista no encontrada.'}</p> : <div className="interview-live">
        <div className="selected-vacancy"><p>Vacante seleccionada · {session.using_resume ? 'Incluye CV principal' : 'Solo vacante'}</p><strong>{session.vacancy_title}</strong></div>
        {session.mode === 'multiple_choice' ? <>
          <nav className="interview-question-nav" aria-label="Preguntas de la entrevista">
            {session.questions.map((item, index) => <button type="button" key={item.id} disabled={busy} className={index === currentIndex ? 'current' : ''} aria-current={index === currentIndex ? 'step' : undefined} aria-label={`Pregunta ${item.position}${item.answer !== null ? ', respondida' : ', sin responder'}`} onClick={() => setCurrentIndex(index)}>{item.position}<span className="question-dot" aria-hidden="true" /></button>)}
          </nav>
          {question && <section className="panel interview-question-card"><span className="eyebrow">PREGUNTA {question.position} DE {session.questions.length} · {question.topic}</span><h2>{question.question}</h2>
            <div className="interview-choices">{question.options?.map((option, index) => <label className="interview-option" key={index}><input type="radio" name={`question-${question.id}`} checked={question.answer === String(index)} disabled={busy} onChange={() => void choose(index)} /><span>{option}</span></label>)}</div>
            <div className="interview-question-actions"><button type="button" className="secondary" disabled={busy || currentIndex === 0} onClick={() => setCurrentIndex(currentIndex - 1)}>Anterior</button>
              {question.answer !== null && <button type="button" className="secondary" disabled={busy} onClick={() => void choose(null)}>Borrar respuesta</button>}
              <button type="button" className="secondary" disabled={busy || currentIndex === session.questions.length - 1} onClick={() => setCurrentIndex(currentIndex + 1)}>Siguiente</button></div>
          </section>}
        </> : <>
          <p className="interview-count" role="status">{transition ? 'Preparando la siguiente pregunta…' : nextQuestion ? `Pregunta ${nextQuestion.position} de ${session.questions.length}` : 'Respondiste todas las preguntas'}</p>
          <div className="interview-conversation">
          <div className="panel interview-chat" aria-label="Conversación de la entrevista">
            {session.questions.filter((item) => item.verdict !== null || item.id === visibleQuestionId).map((item) => <div className="interview-exchange" key={item.id}>
              {connector?.questionId === item.id && <div className="chat-bubble agent"><span>Entrevistador/a</span><p>{streamedText[`c-${item.id}`] ?? connector.text}</p></div>}
              <div className="chat-bubble agent"><span>Entrevistador/a · {item.topic}</span><p>{streamedText[`q-${item.id}`] ?? item.question}</p></div>
              {item.answer && <div className="chat-bubble candidate"><span>Tu respuesta</span><p>{item.answer}</p></div>}
              {item.explanation && <div className="chat-bubble agent"><span>{item.verdict === 'parcial' ? 'Respuesta parcial' : 'Para mejorar'}</span><p>{streamedText[`e-${item.id}`] ?? item.explanation}</p></div>}
            </div>)}
            {!nextQuestion && session.questions.at(-1) && <div className="chat-bubble agent"><span>Entrevistador/a</span><p>{streamedText[`end-${session.questions.at(-1)!.id}`] ?? 'Terminaste las preguntas. Finalizá para ver tus resultados.'}</p></div>}
          </div>
          <div className="interview-agent-voice" role="status" aria-label={voiceOn && voiceStatus === 'speaking' ? 'El agente está hablando' : 'El agente está en silencio'}>
            <span className={`interview-agent-orb${voiceOn && voiceStatus === 'speaking' ? ' is-speaking' : ''}`} aria-hidden="true"><span /></span>
            <strong>Voz del agente</strong><small>{voiceOn && voiceStatus === 'speaking' ? 'Hablando…' : voiceOn && voiceStatus === 'connecting' ? 'Conectando…' : 'En espera'}</small>
          </div>
          </div>
          <div className="interview-voice-bar"><button className="secondary" type="button" aria-pressed={micOn} disabled={!((window as SpeechWindow).SpeechRecognition || (window as SpeechWindow).webkitSpeechRecognition)} onClick={toggleMic}><MicrophoneIcon aria-hidden="true" /> {micOn ? 'Desactivar micrófono' : 'Activar micrófono'}</button>
            <button className="secondary" type="button" aria-pressed={voiceOn} disabled={!('RTCPeerConnection' in window)} onClick={() => {
              if (voiceOn) {
                if (!transitionRef.current) transitioning.current = false
                voice.current?.stop(); clearPresentation(); setVoiceStatus('ready'); setVoiceOn(false)
              }
              else { lastSpoken.current = null; setVoiceOn(true); if (!voice.current) setVoiceRetry((value) => value + 1) }
            }}>{voiceOn ? <SpeakerWaveIcon aria-hidden="true" /> : <SpeakerXMarkIcon aria-hidden="true" />}{voiceOn ? 'Desactivar voz del agente' : 'Activar voz del agente'}</button></div>
          {voiceOn && voiceStatus === 'connecting' && <p className="helper" role="status">Conectando voz natural…</p>}
          {voiceOn && voiceStatus === 'blocked' && <button className="secondary" type="button" onClick={() => voice.current?.resumeAudio()}>Reproducir audio (permiso del navegador)</button>}
          {micError && <p className="helper" role="status">{micError}</p>}
          {voiceError && <p className="helper" role="status">{voiceError}</p>}
          {nextQuestion ? !transition && visibleQuestionId === nextQuestion.id && <form className="interview-compose" onSubmit={(event) => void submitAnswer(event)}><label htmlFor="interview-answer">Escribí o dictá tu respuesta</label><textarea id="interview-answer" value={draft} maxLength={2000} onChange={(event) => setDraft(event.target.value)} placeholder="Tu respuesta aparecerá aquí…" /><button className="primary" type="submit" disabled={busy || !draft.trim()}>{busy ? 'Evaluando…' : 'Enviar respuesta'}</button></form> : <p className="panel interview-done"><ChatBubbleLeftRightIcon aria-hidden="true" /> ¡Terminaste las preguntas! Finalizá para ver tus resultados.</p>}
        </>}
        {error && <p className="field-error" role="alert">{error}</p>}
        <div className="interview-finish-actions"><button className="secondary" type="button" disabled={busy} onClick={() => setCancelConfirm(true)}>Cancelar sin resultado</button><button className="primary" type="button" disabled={busy} onClick={() => setConfirm(true)}>Finalizar entrevista</button></div>
      </div>}
    {confirm && <Modal title="¿Finalizar entrevista?" onClose={() => { if (!busy) setConfirm(false) }}><p>Las respuestas vacías se guardarán como incorrectas. Se calculará tu resultado con todas las preguntas, incluso si terminás antes.</p><button className="primary" type="button" disabled={busy} onClick={() => void finish()}>{busy ? 'Calculando resultado…' : 'Sí, finalizar y ver resultado'}</button></Modal>}
    {cancelConfirm && <Modal title="¿Cancelar entrevista?" onClose={() => { if (!busy) setCancelConfirm(false) }}><p>No se generará una nota ni recomendaciones. Podés salir de la página y retomarla más tarde si preferís.</p><button className="primary" type="button" disabled={busy} onClick={() => void cancel()}>{busy ? 'Cancelando…' : 'Sí, cancelar sin resultado'}</button></Modal>}
  </>
}
