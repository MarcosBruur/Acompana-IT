import { createContext, useContext } from 'react'

export type Notifications = { success: (message: string) => void; error: (message: string) => void; info: (message: string) => void }

export const NotificationsContext = createContext<Notifications | null>(null)

export function useNotifications() {
  const context = useContext(NotificationsContext)
  if (!context) throw new Error('Las notificaciones deben usarse dentro de NotificationsProvider.')
  return context
}
