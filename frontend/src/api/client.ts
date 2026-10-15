import type { Language, MatchEvent, MetricResult, Snapshot, TrackingFrame } from '../contracts/generated'

export type ApiErrorCode =
  | 'match_not_found'
  | 'evidence_not_found'
  | 'invalid_scenario'
  | 'invalid_action'
  | 'invalid_request'
  | 'session_start_timeout'
  | 'capacity_reached'
  | 'presenter_disabled'
  | 'presenter_key_invalid'
  | 'main_missing'
  | 'media_too_large'
  | 'unsupported_media'
  | 'invalid_url'
  | 'network_error'
  | 'unknown_error'

const KNOWN_CODES = new Set<string>([
  'match_not_found',
  'evidence_not_found',
  'invalid_scenario',
  'invalid_action',
  'invalid_request',
  'session_start_timeout',
  'capacity_reached',
  'presenter_disabled',
  'presenter_key_invalid',
  'main_missing',
  'media_too_large',
  'unsupported_media',
  'invalid_url',
])

/** A REST failure: the server's `{"error", "detail"}` envelope, or `network_error` / `unknown_error`. */
export class ApiError extends Error {
  readonly status: number
  readonly code: ApiErrorCode
  readonly detail: string

  constructor(status: number, code: ApiErrorCode, detail: string) {
    super(`${code}: ${detail}`)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
  }
}

export interface SessionInfo {
  session_id: string
  match_id: string
  ws_path: string
}

export type ControlAction = 'play' | 'pause' | 'reset'

export interface ControlResponse {
  playback: Snapshot['playback']
  session_clock_ms: number
}

export type EvidenceResponse =
  | { evidence_id: string; kind: 'event'; record: MatchEvent }
  | { evidence_id: string; kind: 'frame'; record: TrackingFrame }
  | { evidence_id: string; kind: 'metric'; record: MetricResult }

function isEnvelope(body: unknown): body is { error: string; detail?: unknown } {
  return typeof body === 'object' && body !== null && typeof (body as { error?: unknown }).error === 'string'
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return undefined
  }
}

/** The error for a non-2xx response body. */
export function apiError(status: number, text: string): ApiError {
  const body = parseJson(text)
  if (isEnvelope(body) && KNOWN_CODES.has(body.error)) {
    const detail = typeof body.detail === 'string' ? body.detail : ''
    return new ApiError(status, body.error as ApiErrorCode, detail)
  }
  return new ApiError(status, 'unknown_error', text.slice(0, 200))
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch (error) {
    throw new ApiError(0, 'network_error', error instanceof Error ? error.message : String(error))
  }
  const text = await response.text()
  if (response.ok) return parseJson(text) as T
  throw apiError(response.status, text)
}

const postJson = <T>(path: string, body: unknown) =>
  request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

export const createSession = (scenario = 'skeleton') => postJson<SessionInfo>('/api/sessions', { scenario })

export const control = (matchId: string, action: ControlAction) =>
  postJson<ControlResponse>(`/api/matches/${encodeURIComponent(matchId)}/control`, { action })

export const getEvidence = (matchId: string, evidenceId: string, language: Language) =>
  request<EvidenceResponse>(
    `/api/matches/${encodeURIComponent(matchId)}/evidence/${encodeURIComponent(evidenceId)}?language=${language}`,
  )

export const wsUrl = (wsPath: string, location: Pick<Location, 'protocol' | 'host'> = window.location) =>
  `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${wsPath}`
