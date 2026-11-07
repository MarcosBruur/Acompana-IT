import { useEffect, useId, useRef, type ReactNode } from 'react'
import { useAuth } from '../features/auth-context'
import { Link } from 'react-router-dom'

export type DesignScreen =
  | 'login'
  | 'registration'
  | 'dashboard'
  | 'resume'
  | 'vacancy'
  | 'analysis'
  | 'interview'
export function Asset({
  screen,
  name,
  className = '',
}: {
  screen: DesignScreen
  name: string
  className?: string
}) {
  return (
    <img
      className={`design-asset ${className}`}
      src={`/figma/${screen}-${name}.svg`}
      alt=""
      aria-hidden="true"
    />
  )
}
export function Header({
  title,
  screen,
}: {
  title: string
  screen: DesignScreen
}) {
  const { candidate } = useAuth()
  return (
    <header className="page-header">
      <h1>{title}</h1>
      <Link className="user-pill" to="/perfil" aria-label={`Ir a perfil de ${candidate?.nickname || candidate?.first_name || 'visitante'}`}>
        {candidate?.avatar_url ? <img className="avatar-thumb" src={candidate.avatar_url} alt="" /> : <Asset screen={screen} name="imgAvatar" />}
        <span>{candidate?.nickname || candidate?.first_name || 'Visitante'}</span>
      </Link>
    </header>
  )
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string
  children: ReactNode
  onClose: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  useEffect(() => {
    const dialog = ref.current
    dialog?.showModal()
    dialog?.querySelector<HTMLButtonElement>('[autofocus]')?.focus()
    return () => dialog?.close()
  }, [])
  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby={titleId}
      onCancel={onClose}
    >
      <h2 id={titleId}>{title}</h2>
      {children}
      <button className="secondary" onClick={onClose} autoFocus>
        Volver
      </button>
    </dialog>
  )
}
export function PreviewNotice() {
  return (
    <p className="preview-notice">
      Algunas vistas aún contienen datos de ejemplo · Comparaciones y voz pendientes de integración.
    </p>
  )
}
