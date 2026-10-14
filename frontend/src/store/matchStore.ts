import { create } from 'zustand'

import type {
  InsightBundle,
  InsightPacket,
  Language,
  MatchEvent,
  MatchMetadata,
  ServerMessage,
  Snapshot,
  TrackingFrame,
  ViewerMode,
} from '../contracts/generated'

export interface Prefs {
  mode: ViewerMode
  language: Language
}

export type Playback = Snapshot['playback']

export interface MatchState {
  matchId: string | null
  metadata: MatchMetadata | null
  events: MatchEvent[]
  latestFrame: TrackingFrame | null
  insights: Record<string, InsightBundle>
  insightSeq: Record<string, number>
  activeInsightId: string | null
  playback: Playback | null
  /** The match socket is open. */
  connected: boolean
  sessionClockMs: number
  lastSeq: number
  prefs: Prefs
}

export interface MatchActions {
  startSession: (matchId: string | null) => void
  applySnapshot: (message: ServerMessage) => void
  applyMessage: (message: ServerMessage) => void
  setPrefs: (prefs: Prefs) => void
  setConnected: (connected: boolean) => void
  setPlayback: (playback: Playback) => void
  variantFor: (prefs: Prefs) => InsightPacket | null
}

export type MatchStore = MatchState & MatchActions

type MatchData = Omit<MatchState, 'prefs'>

const emptyMatch = (matchId: string | null): MatchData => ({
  matchId,
  metadata: null,
  events: [],
  latestFrame: null,
  insights: {},
  insightSeq: {},
  activeInsightId: null,
  playback: null,
  connected: false,
  sessionClockMs: 0,
  lastSeq: 0,
})

/** Render priority: 1 is the most important. */
const priorityOf = (bundle: InsightBundle) => bundle.variants[0]?.render.priority ?? Number.POSITIVE_INFINITY

const isExpired = (bundle: InsightBundle, sessionClockMs: number) =>
  sessionClockMs > (bundle.variants[0]?.expires_at_session_ms ?? Number.NEGATIVE_INFINITY)

/** At most one card: higher priority preempts lower, ties go to the newest, expired cards never show. */
function preempts(candidate: InsightBundle, current: InsightBundle | undefined, sessionClockMs: number) {
  if (isExpired(candidate, sessionClockMs)) return false
  if (current === undefined || isExpired(current, sessionClockMs)) return true
  return priorityOf(candidate) <= priorityOf(current)
}

function pickActive(bundles: InsightBundle[], sessionClockMs: number): string | null {
  let active: InsightBundle | undefined
  for (const bundle of bundles) {
    if (preempts(bundle, active, sessionClockMs)) active = bundle
  }
  return active?.insight_id ?? null
}

export const createMatchStore = () =>
  create<MatchStore>()((set, get) => ({
    ...emptyMatch(null),
    prefs: { mode: 'fan', language: 'en' },

    startSession: (matchId) => {
      set(emptyMatch(matchId))
    },

    applySnapshot: (message) => {
      if (message.type !== 'snapshot') return
      const snap = message.payload
      set({
        metadata: snap.metadata,
        events: snap.events,
        latestFrame: snap.latest_frame,
        insights: Object.fromEntries(snap.insights.map((b) => [b.insight_id, b])),
        insightSeq: Object.fromEntries(snap.insights.map((b) => [b.insight_id, message.seq])),
        activeInsightId: pickActive(snap.insights, snap.session_clock_ms),
        playback: snap.playback,
        sessionClockMs: snap.session_clock_ms,
        lastSeq: message.seq,
      })
    },

    applyMessage: (message) => {
      if (message.type === 'snapshot') {
        get().applySnapshot(message)
        return
      }
      const state = get()
      const lastSeq = Math.max(state.lastSeq, message.seq)
      const clock = (ms: number) => Math.max(state.sessionClockMs, ms)
      switch (message.type) {
        case 'event': {
          const ev = message.payload
          if (state.events.some((e) => e.event_id === ev.event_id)) {
            set({ lastSeq })
            break
          }
          set({ events: [...state.events, ev], sessionClockMs: clock(ev.session_clock_ms), lastSeq })
          break
        }
        case 'frame':
          set({
            latestFrame: message.payload,
            sessionClockMs: clock(message.payload.session_clock_ms),
            lastSeq,
          })
          break
        case 'insight': {
          const bundle = message.payload
          const current = state.activeInsightId ? state.insights[state.activeInsightId] : undefined
          set({
            insights: { ...state.insights, [bundle.insight_id]: bundle },
            insightSeq: { ...state.insightSeq, [bundle.insight_id]: message.seq },
            activeInsightId: preempts(bundle, current, state.sessionClockMs)
              ? bundle.insight_id
              : state.activeInsightId,
            lastSeq,
          })
          break
        }
        case 'heartbeat': {
          const ms = message.payload.session_clock_ms
          set(typeof ms === 'number' ? { sessionClockMs: clock(ms), lastSeq } : { lastSeq })
          break
        }
        default:
          set({ lastSeq })
      }
      const next = get()
      const active = next.activeInsightId ? next.insights[next.activeInsightId] : undefined
      if (active && isExpired(active, next.sessionClockMs)) {
        set({ activeInsightId: pickActive(Object.values(next.insights), next.sessionClockMs) })
      }
    },

    setPrefs: (prefs) => {
      set({ prefs })
    },

    setConnected: (connected) => {
      set({ connected })
    },

    setPlayback: (playback) => {
      set({ playback })
    },

    variantFor: (prefs) => {
      const { activeInsightId, insights, sessionClockMs } = get()
      const bundle = activeInsightId ? insights[activeInsightId] : undefined
      if (bundle === undefined || isExpired(bundle, sessionClockMs)) return null
      return bundle.variants.find((p) => p.mode === prefs.mode && p.language === prefs.language) ?? null
    },
  }))

export const useMatchStore = createMatchStore()
