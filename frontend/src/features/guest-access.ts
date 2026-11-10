import type { MouseEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './auth-context'

type GuestArea = 'profile' | 'interviews'
type GuestPromptState = { accessPrompt?: GuestArea; [key: string]: unknown }

export function useGuestAccessLink(area: GuestArea) {
  const { candidate } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  return (event: MouseEvent<HTMLAnchorElement>) => {
    if (candidate || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    const state = (location.state ?? {}) as GuestPromptState
    navigate(`${location.pathname}${location.search}${location.hash}`, {
      replace: true,
      state: { ...state, accessPrompt: area },
    })
  }
}
