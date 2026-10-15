import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../../src/App'
import type { ServerMessage } from '../../src/contracts/generated'
import { useMatchStore } from '../../src/store/matchStore'
import { event, eventMessage, insight, insightMessage, MATCH_ID, snapshot } from './fixtures'
import { MockWebSocket } from './mockWebSocket'

const session = { session_id: 's-1', match_id: MATCH_ID, ws_path: `/ws/matches/${MATCH_ID}` }
const controlPath = `POST /api/matches/${MATCH_ID}/control`
const playback = (state: 'playing' | 'paused') => ({
  playback: { state, speed: 1, seed: 42 },
  session_clock_ms: 0,
})

let routes: Record<string, () => Response>
let calls: [string, unknown][]

const json = (status: number, body: unknown) => () => new Response(JSON.stringify(body), { status })

beforeEach(() => {
  localStorage.clear()
  MockWebSocket.instances = []
  calls = []
  routes = {
    'POST /api/sessions': json(200, session),
    [controlPath]: json(200, playback('playing')),
  }
  vi.stubGlobal('WebSocket', MockWebSocket)
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) =>
    setTimeout(() => {
      cb(0)
    }, 0),
  )
  vi.stubGlobal('cancelAnimationFrame', (id: number) => {
    clearTimeout(id)
  })
  vi.stubGlobal(
    'fetch',
    vi.fn((path: string, init?: RequestInit) => {
      const key = `${init?.method ?? 'GET'} ${path}`
      calls.push([key, typeof init?.body === 'string' ? JSON.parse(init.body) : undefined])
      const route = routes[key]
      return Promise.resolve(route ? route() : new Response('not routed', { status: 500 }))
    }),
  )
  const store = useMatchStore.getState()
  store.startSession(null)
  store.setPrefs({ mode: 'fan', language: 'en' })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

async function startMatch() {
  const user = userEvent.setup()
  render(<App />)
  await user.click(screen.getByRole('button', { name: 'Start demo match' }))
  await waitFor(() => {
    expect(MockWebSocket.instances).toHaveLength(1)
  })
  const ws = MockWebSocket.latest()
  act(() => {
    ws.open()
  })
  return { user, ws }
}

function deliver(ws: MockWebSocket, ...messages: ServerMessage[]) {
  act(() => {
    for (const message of messages) ws.receive(message)
  })
}

