import type {
  InsightBundle,
  InsightPacket,
  Language,
  MatchEvent,
  MatchMetadata,
  ServerMessage,
  Snapshot,
  ViewerMode,
} from '../../src/contracts/generated'

export const MATCH_ID = 'demo-blue-amber-001'

const source = { kind: 'synthetic', generator_version: '0.1.0', seed: 42 } as const

function players(team: 'blue' | 'amber') {
  return Array.from({ length: 11 }, (_, i) => ({
    player_id: `${team}-${String(i + 1).padStart(2, '0')}`,
    shirt_number: i + 1,
    role: i === 0 ? ('GK' as const) : ('MF' as const),
    display_name: { en: `${team} ${String(i + 1)}`, hi: `${team} ${String(i + 1)}` },
  }))
}

export function metadata(): MatchMetadata {
  return {
    schema_version: '1.0',
    match_id: MATCH_ID,
    pitch: { length_m: 105, width_m: 68, origin: 'bottom_left' },
    teams: [
      {
        team_id: 'blue',
        display_name: { en: 'Blue', hi: 'ब्लू' },
        color_hex: '#3B82F6',
        players: players('blue'),
      },
      {
        team_id: 'amber',
        display_name: { en: 'Amber', hi: 'एम्बर' },
        color_hex: '#F59E0B',
        players: players('amber'),
      },
    ],
    periods: [{ period: 1, attack_direction: { blue: 1, amber: -1 } }],
    frame_interval_ms: 100,
    source,
  }
}

export function event(eventId: string, overrides: Partial<MatchEvent> = {}): MatchEvent {
  return {
    schema_version: '1.0',
    match_id: MATCH_ID,
    event_id: eventId,
    sequence: 42,
    period: 1,
    period_clock_ms: 3000,
    session_clock_ms: 3000,
    event_type: 'pass',
    team_id: 'blue',
    player_id: 'blue-08',
    recipient_id: 'blue-11',
    start_m: [58.1, 32.4],
    end_m: [71.2, 28.0],
    duration_ms: 900,
    outcome: 'complete',
    source,
    ...overrides,
  }
}

interface InsightOptions {
  priority?: number
  expiresAt?: number
}

function packet(
  insightId: string,
  mode: ViewerMode,
  language: Language,
  { priority = 3, expiresAt = 33_900 }: InsightOptions,
): InsightPacket {
  return {
    schema_version: '1.0',
    insight_id: insightId,
    insight_version: 1,
    match_id: MATCH_ID,
    moment_id: 'mom-0042',
    state_version: 5,
    as_of_session_ms: 3000,
    mode,
    language,
    source_kind: 'synthetic',
    claim_status: 'verified_fact',
    title: `${insightId} title ${mode} ${language}`,
    body: `${insightId} body ${mode} ${language}`,
    labels: ['synthetic'],
    evidence_ids: ['evt-0042', 'met-fp-evt-0042'],
    claim_ids: [],
    render: {
      clock: 'session_clock_ms',
      show_from_ms: 3900,
      show_until_ms: 9900,
      priority,
      panel: 'lower_third',
      annotations: [],
    },
    expires_at_session_ms: expiresAt,
    trace_id: '0'.repeat(32),
  }
}

export function insight(insightId: string, options: InsightOptions = {}): InsightBundle {
  const modes: ViewerMode[] = ['fan', 'analyst']
  const languages: Language[] = ['en', 'hi']
  return {
    insight_id: insightId,
    insight_version: 1,
    variants: modes.flatMap((mode) =>
      languages.map((language) => packet(insightId, mode, language, options)),
    ),
  }
}

export function snapshot(seq: number, overrides: Partial<Snapshot> = {}): ServerMessage {
  return {
    type: 'snapshot',
    seq,
    match_id: MATCH_ID,
    payload: {
      metadata: metadata(),
      state_version: 1,
      session_clock_ms: 0,
      events: [],
      latest_frame: null,
      moments: [],
      insights: [],
      playback: { state: 'paused', speed: 1, seed: 42 },
      ...overrides,
    },
  }
}

export function eventMessage(seq: number, payload: MatchEvent): ServerMessage {
  return { type: 'event', seq, match_id: MATCH_ID, payload }
}

export function insightMessage(seq: number, payload: InsightBundle): ServerMessage {
  return { type: 'insight', seq, match_id: MATCH_ID, payload }
}

export function heartbeat(seq: number, sessionClockMs: number): ServerMessage {
  return { type: 'heartbeat', seq, match_id: MATCH_ID, payload: { session_clock_ms: sessionClockMs } }
}
