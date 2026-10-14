import type { ClientMessage, ServerMessage } from '../contracts/generated'

export const BACKOFF_START_MS = 500
export const BACKOFF_MAX_MS = 8000
export const SILENCE_TIMEOUT_MS = 25_000
const CLOSE_UNKNOWN_MATCH = 4404
const OPEN = 1

export interface MatchSocketOptions {
  url: string
  onMessage: (message: ServerMessage) => void
  getLastSeq: () => number
  WebSocketImpl?: typeof WebSocket
}

/** One match stream: snapshot on connect, `resume` with the last seq on reconnect, backoff, silence watchdog. */
export class MatchSocket {
  private readonly options: MatchSocketOptions
  private ws: WebSocket | null = null
  private connectedOnce = false
  private closed = false
  private backoffMs = BACKOFF_START_MS
  private reconnectTimer: ReturnType<typeof setTimeout> | undefined
  private silenceTimer: ReturnType<typeof setTimeout> | undefined
  private readonly acked = new Set<string>()
  private readonly pendingAcks = new Map<string, ClientMessage>()

  constructor(options: MatchSocketOptions) {
    this.options = options
  }

  connect() {
    const Impl = this.options.WebSocketImpl ?? WebSocket
    const ws = new Impl(this.options.url)
    this.ws = ws
    ws.onopen = () => {
      if (this.connectedOnce) this.send({ type: 'resume', last_seq: this.options.getLastSeq() })
      this.connectedOnce = true
      this.flushAcks()
      this.armWatchdog()
    }
    ws.onmessage = (event: MessageEvent<string>) => {
      this.backoffMs = BACKOFF_START_MS
      this.armWatchdog()
      this.options.onMessage(JSON.parse(event.data) as ServerMessage)
    }
    ws.onclose = (event: CloseEvent) => {
      if (event.code === CLOSE_UNKNOWN_MATCH) this.closed = true
      this.handleDrop()
    }
  }

  /** Records a fast-overlay latency sample on the server; only the first display of a target counts.
   * Sent once the socket is open if it is not open yet. */
  ackDisplay(targetKind: 'event' | 'insight', targetId: string, serverSeq: number) {
    const key = `${targetKind}:${targetId}`
    if (this.acked.has(key)) return
    this.acked.add(key)
    const ack: ClientMessage = {
      type: 'display_ack',
      target_kind: targetKind,
      target_id: targetId,
      server_seq: serverSeq,
    }
    if (!this.send(ack)) this.pendingAcks.set(key, ack)
  }

  close() {
    this.closed = true
    clearTimeout(this.reconnectTimer)
    clearTimeout(this.silenceTimer)
    this.detach()?.close()
  }

  private send(message: ClientMessage): boolean {
    if (this.ws?.readyState !== OPEN) return false
    this.ws.send(JSON.stringify(message))
    return true
  }

  private flushAcks() {
    for (const [key, ack] of this.pendingAcks) {
      if (!this.send(ack)) return
      this.pendingAcks.delete(key)
    }
  }

  private armWatchdog() {
    clearTimeout(this.silenceTimer)
    this.silenceTimer = setTimeout(() => {
      this.detach()?.close()
      this.handleDrop()
    }, SILENCE_TIMEOUT_MS)
  }

  private detach(): WebSocket | null {
    const ws = this.ws
    if (ws) {
      ws.onopen = ws.onmessage = ws.onclose = null
    }
    this.ws = null
    return ws
  }

  private handleDrop() {
    clearTimeout(this.silenceTimer)
    this.detach()
    if (this.closed) return
    const delay = this.backoffMs
    this.backoffMs = Math.min(this.backoffMs * 2, BACKOFF_MAX_MS)
    this.reconnectTimer = setTimeout(() => {
      this.connect()
    }, delay)
  }
}