describe('App', () => {
  it('renders the product name', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'TactiStream' })).toBeInTheDocument()
  })

  it('disables playback controls until a session exists', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: 'Pause' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Reset' })).toBeDisabled()
  })

  it('creates a session, connects the match socket and starts playback', async () => {
    const { ws } = await startMatch()

    expect(ws.url).toBe(`ws://${window.location.host}/ws/matches/${MATCH_ID}`)
    await waitFor(() => {
      expect(calls).toContainEqual([controlPath, { action: 'play' }])
    })
    expect(calls[0]).toEqual(['POST /api/sessions', { scenario: 'skeleton' }])
  })

  it('shows the source badge, event list, session clock and card from socket messages', async () => {
    const { ws } = await startMatch()
    deliver(
      ws,
      snapshot(5, { events: [event('evt-0001', { event_type: 'kickoff', session_clock_ms: 0 })] }),
      eventMessage(6, event('evt-0042')),
      insightMessage(7, insight('ins-0042')),
    )

    expect(screen.getByTestId('source-badge')).toHaveTextContent('Synthetic')
    const events = screen.getByRole('table', { name: 'Events' })
    const rows = within(events).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(2)
    expect(rows[1]).toHaveTextContent('pass')
    expect(screen.getByTestId('session-clock')).toHaveTextContent('00:03')
    expect(screen.getByRole('heading', { name: 'ins-0042 title fan en' })).toBeInTheDocument()
  })

  it('acknowledges the displayed card over the socket', async () => {
    const { ws } = await startMatch()
    deliver(ws, snapshot(5), insightMessage(7, insight('ins-0042')))

    await waitFor(() => {
      expect(ws.sent).toContainEqual({
        type: 'display_ack',
        target_kind: 'insight',
        target_id: 'ins-0042',
        server_seq: 7,
      })
    })
  })

  it('opens evidence from the card in the viewer language and returns focus on close', async () => {
    routes[`GET /api/matches/${MATCH_ID}/evidence/evt-0042?language=en`] = json(200, {
      evidence_id: 'evt-0042',
      kind: 'event',
      record: event('evt-0042'),
    })
    const { user, ws } = await startMatch()
    deliver(ws, snapshot(5), insightMessage(7, insight('ins-0042')))

    const chip = screen.getByRole('button', { name: 'evt-0042' })
    await user.click(chip)
    const dialog = await screen.findByRole('dialog', { name: 'Evidence evt-0042' })
    expect(await screen.findByText('blue-08')).toBeInTheDocument()
    expect(dialog).toHaveTextContent('pass')

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(chip).toHaveFocus()
  })

  it('pauses and resets through the control endpoint; the reset snapshot hides the card', async () => {
    const { user, ws } = await startMatch()
    deliver(ws, snapshot(5), insightMessage(7, insight('ins-0042')))

    routes[controlPath] = json(200, playback('paused'))
    await user.click(screen.getByRole('button', { name: 'Pause' }))
    await user.click(screen.getByRole('button', { name: 'Reset' }))
    expect(calls).toContainEqual([controlPath, { action: 'pause' }])
    expect(calls).toContainEqual([controlPath, { action: 'reset' }])

    deliver(ws, snapshot(9))
    expect(screen.queryByTestId('insight-card')).not.toBeInTheDocument()
  })

  it.each([
    [503, 'session_start_timeout', 'The demo match took too long to start. Please try again.'],
    [422, 'invalid_scenario', 'The demo scenario is not available on this server.'],
  ])('shows a short message when session creation fails with %i', async (status, code, message) => {
    routes['POST /api/sessions'] = json(status, { error: code, detail: 'x' })
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Start demo match' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(MockWebSocket.instances).toHaveLength(0)
  })

  it('keeps the session and asks for Play when the first play command fails', async () => {
    routes[controlPath] = json(503, { error: 'unexpected', detail: 'x' })
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Start demo match' }))
    expect(await screen.findByRole('alert')).toHaveTextContent("Playback didn't start — press Play.")
    expect(MockWebSocket.instances).toHaveLength(1)
    expect(MockWebSocket.latest().readyState).not.toBe(3)
    expect(screen.getByRole('button', { name: 'Play' })).toBeEnabled()
  })

  it('switches the card variant and chrome strings to Hindi', async () => {
    const { ws } = await startMatch()
    deliver(ws, snapshot(5), insightMessage(7, insight('ins-0042')))

    act(() => {
      useMatchStore.getState().setPrefs({ mode: 'fan', language: 'hi' })
    })

    expect(screen.getByRole('heading', { name: 'ins-0042 title fan hi' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'डेमो मैच शुरू करें' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('hi')
  })

  it('switches the card variant to Analyst mode', async () => {
    const { ws } = await startMatch()
    deliver(ws, snapshot(5), insightMessage(7, insight('ins-0042')))

    act(() => {
      useMatchStore.getState().setPrefs({ mode: 'analyst', language: 'en' })
    })

    expect(screen.getByRole('heading', { name: 'ins-0042 title analyst en' })).toBeInTheDocument()
  })

  it('does not render the mode or language controls before they are wired (006)', () => {
    render(<App />)
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(screen.queryByText('Analyst')).not.toBeInTheDocument()
  })

  it('groups Start, Play, Pause and Reset in the playback toolbar', () => {
    render(<App />)
    const toolbar = screen.getByRole('toolbar', { name: 'Playback' })
    for (const name of ['Start demo match', 'Play', 'Pause', 'Reset']) {
      expect(within(toolbar).getByRole('button', { name })).toBeInTheDocument()
    }
  })

  it('shows the connection status as text: Offline, then Live, then Paused', async () => {
    render(<App />)
    expect(screen.getByTestId('connection-status')).toHaveTextContent('Offline')
    cleanup()

    const { user, ws } = await startMatch()
    deliver(ws, snapshot(5, { playback: { state: 'playing', speed: 1, seed: 42 } }))
    expect(screen.getByTestId('connection-status')).toHaveTextContent('Live')

    routes[controlPath] = json(200, playback('paused'))
    await user.click(screen.getByRole('button', { name: 'Pause' }))
    await waitFor(() => {
      expect(screen.getByTestId('connection-status')).toHaveTextContent('Paused')
    })

    act(() => {
      ws.drop()
    })
    expect(screen.getByTestId('connection-status')).toHaveTextContent('Offline')
  })

  it('shows the match title from metadata and a pitch placeholder', async () => {
    const { ws } = await startMatch()
    deliver(ws, snapshot(5))
    expect(screen.getByTestId('match-title')).toHaveTextContent('Blue vs Amber')
    expect(screen.getByText('Pitch view arrives with tactical replay')).toBeInTheDocument()
  })

  it('switches between dark and light themes from the header', async () => {
    localStorage.clear()
    const user = userEvent.setup()
    render(<App />)
    const toggle = screen.getByRole('button', { name: 'Light theme' })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByTestId('app-shell')).toHaveAttribute('data-theme', 'dark')

    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('app-shell')).toHaveAttribute('data-theme', 'light')
    expect(localStorage.getItem('tactistream.theme')).toBe('light')
  })
})
