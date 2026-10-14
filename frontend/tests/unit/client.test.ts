import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, control, createSession, getEvidence, wsUrl } from '../../src/api/client'

function respond(status: number, body: unknown) {
  const fetchMock = vi
    .fn<typeof fetch>()
    .mockResolvedValue(new Response(typeof body === 'string' ? body : JSON.stringify(body), { status }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function rejection(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (error) {
    if (error instanceof ApiError) return error
    throw error
  }
  throw new Error('expected the call to fail')
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('createSession', () => {
  it('posts the scenario and returns the session', async () => {
    const session = { session_id: 's-1', match_id: 'm1', ws_path: '/ws/matches/m1' }
    const fetchMock = respond(200, session)

    await expect(createSession()).resolves.toEqual(session)
    const [url, init] = fetchMock.mock.calls[0] ?? []
    expect(url).toBe('/api/sessions')
    expect(init?.method).toBe('POST')
    expect(init?.body).toBe(JSON.stringify({ scenario: 'skeleton' }))
  })

  it.each([
    [422, 'invalid_scenario'],
    [503, 'session_start_timeout'],
  ])('turns a %i error envelope into a typed ApiError (%s)', async (status, code) => {
    respond(status, { error: code, detail: 'nope' })

    const error = await rejection(createSession())
    expect(error.status).toBe(status)
    expect(error.code).toBe(code)
    expect(error.detail).toBe('nope')
  })

  it('reports a body that is not an error envelope as unknown_error', async () => {
    respond(502, 'Bad Gateway')

    const error = await rejection(createSession())
    expect(error.status).toBe(502)
    expect(error.code).toBe('unknown_error')
  })

  it('reports a failed request as network_error', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockRejectedValue(new TypeError('Failed to fetch')))

    const error = await rejection(createSession())
    expect(error.status).toBe(0)
    expect(error.code).toBe('network_error')
  })
})

describe('control', () => {
  it('posts the action to the match control endpoint', async () => {
    const body = { playback: { state: 'paused', speed: 1, seed: 42 }, session_clock_ms: 1200 }
    const fetchMock = respond(200, body)

    await expect(control('m 1', 'pause')).resolves.toEqual(body)
    const [url, init] = fetchMock.mock.calls[0] ?? []
    expect(url).toBe('/api/matches/m%201/control')
    expect(init?.body).toBe(JSON.stringify({ action: 'pause' }))
  })
})

describe('getEvidence', () => {
  it('requests the evidence in the given language', async () => {
    const body = { evidence_id: 'evt-0042', kind: 'event', record: {} }
    const fetchMock = respond(200, body)

    await expect(getEvidence('m1', 'evt-0042', 'hi')).resolves.toEqual(body)
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/matches/m1/evidence/evt-0042?language=hi')
  })

  it('throws evidence_not_found on 404', async () => {
    respond(404, { error: 'evidence_not_found', detail: 'evt-9999 is not available' })

    const error = await rejection(getEvidence('m1', 'evt-9999', 'en'))
    expect(error.status).toBe(404)
    expect(error.code).toBe('evidence_not_found')
  })
})

describe('wsUrl', () => {
  it('uses ws for http and wss for https on the same host', () => {
    expect(wsUrl('/ws/matches/m1', { protocol: 'http:', host: 'localhost:5173' })).toBe(
      'ws://localhost:5173/ws/matches/m1',
    )
    expect(wsUrl('/ws/matches/m1', { protocol: 'https:', host: 'demo.example' })).toBe(
      'wss://demo.example/ws/matches/m1',
    )
  })
})
