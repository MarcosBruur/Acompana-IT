import { getInterviewVoiceToken } from './interviews'

type VoiceEvents = {
  onStatus: (status: 'connecting' | 'ready' | 'speaking' | 'blocked') => void
  onSpeaking: (speaking: boolean) => void
  onPlaybackStart: () => void
  onTranscript: (delta: string) => void
  onPlaybackEnd: () => void
  onError: () => void
}

/** La conexión solo recibe audio: el micrófono permanece en el dictado del navegador. */
export class RealtimeVoice {
  private events: VoiceEvents
  private pc: RTCPeerConnection | null = null
  private channel: RTCDataChannel | null = null
  private audio: HTMLAudioElement | null = null
  private abort = new AbortController()
  private closed = false
  private active = false
  private generating = false
  private responseId: string | null = null
  private pending: string | null = null
  private pendingFinished: (() => void) | null = null
  private onFinished: (() => void) | null = null
  private lastText: string | null = null
  private blocked = false

  constructor(events: VoiceEvents) { this.events = events }

  async connect(interviewId: number) {
    if (!('RTCPeerConnection' in window)) throw new Error('WebRTC no disponible')
    this.events.onStatus('connecting')
    const { value } = await getInterviewVoiceToken(interviewId)
    if (this.closed) return
    const pc = new RTCPeerConnection()
    this.pc = pc
    pc.addTransceiver('audio', { direction: 'recvonly' })
    const audio = document.createElement('audio')
    audio.autoplay = true
    this.audio = audio
    pc.ontrack = (event) => {
      audio.srcObject = event.streams[0] ?? new MediaStream([event.track])
      void audio.play().catch(() => { if (!this.closed) { this.blocked = true; this.events.onStatus('blocked') } })
    }
    pc.onconnectionstatechange = () => {
      if (!this.closed && (pc.connectionState === 'failed' || pc.connectionState === 'closed')) this.fail()
    }
    const channel = pc.createDataChannel('oai-events')
    this.channel = channel
    channel.onopen = () => {
      if (this.closed) return
      this.events.onStatus(this.blocked ? 'blocked' : 'ready')
      if (this.pending) {
        const text = this.pending
        const onFinished = this.pendingFinished ?? undefined
        this.pending = null
        this.pendingFinished = null
        this.speak(text, onFinished)
      }
    }
    channel.onclose = () => { if (!this.closed) this.fail() }
    channel.onmessage = (event: MessageEvent<string>) => {
      if (this.closed) return
      try {
        const message = JSON.parse(event.data) as { type?: string; response_id?: string; delta?: string; response?: { id?: string; status?: string } }
        if (message.type === 'response.created') {
          this.responseId = message.response?.id ?? null
          return
        }
        if (message.response_id && message.response_id !== this.responseId) return
        if (message.type === 'output_audio_buffer.started') {
          this.events.onPlaybackStart()
          this.events.onStatus(this.blocked ? 'blocked' : 'speaking')
        } else if (message.type === 'response.output_audio_transcript.delta' && message.delta) {
          this.events.onTranscript(message.delta)
        } else if (message.type === 'output_audio_buffer.stopped' || message.type === 'output_audio_buffer.cleared') {
          if (message.type === 'output_audio_buffer.stopped') this.events.onPlaybackEnd()
          this.active = false
          this.events.onSpeaking(false)
          this.events.onStatus(this.blocked ? 'blocked' : 'ready')
          if (message.type === 'output_audio_buffer.stopped' && !this.blocked) {
            const onFinished = this.onFinished
            this.onFinished = null
            onFinished?.()
          }
        } else if (message.type === 'response.done') {
          if (message.response?.id === this.responseId) {
            this.generating = false
            if (message.response?.status === 'failed') this.fail()
          }
        } else if (message.type === 'error') {
          this.fail()
        }
      } catch { /* Ignorar eventos desconocidos sin exponer contenido del proveedor. */ }
    }

    const timeout = setTimeout(() => this.abort.abort(), 20000)
    try {
      const offer = await pc.createOffer()
      if (this.closed) return
      await pc.setLocalDescription(offer)
      const answer = await fetch('https://api.openai.com/v1/realtime/calls', {
        method: 'POST', body: offer.sdp,
        headers: { Authorization: `Bearer ${value}`, 'Content-Type': 'application/sdp' },
        signal: this.abort.signal,
      })
      if (!answer.ok) throw new Error('No se pudo establecer la conexión de audio')
      const sdp = await answer.text()
      if (this.closed) return
      await pc.setRemoteDescription({ type: 'answer', sdp })
      await new Promise<void>((resolve, reject) => {
        if (channel.readyState === 'open') { resolve(); return }
        const onOpen = () => { clearTimeout(wait); resolve() }
        const wait = setTimeout(() => {
          channel.removeEventListener('open', onOpen)
          reject(new Error('La conexión de voz tardó demasiado'))
        }, 12000)
        channel.addEventListener('open', onOpen, { once: true })
      })
    } finally { clearTimeout(timeout) }
  }

  speak(text: string, onFinished?: () => void) {
    if (this.closed || !text.trim()) return
    this.lastText = text
    if (this.channel?.readyState !== 'open') {
      this.pending = text
      this.pendingFinished = onFinished ?? null
      return
    }
    this.stop()
    this.onFinished = onFinished ?? null
    this.active = true
    this.generating = true
    this.responseId = null
    this.events.onSpeaking(true)
    this.events.onStatus(this.blocked ? 'blocked' : 'ready')
    if (this.audio?.srcObject) void this.audio.play().catch(() => { this.blocked = true; this.events.onStatus('blocked') })
    this.channel.send(JSON.stringify({
      type: 'response.create',
      response: {
        conversation: 'none', output_modalities: ['audio'], max_output_tokens: 2000,
        // response.create.instructions reemplaza las instrucciones de la sesión en esta intervención.
        instructions: 'Leé literalmente el texto proporcionado en español rioplatense de Argentina, con acento argentino natural y sutil. Mantené una entonación cálida, pausas breves y ritmo conversacional; no exageres el acento ni cambies de idioma. No agregues comentarios ni cambies la corrección.',
        input: [{ type: 'message', role: 'user', content: [{ type: 'input_text', text: text.slice(0, 1400) }] }],
      },
    }))
  }

  stop() {
    this.pending = null
    this.pendingFinished = null
    this.onFinished = null
    if (this.channel?.readyState === 'open' && this.active) {
      if (this.generating) this.channel.send(JSON.stringify({ type: 'response.cancel' }))
      this.channel.send(JSON.stringify({ type: 'output_audio_buffer.clear' }))
    }
    this.active = false
    this.generating = false
    this.responseId = null
    this.audio?.pause()
    this.events.onSpeaking(false)
  }

  resumeAudio() {
    if (this.audio?.srcObject) void this.audio.play().then(() => {
      this.blocked = false
      const text = this.lastText
      const onFinished = this.onFinished ?? this.pendingFinished ?? undefined
      this.stop()
      if (text) this.speak(text, onFinished)
    }).catch(() => { this.blocked = true; this.events.onStatus('blocked') })
  }

  private fail() {
    if (this.closed) return
    this.close()
    this.events.onError()
  }

  close() {
    if (this.closed) return
    this.closed = true
    this.abort.abort()
    this.stop()
    this.channel?.close()
    this.pc?.close()
    if (this.audio) this.audio.srcObject = null
    this.channel = null
    this.pc = null
    this.audio = null
  }
}
