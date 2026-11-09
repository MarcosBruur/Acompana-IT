import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { NotificationsContext, type Notifications } from './notifications-context'
import './notifications.css'

type Kind = 'success' | 'error' | 'info'
type Notice = { id: number; message: string; kind: Kind }
export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [notices, setNotices] = useState<Notice[]>([])
  const nextId = useRef(0)
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>())

  useEffect(() => () => { for (const timer of timers.current.values()) clearTimeout(timer) }, [])
  useEffect(() => {
    const active = new Set(notices.map(({ id }) => id))
    for (const [id, timer] of timers.current) {
      if (!active.has(id)) { clearTimeout(timer); timers.current.delete(id) }
    }
  }, [notices])

  const dismiss = useCallback((id: number) => {
    const timer = timers.current.get(id)
    if (timer) clearTimeout(timer)
    timers.current.delete(id)
    setNotices((current) => current.filter((notice) => notice.id !== id))
  }, [])

  const notify = useCallback((message: string, kind: Kind) => {
    const id = ++nextId.current
    setNotices((current) => [...current.slice(-2), { id, message, kind }])
    timers.current.set(id, setTimeout(() => dismiss(id), kind === 'error' ? 8000 : 5000))
  }, [dismiss])
  const value = useMemo<Notifications>(() => ({
    success: (message) => notify(message, 'success'),
    error: (message) => notify(message, 'error'),
    info: (message) => notify(message, 'info'),
  }), [notify])

  return <NotificationsContext.Provider value={value}>
    {children}
    <div className="notifications" aria-label="Notificaciones">
      {notices.map((notice) => <div className={`notification notification-${notice.kind}`} key={notice.id} role={notice.kind === 'error' ? 'alert' : 'status'}>
        <span className="notification-icon" aria-hidden="true">{notice.kind === 'success' ? '✓' : notice.kind === 'error' ? '!' : 'i'}</span>
        <span className="notification-message">{notice.message}</span>
        <button type="button" className="notification-dismiss" aria-label={`Cerrar notificación: ${notice.message}`} onClick={() => dismiss(notice.id)}>×</button>
      </div>)}
    </div>
  </NotificationsContext.Provider>
}
