import type { ServerMessage } from '../../src/contracts/generated'

export class MockWebSocket {
  static instances: MockWebSocket[] = []
  url: string
  readyState = 0
  sent: unknown[] = []
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onerror: (() => void) | null = null

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  static latest(): MockWebSocket {
    const ws = MockWebSocket.instances.at(-1)
    if (!ws) throw new Error('no socket created')
    return ws
  }

  send(data: string) {
    this.sent.push(JSON.parse(data))
  }

  close() {
    this.readyState = 3
  }

  open() {
    this.readyState = 1
    this.onopen?.()
  }

  receive(message: ServerMessage) {
    this.onmessage?.({ data: JSON.stringify(message) })
  }

  drop(code = 1006) {
    this.readyState = 3
    this.onclose?.({ code })
  }
}
