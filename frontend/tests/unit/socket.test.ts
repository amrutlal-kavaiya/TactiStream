import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { MatchSocket } from '../../src/api/socket'
import type { ServerMessage } from '../../src/contracts/generated'
import { heartbeat } from './fixtures'

class MockWebSocket {
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

const latest = () => {
  const ws = MockWebSocket.instances.at(-1)
  if (!ws) throw new Error('no socket created')
  return ws
}

let received: ServerMessage[]
let lastSeq: number

function connect() {
  const socket = new MatchSocket({
    url: 'ws://test/ws/matches/m1',
    onMessage: (m) => received.push(m),
    getLastSeq: () => lastSeq,
    WebSocketImpl: MockWebSocket as unknown as typeof WebSocket,
  })
  socket.connect()
  return socket
}

beforeEach(() => {
  vi.useFakeTimers()
  MockWebSocket.instances = []
  received = []
  lastSeq = 0
})

afterEach(() => {
  vi.useRealTimers()
})

describe('MatchSocket', () => {
  it('passes parsed server messages to onMessage', () => {
    connect()
    latest().open()
    latest().receive(heartbeat(3, 1000))

    expect(received).toEqual([heartbeat(3, 1000)])
  })

  it('does not send resume on the first connection', () => {
    connect()
    latest().open()

    expect(latest().sent).toEqual([])
  })

  it('sends resume with lastSeq when it reconnects', () => {
    connect()
    latest().open()
    lastSeq = 42
    latest().drop()
    vi.advanceTimersByTime(500)
    latest().open()

    expect(MockWebSocket.instances).toHaveLength(2)
    expect(latest().sent).toEqual([{ type: 'resume', last_seq: 42 }])
  })

  it('backs off 500, 1000, 2000 ms and caps at 8000 ms', () => {
    connect()
    const delays = [500, 1000, 2000, 4000, 8000, 8000]
    for (const [i, delay] of delays.entries()) {
      latest().drop()
      vi.advanceTimersByTime(delay - 1)
      expect(MockWebSocket.instances).toHaveLength(i + 1)
      vi.advanceTimersByTime(1)
      expect(MockWebSocket.instances).toHaveLength(i + 2)
    }
  })

  it('resets the backoff once a message arrives', () => {
    connect()
    latest().drop()
    vi.advanceTimersByTime(500)
    latest().drop()
    vi.advanceTimersByTime(1000)
    latest().open()
    latest().receive(heartbeat(1, 0))
    latest().drop()
    vi.advanceTimersByTime(500)

    expect(MockWebSocket.instances).toHaveLength(4)
  })

  it('reconnects after 25 s without messages', () => {
    connect()
    const first = latest()
    first.open()
    first.receive(heartbeat(1, 0))
    vi.advanceTimersByTime(20_000)
    first.receive(heartbeat(2, 10_000))
    vi.advanceTimersByTime(24_999)
    expect(first.readyState).toBe(1)

    vi.advanceTimersByTime(1)
    expect(first.readyState).toBe(3)
    vi.advanceTimersByTime(500)
    expect(MockWebSocket.instances).toHaveLength(2)
  })

  it('does not reconnect after close()', () => {
    const socket = connect()
    latest().open()
    socket.close()
    latest().drop(1000)
    vi.advanceTimersByTime(60_000)

    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('does not reconnect when the server does not know the match (4404)', () => {
    connect()
    latest().drop(4404)
    vi.advanceTimersByTime(60_000)

    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('sends display_ack once per target', () => {
    const socket = connect()
    latest().open()
    socket.ackDisplay('insight', 'ins-0042', 11)
    socket.ackDisplay('insight', 'ins-0042', 12)
    socket.ackDisplay('insight', 'ins-0043', 13)

    expect(latest().sent).toEqual([
      { type: 'display_ack', target_kind: 'insight', target_id: 'ins-0042', server_seq: 11 },
      { type: 'display_ack', target_kind: 'insight', target_id: 'ins-0043', server_seq: 13 },
    ])
  })

  it('sends display_ack later if the socket was not open yet', () => {
    const socket = connect()
    socket.ackDisplay('insight', 'ins-0042', 11)
    latest().open()
    socket.ackDisplay('insight', 'ins-0042', 11)

    expect(latest().sent).toEqual([
      { type: 'display_ack', target_kind: 'insight', target_id: 'ins-0042', server_seq: 11 },
    ])
  })
})
