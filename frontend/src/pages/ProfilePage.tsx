import { useEffect, useRef, useState, type FormEvent, type PointerEvent } from 'react'
import { TrashIcon } from '@heroicons/react/24/outline'
import { Asset, Header, Modal } from '../components/Design'
import { useAuth } from '../features/auth-context'
import { useNotifications } from '../features/notifications-context'
import type { Candidate } from '../services/auth'
import { hideResume, listResumes, saveNickname, selectPrimary, uploadFile, validatePdf, type Resume } from '../services/profile'

const SIDE = 256

function draw(canvas: HTMLCanvasElement, image: HTMLImageElement, zoom: number, x: number, y: number) {
  const context = canvas.getContext('2d')
  if (!context) return
  const scale = Math.max(SIDE / image.naturalWidth, SIDE / image.naturalHeight) * zoom
  const width = image.naturalWidth * scale
  const height = image.naturalHeight * scale
  context.clearRect(0, 0, SIDE, SIDE)
  context.drawImage(image, (SIDE - width) / 2 + x, (SIDE - height) / 2 + y, width, height)
}

function CropPhoto({ file, onClose, onSaved }: { file: File; onClose: () => void; onSaved: (candidate: Candidate) => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const image = useRef<HTMLImageElement | null>(null)
  const pointer = useRef<{ x: number; y: number } | null>(null)
  const [zoom, setZoom] = useState(1)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let active = true
    const current = dialog.current
    current?.showModal()
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      if (!active) return
      if (img.naturalWidth < 64 || img.naturalHeight < 64) setError('Elegí una imagen de al menos 64 píxeles por lado.')
      else { image.current = img; setError(''); setReady(true); if (canvas.current) draw(canvas.current, img, 1, 0, 0) }
    }
    img.onerror = () => { if (active) setError('No se pudo abrir la imagen.') }
    img.src = url
    return () => {
      active = false
      img.onload = null
      img.onerror = null
      current?.close()
      URL.revokeObjectURL(url)
    }
  }, [file])

  useEffect(() => { if (image.current && canvas.current) draw(canvas.current, image.current, zoom, position.x, position.y) }, [zoom, position])

  function move(event: PointerEvent<HTMLDivElement>) {
    if (!pointer.current) return
    const ratio = SIDE / event.currentTarget.clientWidth
    const dx = (event.clientX - pointer.current.x) * ratio
    const dy = (event.clientY - pointer.current.y) * ratio
    pointer.current = { x: event.clientX, y: event.clientY }
    const img = image.current
    if (!img) return
    const scale = Math.max(SIDE / img.naturalWidth, SIDE / img.naturalHeight) * zoom
    const limitX = Math.max(0, (img.naturalWidth * scale - SIDE) / 2)
    const limitY = Math.max(0, (img.naturalHeight * scale - SIDE) / 2)
    setPosition((p) => ({ x: Math.max(-limitX, Math.min(limitX, p.x + dx)), y: Math.max(-limitY, Math.min(limitY, p.y + dy)) }))
  }

  async function save() {
    const preview = canvas.current
    if (!preview || !image.current) return
    setBusy(true)
    setError('')
    try {
      const output = document.createElement('canvas')
      output.width = output.height = 512
      const context = output.getContext('2d')
      if (!context) throw new Error('No se pudo procesar la imagen.')
      context.scale(2, 2)
      context.drawImage(preview, 0, 0)
      const blob = await new Promise<Blob | null>((resolve) => output.toBlob(resolve, 'image/webp', 0.88))
      if (!blob) throw new Error('No se pudo procesar la imagen.')
      const saved = await uploadFile<Candidate>('/avatar', new File([blob], 'imagen.webp', { type: 'image/webp' }))
      onSaved(saved)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo guardar la foto.') }
    finally { setBusy(false) }
  }

  return <dialog ref={dialog} className="modal crop-dialog" aria-label="Ajustar foto de perfil" onCancel={(event) => { event.preventDefault(); if (!busy) onClose() }}>
    <h2>Ajustá tu foto</h2>
    <p>Arrastrá la imagen para ubicarla dentro del círculo y ajustá el zoom.</p>
    <div className="crop-area" aria-label="Previsualización de la foto" onPointerDown={(event) => { event.currentTarget.setPointerCapture(event.pointerId); pointer.current = { x: event.clientX, y: event.clientY } }} onPointerMove={move} onPointerUp={() => { pointer.current = null }} onPointerCancel={() => { pointer.current = null }}>
      <canvas ref={canvas} width={SIDE} height={SIDE} />
    </div>
    <label>Zoom <input type="range" min="1" max="3" step="0.05" value={zoom} onChange={(event) => { const next = Number(event.target.value); setZoom(next); setPosition({ x: 0, y: 0 }) }} /></label>
    {error && <p className="field-error" role="alert">{error}</p>}
    <div className="profile-actions"><button className="primary" disabled={busy || !ready || !!error} onClick={() => void save()}>{busy ? 'Guardando…' : 'Guardar foto'}</button><button className="secondary" disabled={busy} onClick={onClose}>Cancelar</button></div>
  </dialog>
}

