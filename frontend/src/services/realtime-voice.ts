import { API_BASE_URL } from './api'

type VoiceEvents = {
  onStatus: (status: 'connecting' | 'ready' | 'speaking' | 'blocked') => void
  onSpeaking: (speaking: boolean) => void
  onPlaybackStart: () => void
  onTranscript: (delta: string) => void
  onPlaybackEnd: () => void
  onError: () => void
}

type SpokenPart = { key: string; text: string }

/** El navegador recibe audio; el servidor selecciona el texto autorizado desde la DB. */
export class RealtimeVoice {
  private socket: WebSocket | null = null
  private context: AudioContext | null = null
  private sources = new Set<AudioBufferSourceNode>()
  private nextTime = 0
  private pending: { keys: string[]; onFinished?: () => void } | null = null
  private onFinished: (() => void) | null = null
  private events: VoiceEvents
  private closed = false
  private active = false
  private finishedGenerating = false
  private playbackStarted = false

  constructor(events: VoiceEvents) { this.events = events }

  async connect(interviewId: number) {
    if (!('WebSocket' in window) || !('AudioContext' in window)) throw new Error('Audio no disponible')
    this.events.onStatus('connecting')
    const url = new URL(`${API_BASE_URL}/interviews/${interviewId}/voice`, window.location.href)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(url)
    this.socket = socket
    await new Promise<void>((resolve, reject) => {
      let ready = false
      const timer = window.setTimeout(() => { if (!ready) { socket.close(); reject(new Error('La voz tardó demasiado')) } }, 15000)
      socket.onmessage = (event: MessageEvent<string>) => {
        if (this.closed) return
        try {
          const message = JSON.parse(event.data) as { type: string; delta?: string; failed?: boolean }
          if (message.type === 'ready') {
            ready = true; clearTimeout(timer); resolve()
            this.events.onStatus('ready')
            if (this.pending) {
              const pending = this.pending
              this.pending = null
              this.send(pending.keys, pending.onFinished)
            }
          } else if (message.type === 'audio' && message.delta) {
            this.playChunk(message.delta)
          } else if (message.type === 'transcript' && message.delta) {
            this.events.onTranscript(message.delta)
          } else if (message.type === 'done') {
            if (message.failed) { this.fail(); return }
            this.finishedGenerating = true
            this.completeIfPlayed()
          } else if (message.type === 'error') this.fail()
        } catch { this.fail() }
      }
      socket.onerror = () => { if (!ready) { clearTimeout(timer); reject(new Error('No se pudo conectar la voz')) } else this.fail() }
      socket.onclose = () => { if (!this.closed) {
        if (!ready) { clearTimeout(timer); reject(new Error('No se pudo conectar la voz')) }
        else this.fail()
      } }
    })
  }

  speak(parts: SpokenPart[], onFinished?: () => void) {
    if (this.closed || !parts.length) return
    const keys = parts.map((part) => part.key)
    if (this.socket?.readyState !== WebSocket.OPEN) {
      this.pending = { keys, onFinished }
      return
    }
    this.send(keys, onFinished)
  }

  private send(keys: string[], onFinished?: () => void) {
    this.stop()
    this.active = true
    this.finishedGenerating = false
    this.onFinished = onFinished ?? null
    this.events.onSpeaking(true)
    this.socket?.send(JSON.stringify({ type: 'speak', keys }))
  }

  private playChunk(base64: string) {
    if (!this.active) return
    if (!this.context) this.context = new AudioContext({ sampleRate: 24000 })
    const context = this.context
    if (context.state !== 'running') {
      void context.resume().catch(() => { if (!this.closed) this.events.onStatus('blocked') })
      window.setTimeout(() => { if (!this.closed && this.active && context.state !== 'running') this.events.onStatus('blocked') }, 1200)
    }
    const bytes = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0))
    if (bytes.length < 2 || bytes.length % 2) return
    const samples = new Int16Array(bytes.length / 2)
    const view = new DataView(bytes.buffer)
    for (let i = 0; i < samples.length; i++) samples[i] = view.getInt16(i * 2, true)
    const buffer = context.createBuffer(1, samples.length, 24000)
    const channel = buffer.getChannelData(0)
    for (let i = 0; i < samples.length; i++) channel[i] = samples[i] / 32768
    const source = context.createBufferSource()
    source.buffer = buffer
    source.connect(context.destination)
    source.onended = () => { this.sources.delete(source); this.completeIfPlayed() }
    this.sources.add(source)
    if (!this.playbackStarted) {
      this.playbackStarted = true
      this.events.onPlaybackStart()
      this.events.onStatus('speaking')
    }
    const at = Math.max(context.currentTime + 0.04, this.nextTime)
    source.start(at)
    this.nextTime = at + buffer.duration
  }

  private completeIfPlayed() {
    if (!this.active || !this.finishedGenerating || this.sources.size) return
    this.active = false
    this.playbackStarted = false
    this.nextTime = 0
    this.events.onPlaybackEnd()
    this.events.onSpeaking(false)
    this.events.onStatus('ready')
    const finished = this.onFinished
    this.onFinished = null
    finished?.()
  }

  stop() {
    this.pending = null
    this.onFinished = null
    if (this.active && !this.finishedGenerating && this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type: 'stop' }))
    }
    this.active = false
    this.finishedGenerating = false
    this.playbackStarted = false
    this.nextTime = 0
    for (const source of this.sources) { source.onended = null; try { source.stop() } catch { /* Ya finalizado */ } }
    this.sources.clear()
    this.events.onSpeaking(false)
  }

  resumeAudio() { if (this.context) void this.context.resume().catch(() => this.events.onStatus('blocked')) }

  private fail() {
    if (this.closed) return
    this.close()
    this.events.onError()
  }

  close() {
    if (this.closed) return
    this.closed = true
    this.stop()
    this.socket?.close()
    this.socket = null
    if (this.context) void this.context.close()
    this.context = null
  }
}
