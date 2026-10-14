import { beforeEach, describe, expect, it } from 'vitest'

import { createMatchStore } from '../../src/store/matchStore'
import { event, eventMessage, heartbeat, insight, insightMessage, MATCH_ID, snapshot } from './fixtures'

let store: ReturnType<typeof createMatchStore>

beforeEach(() => {
  store = createMatchStore()
  store.getState().startSession(MATCH_ID)
})

describe('applySnapshot', () => {
  it('replaces events, insights, playback and lastSeq', () => {
    const s = store.getState()
    s.applySnapshot(snapshot(3, { events: [event('evt-0001')], insights: [insight('ins-0001')] }))
    s.applySnapshot(
      snapshot(10, {
        events: [event('evt-0002')],
        session_clock_ms: 500,
        playback: { state: 'playing', speed: 1, seed: 42 },
      }),
    )

    const state = store.getState()
    expect(state.events.map((e) => e.event_id)).toEqual(['evt-0002'])
    expect(state.insights).toEqual({})
    expect(state.activeInsightId).toBeNull()
    expect(state.lastSeq).toBe(10)
    expect(state.sessionClockMs).toBe(500)
    expect(state.playback?.state).toBe('playing')
    expect(state.metadata?.match_id).toBe(MATCH_ID)
  })

  it('shows a released, unexpired insight from the snapshot', () => {
    store.getState().applySnapshot(snapshot(7, { insights: [insight('ins-0042')], session_clock_ms: 6000 }))

    expect(store.getState().activeInsightId).toBe('ins-0042')
    expect(store.getState().insightSeq['ins-0042']).toBe(7)
  })
})

describe('applyMessage', () => {
  beforeEach(() => {
    store.getState().applySnapshot(snapshot(10, { events: [event('evt-0001')] }))
  })

  it('ignores an event whose event_id is already known', () => {
    const s = store.getState()
    s.applyMessage(eventMessage(11, event('evt-0001')))
    s.applyMessage(eventMessage(12, event('evt-0002')))
    s.applyMessage(eventMessage(13, event('evt-0002')))

    expect(store.getState().events.map((e) => e.event_id)).toEqual(['evt-0001', 'evt-0002'])
    expect(store.getState().lastSeq).toBe(13)
  })

  it('activates the first insight and remembers its seq', () => {
    store.getState().applyMessage(insightMessage(11, insight('ins-0042')))

    expect(store.getState().activeInsightId).toBe('ins-0042')
    expect(store.getState().insightSeq['ins-0042']).toBe(11)
  })

  it('keeps the active insight when a lower-priority one arrives', () => {
    const s = store.getState()
    s.applyMessage(insightMessage(11, insight('ins-a', { priority: 2 })))
    s.applyMessage(insightMessage(12, insight('ins-b', { priority: 3 })))

    expect(store.getState().activeInsightId).toBe('ins-a')
    expect(Object.keys(store.getState().insights)).toEqual(['ins-a', 'ins-b'])
  })

  it('replaces the active insight with an equal or higher priority one', () => {
    const s = store.getState()
    s.applyMessage(insightMessage(11, insight('ins-a', { priority: 3 })))
    s.applyMessage(insightMessage(12, insight('ins-b', { priority: 3 })))
    expect(store.getState().activeInsightId).toBe('ins-b')

    s.applyMessage(insightMessage(13, insight('ins-c', { priority: 1 })))
    expect(store.getState().activeInsightId).toBe('ins-c')
  })

  it('replaces an expired active insight even with a lower-priority one', () => {
    const s = store.getState()
    s.applyMessage(insightMessage(11, insight('ins-a', { priority: 1, expiresAt: 4000 })))
    s.applyMessage(heartbeat(11, 5000))
    s.applyMessage(insightMessage(12, insight('ins-b', { priority: 5 })))

    expect(store.getState().activeInsightId).toBe('ins-b')
  })
})

describe('variantFor', () => {
  it('returns the active packet matching mode and language', () => {
    store.getState().applyMessage(insightMessage(11, insight('ins-0042')))

    const packet = store.getState().variantFor({ mode: 'analyst', language: 'hi' })
    expect(packet?.mode).toBe('analyst')
    expect(packet?.language).toBe('hi')
    expect(packet?.title).toBe('ins-0042 title analyst hi')
  })

  it('returns null without an active insight', () => {
    expect(store.getState().variantFor({ mode: 'fan', language: 'en' })).toBeNull()
  })

  it('returns null once the session clock passes expires_at_session_ms', () => {
    const s = store.getState()
    s.applyMessage(insightMessage(11, insight('ins-0042', { expiresAt: 4000 })))
    s.applyMessage(heartbeat(11, 4001))

    expect(store.getState().variantFor({ mode: 'fan', language: 'en' })).toBeNull()
  })
})

describe('startSession', () => {
  it('clears the previous match and keeps prefs', () => {
    const s = store.getState()
    s.setPrefs({ mode: 'analyst', language: 'hi' })
    s.applySnapshot(snapshot(10, { events: [event('evt-0001')], insights: [insight('ins-0042')] }))
    s.startSession('other-match')

    const state = store.getState()
    expect(state.matchId).toBe('other-match')
    expect(state.events).toEqual([])
    expect(state.activeInsightId).toBeNull()
    expect(state.lastSeq).toBe(0)
    expect(state.prefs).toEqual({ mode: 'analyst', language: 'hi' })
  })
})