export function ProfilePage() {
  const { candidate, setCandidate } = useAuth()
  const notifications = useNotifications()
  const photoInput = useRef<HTMLInputElement>(null)
  const cvInput = useRef<HTMLInputElement>(null)
  const [nickname, setNickname] = useState(candidate?.nickname || candidate?.first_name || '')
  const [resumes, setResumes] = useState<Resume[]>([])
  const [photo, setPhoto] = useState<File | null>(null)
  const [selectedResume, setSelectedResume] = useState<Resume | null>(null)
  const [removeError, setRemoveError] = useState('')
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)

  useEffect(() => { listResumes().then(setResumes).catch((reason: Error) => notifications.error(reason.message)) }, [notifications])
  async function refresh() { setResumes(await listResumes()) }
  async function addResume(file?: File) {
    if (!file || busy) return
    try {
      await validatePdf(file)
      setBusy(true)
      await uploadFile('/resumes', file)
      notifications.success('Currículum cargado correctamente.')
      await refresh()
    } catch (reason) { notifications.error(reason instanceof Error ? reason.message : 'No se pudo cargar el currículum.') }
    finally { setBusy(false) }
  }

  async function makePrimary(id: number) {
    setBusy(true)
    try {
      await selectPrimary(id)
      notifications.success('Currículum principal actualizado.')
      await refresh()
    } catch (reason) { notifications.error(reason instanceof Error ? reason.message : 'No se pudo actualizar el currículum principal.') }
    finally { setBusy(false) }
  }

  async function confirmRemove() {
    if (!selectedResume || busy) return
    setBusy(true)
    setRemoveError('')
    try {
      await hideResume(selectedResume.id)
      setResumes((current) => {
        const remaining = current.filter((resume) => resume.id !== selectedResume.id)
        if (!selectedResume.is_primary) return remaining
        return remaining.map((resume, index) => ({ ...resume, is_primary: index === 0 }))
      })
      setSelectedResume(null)
      notifications.success('Currículum quitado de tu perfil.')
      try { await refresh() }
      catch { notifications.error('El currículum se quitó, pero no se pudo actualizar el listado. Recargá la página.') }
    } catch (reason) {
      setRemoveError(reason instanceof Error ? reason.message : 'No se pudo quitar el currículum.')
    } finally {
      setBusy(false)
    }
  }

  async function updateNickname(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    try {
      setCandidate(await saveNickname(nickname.trim()))
      notifications.success('Nombre visible actualizado.')
    } catch (reason) {
      notifications.error(reason instanceof Error ? reason.message : 'No se pudo actualizar el nombre visible.')
    } finally {
      setBusy(false)
    }
  }

  const primary = resumes.find((resume) => resume.is_primary)
  const others = resumes.filter((resume) => !resume.is_primary)

  return <>
    <Header title="Perfil" screen="dashboard" />
    <div className="profile-content">
      <section className="panel profile-person" aria-label="Datos de perfil">
        <button className="profile-avatar" aria-label="Agregar o cambiar foto de perfil" onClick={() => photoInput.current?.click()}>
          {candidate?.avatar_url ? <img src={candidate.avatar_url} alt="" /> : <Asset screen="dashboard" name="imgAvatar" />}
          <span className="edit-avatar" aria-hidden="true">✎</span>
        </button>
        <input ref={photoInput} className="visually-hidden" type="file" accept="image/png,image/jpeg,image/webp" aria-label="Seleccionar foto" onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ''; if (file) { if (file.size > 5 * 1024 * 1024 || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) notifications.error('Elegí una imagen JPG, PNG o WebP de hasta 5 MB.'); else setPhoto(file) } }} />
        <div className="profile-name"><h2>Tu apodo</h2>
          <form onSubmit={(event) => void updateNickname(event)}>
            <label className="field">Nombre visible<input value={nickname} maxLength={100} required onChange={(event) => setNickname(event.target.value)} /></label>
            <button className="primary" disabled={busy || !nickname.trim()}>Guardar</button>
          </form>
          <p className="helper">Este nombre aparecerá junto a tu foto en el encabezado.</p>
        </div>
      </section>
      <div className="profile-resumes">
        <p className="intro">Tu CV se utilizará para comparar tu perfil con las oportunidades laborales y evaluar tu compatibilidad.</p>
        <section className="panel upload-panel"><h2>Cargá tu currículum</h2>
          <div className={`dropzone ${dragging ? 'dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true) }} onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false) }} onDrop={(event) => { event.preventDefault(); setDragging(false); void addResume(event.dataTransfer.files[0]) }}>
            <Asset screen="resume" name="imgUploadIcon" />
            <h3>Arrastrá y soltá tu CV aquí</h3><p>Formato PDF · Máximo 5 MB</p>
            <button className="primary" disabled={busy} onClick={() => cvInput.current?.click()}>Seleccionar PDF</button>
            <input ref={cvInput} className="visually-hidden" type="file" accept=".pdf,application/pdf" aria-label="Seleccionar currículum PDF" onChange={(event) => { void addResume(event.target.files?.[0]); event.target.value = '' }} />
          </div>
        </section>
        <section className="panel current-cv"><div className="cv-heading"><h2>Currículum principal</h2>{primary && <span className="pill green">Principal</span>}</div>
          {primary ? <div className="file-details"><div className="pdf-badge"><Asset screen="resume" name="imgFile1" /><span>PDF</span></div><div className="file-meta"><strong>{primary.filename}</strong><p>Fecha de carga: {new Date(primary.uploaded_at).toLocaleDateString('es-AR')}</p></div><button className="secondary profile-delete" type="button" disabled={busy} aria-label={`Eliminar currículum ${primary.filename}`} onClick={() => { setRemoveError(''); setSelectedResume(primary) }}><TrashIcon aria-hidden="true" />Eliminar</button></div> : <p>Tu currículum principal aparecerá aquí cuando cargues un PDF.</p>}
        </section>
        {others.length > 0 && <section className="profile-other-cvs" aria-label="Otros currículums"><h2>Otros currículums</h2>
          <ul className="profile-cv-list">{others.map((resume) => <li className="panel current-cv" key={resume.id}>
            <div className="file-details"><div className="pdf-badge"><Asset screen="resume" name="imgFile1" /><span>PDF</span></div><div className="file-meta"><strong>{resume.filename}</strong><p>Fecha de carga: {new Date(resume.uploaded_at).toLocaleDateString('es-AR')}</p></div><div className="profile-cv-actions"><button className="secondary" type="button" disabled={busy} onClick={() => void makePrimary(resume.id)}>Elegir como principal</button><button className="secondary profile-delete" type="button" disabled={busy} aria-label={`Eliminar currículum ${resume.filename}`} onClick={() => { setRemoveError(''); setSelectedResume(resume) }}><TrashIcon aria-hidden="true" />Eliminar</button></div></div>
          </li>)}</ul>
        </section>}
      </div>
    </div>
    {photo && <CropPhoto file={photo} onClose={() => setPhoto(null)} onSaved={(saved) => { setCandidate(saved); setPhoto(null); notifications.success('Foto de perfil actualizada.') }} />}
    {selectedResume && <Modal title="¿Eliminar currículum del perfil?" onClose={() => { if (!busy) setSelectedResume(null) }}>
      <p>«{selectedResume.filename}» dejará de aparecer en tu perfil. El archivo y los datos relacionados se conservarán.{selectedResume.is_primary && resumes.length > 1 ? ' Otro currículum pasará a ser principal.' : ''}</p>
      {removeError && <p className="field-error" role="alert">{removeError}</p>}
      <button className="primary" type="button" disabled={busy} onClick={() => void confirmRemove()}>{busy ? 'Eliminando…' : 'Sí, eliminar del perfil'}</button>
    </Modal>}
  </>
}
