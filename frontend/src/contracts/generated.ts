/* eslint-disable */
/**
 * GENERATED — do not edit.
 * Source: contracts/schemas/*.schema.json. Regenerate with `npm run contracts:gen` (or `make contracts`).
 */

/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "SchemaVersion".
 */
export type SchemaVersion = string
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "MatchId".
 */
export type MatchId = string
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "MomentId".
 */
export type MomentId = string
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "MomentPattern".
 */
export type MomentPattern = 'space_creation' | 'press_turnover' | 'switch_escape' | 'shot' | 'generic'
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "EventId".
 */
export type EventId = string
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "Milliseconds".
 */
export type Milliseconds = number
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "PlayerId".
 */
export type PlayerId = string
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "MetricId".
 */
export type MetricId = string
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "TeamId".
 */
export type TeamId = 'blue' | 'amber'
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "ClaimId".
 */
export type ClaimId = string
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "EvidenceId".
 */
export type EvidenceId = EventId | FrameId | MetricId
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "FrameId".
 */
export type FrameId = string
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "AnnotationId".
 */
export type AnnotationId = string
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "InsightId".
 */
export type InsightId = string
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "TraceId".
 */
export type TraceId = string
/**
 * Stadium-fixed position in metres; pitch 105 x 68, origin bottom-left.
 *
 * @minItems 2
 * @maxItems 2
 *
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "PointM".
 */
export type PointM = [number, number]
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "SourceKind".
 */
export type SourceKind = 'synthetic' | 'event_feed_aligned_to_video' | 'video_derived'
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "ViewerMode".
 */
export type ViewerMode = 'fan' | 'analyst'
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "Language".
 */
export type Language = 'en' | 'hi'
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "MetricKind".
 */
export type MetricKind =
  | 'pass_completion'
  | 'forward_progress'
  | 'rhythm'
  | 'pressure'
  | 'channel'
  | 'receiver_separation'
  | 'defender_follow'
  | 'off_ball_run'
  | 'contribution'
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "ClaimStatus".
 */
export type ClaimStatus =
  'verified_fact' | 'interpretation_supported' | 'insufficient_data' | 'fallback_template'
/**
 * Unit published on the FeedBus / Azure Event Hubs. Partition key = match_id. Fabric Eventstream routes by kind.
 *
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "FeedEnvelope".
 */
export type FeedEnvelope =
  | {
      schema_version: SchemaVersion
      kind: 'metadata'
      match_id: MatchId
      /**
       * event_id, frame_id, insight_id:version, trace_id or latency sample id; dedupe key together with kind.
       */
      record_id: string
      /**
       * Publisher wall clock (epoch ms).
       */
      published_ms: number
      /**
       * Set by the ingesting service on receipt (epoch ms).
       */
      server_receipt_ms?: number
      payload: MatchMetadata
    }
  | {
      schema_version: SchemaVersion
      kind: 'event'
      match_id: MatchId
      /**
       * event_id, frame_id, insight_id:version, trace_id or latency sample id; dedupe key together with kind.
       */
      record_id: string
      /**
       * Publisher wall clock (epoch ms).
       */
      published_ms: number
      /**
       * Set by the ingesting service on receipt (epoch ms).
       */
      server_receipt_ms?: number
      payload: MatchEvent
    }
  | {
      schema_version: SchemaVersion
      kind: 'frame'
      match_id: MatchId
      /**
       * event_id, frame_id, insight_id:version, trace_id or latency sample id; dedupe key together with kind.
       */
      record_id: string
      /**
       * Publisher wall clock (epoch ms).
       */
      published_ms: number
      /**
       * Set by the ingesting service on receipt (epoch ms).
       */
      server_receipt_ms?: number
      payload: TrackingFrame
    }
  | {
      schema_version: SchemaVersion
      kind: 'insight'
      match_id: MatchId
      /**
       * event_id, frame_id, insight_id:version, trace_id or latency sample id; dedupe key together with kind.
       */
      record_id: string
      /**
       * Publisher wall clock (epoch ms).
       */
      published_ms: number
      /**
       * Set by the ingesting service on receipt (epoch ms).
       */
      server_receipt_ms?: number
      payload: InsightPacket
    }
  | {
      schema_version: SchemaVersion
      kind: 'agent_trace' | 'latency'
      match_id: MatchId
      /**
       * event_id, frame_id, insight_id:version, trace_id or latency sample id; dedupe key together with kind.
       */
      record_id: string
      /**
       * Publisher wall clock (epoch ms).
       */
      published_ms: number
      /**
       * Set by the ingesting service on receipt (epoch ms).
       */
      server_receipt_ms?: number
      payload: {
        [k: string]: unknown
      }
    }
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "ServerMessage".
 */
export type ServerMessage =
  | {
      type: 'event'
      /**
       * Monotonic per match stream; clients resume from the last seq they processed.
       */
      seq: number
      match_id: MatchId
      server_receipt_ms?: number
      payload: MatchEvent
    }
  | {
      type: 'frame'
      /**
       * Monotonic per match stream; clients resume from the last seq they processed.
       */
      seq: number
      match_id: MatchId
      server_receipt_ms?: number
      payload: TrackingFrame
    }
  | {
      type: 'metric'
      /**
       * Monotonic per match stream; clients resume from the last seq they processed.
       */
      seq: number
      match_id: MatchId
      server_receipt_ms?: number
      payload: MetricResult
    }
  | {
      type: 'moment'
      /**
       * Monotonic per match stream; clients resume from the last seq they processed.
       */
      seq: number
      match_id: MatchId
      server_receipt_ms?: number
      payload: CandidateMoment
    }
  | {
      type: 'insight'
      /**
       * Monotonic per match stream; clients resume from the last seq they processed.
       */
      seq: number
      match_id: MatchId
      server_receipt_ms?: number
      payload: InsightBundle
    }
  | {
      type: 'insight_revoked'
      /**
       * Monotonic per match stream; clients resume from the last seq they processed.
       */
      seq: number
      match_id: MatchId
      server_receipt_ms?: number
      payload: InsightRevoked
    }
  | {
      type: 'narrative_status'
      /**
       * Monotonic per match stream; clients resume from the last seq they processed.
       */
      seq: number
      match_id: MatchId
      server_receipt_ms?: number
      payload: NarrativeStatus
    }
  | {
      type: 'snapshot'
      /**
       * Monotonic per match stream; clients resume from the last seq they processed.
       */
      seq: number
      match_id: MatchId
      server_receipt_ms?: number
      payload: Snapshot
    }
  | {
      type: 'heartbeat' | 'error'
      /**
       * Monotonic per match stream; clients resume from the last seq they processed.
       */
      seq: number
      match_id: MatchId
      server_receipt_ms?: number
      payload: {
        [k: string]: unknown
      }
    }
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "ClientMessage".
 */
export type ClientMessage =
  | {
      type: 'resume'
      last_seq: number
    }
  | {
      type: 'prefs'
      mode: ViewerMode
      language: Language
      pinned_player_id?: PlayerId | null
    }
  | {
      type: 'display_ack'
      target_kind: 'event' | 'insight'
      target_id: string
      server_seq: number
    }

/**
 * Every named contract type; see contracts/schemas.
 */
export interface TactiStreamContracts {
  CandidateMoment?: CandidateMoment
  SlotValue?: SlotValue
  Claim?: Claim
  AnalystOutput?: AnalystOutput
  Verdict?: Verdict
  VerifierOutput?: VerifierOutput
  ProducerOutput?: ProducerOutput
  ModePlan?: ModePlan
  SchemaVersion?: SchemaVersion
  Milliseconds?: Milliseconds
  MatchId?: MatchId
  TeamId?: TeamId
  PlayerId?: PlayerId
  EventId?: EventId
  FrameId?: FrameId
  MetricId?: MetricId
  MomentId?: MomentId
  InsightId?: InsightId
  ClaimId?: ClaimId
  EvidenceId?: EvidenceId
  TraceId?: TraceId
  PointM?: PointM
  SourceKind?: SourceKind
  Provenance?: Provenance
  ViewerMode?: ViewerMode
  Language?: Language
  MetricKind?: MetricKind
  MomentPattern?: MomentPattern
  ClaimStatus?: ClaimStatus
  AnnotationId?: AnnotationId
  MatchEvent?: MatchEvent
  FeedEnvelope?: FeedEnvelope
  InsightPacket?: InsightPacket
  MatchMetadata?: MatchMetadata
  MetricResult?: MetricResult
  Recap?: Recap
  TrackingFrame?: TrackingFrame
  ServerMessage?: ServerMessage
  InsightBundle?: InsightBundle
  InsightRevoked?: InsightRevoked
  NarrativeStatus?: NarrativeStatus
  Snapshot?: Snapshot
  ClientMessage?: ClientMessage
}
/**
 * A deterministic, ranked window worth explaining. Never contains scenario labels or future outcomes beyond the trigger.
 *
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "CandidateMoment".
 */
export interface CandidateMoment {
  schema_version: SchemaVersion
  match_id: MatchId
  moment_id: MomentId
  pattern: MomentPattern
  trigger_event_id: EventId
  window: {
    start_ms: Milliseconds
    end_ms: Milliseconds
  }
  involved_player_ids: PlayerId[]
  metric_ids: MetricId[]
  tracking_coverage?: number
  rank_score: number
  state_version: number
}
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "SlotValue".
 */
export interface SlotValue {
  kind: 'player' | 'team' | 'metric' | 'event_time'
  player_id?: PlayerId
  team_id?: TeamId
  metric_id?: MetricId
  event_id?: EventId
}
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "Claim".
 */
export interface Claim {
  claim_id: ClaimId
  kind: 'fact' | 'interpretation'
  /**
   * Key in the narrative catalog, e.g. fact.forward_pass, interp.space_opened_by_run.
   */
  template_id: string
  slots: {
    [k: string]: SlotValue
  }
  /**
   * @minItems 1
   */
  evidence_ids: EvidenceId[]
  uncertainty: 'low' | 'medium' | 'high'
  requested_annotations?: AnnotationId[]
  /**
   * Short public decision note; never private chain-of-thought.
   */
  rationale?: string
}
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "AnalystOutput".
 */
export interface AnalystOutput {
  moment_id: MomentId
  /**
   * @maxItems 2
   */
  claims: Claim[]
  abstained: boolean
  abstain_reason?: 'insufficient_tracking' | 'no_supported_interpretation' | 'timeout'
}
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "Verdict".
 */
export interface Verdict {
  claim_id: ClaimId
  decision: 'approve' | 'revise' | 'reject'
  reason_codes: (
    | 'ok'
    | 'missing_evidence_id'
    | 'future_evidence'
    | 'value_mismatch'
    | 'unit_mismatch'
    | 'unsupported_causality'
    | 'counterevidence'
    | 'insufficient_tracking'
    | 'template_kind_mismatch'
  )[]
  note?: string
}
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "VerifierOutput".
 */
export interface VerifierOutput {
  moment_id: MomentId
  verdicts: Verdict[]
}
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "ProducerOutput".
 */
export interface ProducerOutput {
  moment_id: MomentId
  fan: ModePlan
  analyst: ModePlan
}
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "ModePlan".
 */
export interface ModePlan {
  title_template_id: string
  /**
   * @minItems 1
   * @maxItems 2
   */
  claim_ids: ClaimId[]
  annotations: AnnotationId[]
  priority: number
  panel: 'lower_third' | 'side_panel'
}
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "Provenance".
 */
export interface Provenance {
  kind: SourceKind
  generator_version?: string
  seed?: number
}
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "MatchEvent".
 */
export interface MatchEvent {
  schema_version: SchemaVersion
  match_id: MatchId
  event_id: EventId
  sequence: number
  period: number
  period_clock_ms: Milliseconds
  session_clock_ms: Milliseconds
  event_type:
    | 'kickoff'
    | 'pass'
    | 'carry'
    | 'pressure'
    | 'tackle'
    | 'interception'
    | 'ball_recovery'
    | 'shot'
    | 'clearance'
    | 'out_of_play'
    | 'period_end'
  team_id: TeamId
  player_id: PlayerId
  recipient_id?: PlayerId
  start_m: PointM
  end_m?: PointM
  duration_ms?: Milliseconds
  outcome: 'complete' | 'incomplete' | 'on_target' | 'off_target' | 'blocked' | 'goal' | 'won' | 'lost' | null
  related_event_ids?: EventId[]
  source: Provenance
}
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "MatchMetadata".
 */
export interface MatchMetadata {
  schema_version: SchemaVersion
  match_id: MatchId
  pitch: {
    length_m: 105
    width_m: 68
    origin: 'bottom_left'
  }
  /**
   * @minItems 2
   * @maxItems 2
   */
  teams: {
    team_id: TeamId
    display_name: {
      en: string
      hi: string
    }
    color_hex: string
    /**
     * @minItems 11
     */
    players: {
      player_id: PlayerId
      shirt_number: number
      role: 'GK' | 'DF' | 'MF' | 'FW'
      display_name: {
        en: string
        hi: string
      }
    }[]
  }[]
  /**
   * @minItems 1
   */
  periods: {
    period: number
    /**
     * Direction along x in which each team attacks this period: +1 or -1.
     */
    attack_direction: {
      blue: 1 | -1
      amber: 1 | -1
    }
  }[]
  frame_interval_ms: 100
  source: Provenance
}
/**
 * One 10 Hz snapshot of player and ball positions. Unavailable entities carry visible=false and no position; positions are never fabricated.
 *
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "TrackingFrame".
 */
export interface TrackingFrame {
  schema_version: SchemaVersion
  match_id: MatchId
  frame_id: FrameId
  frame_index: number
  period: number
  period_clock_ms: Milliseconds
  session_clock_ms: Milliseconds
  players: {
    player_id: PlayerId
    visible: boolean
    pos_m?: PointM
  }[]
  ball: {
    visible: boolean
    pos_m?: PointM
    height_m?: number
  }
  source: Provenance
}
/**
 * Machine-readable render instruction for one (mode, language) variant of one insight version. Never contains executable UI code.
 *
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "InsightPacket".
 */
export interface InsightPacket {
  schema_version: SchemaVersion
  insight_id: InsightId
  insight_version: number
  match_id: MatchId
  moment_id: MomentId
  state_version: number
  as_of_session_ms: Milliseconds
  mode: ViewerMode
  language: Language
  source_kind: SourceKind
  claim_status: ClaimStatus
  title: string
  body: string
  labels?: ('synthetic' | 'interpretation' | 'partial_tracking' | 'fallback')[]
  /**
   * @minItems 1
   */
  evidence_ids: EvidenceId[]
  claim_ids: ClaimId[]
  render: {
    clock: 'session_clock_ms'
    show_from_ms: Milliseconds
    show_until_ms: Milliseconds
    priority: number
    panel: 'lower_third' | 'side_panel'
    annotations: AnnotationId[]
    replay_window?: {
      start_ms: Milliseconds
      end_ms: Milliseconds
    }
  }
  expires_at_session_ms: Milliseconds
  trace_id: TraceId
}
/**
 * A deterministic, inspectable measurement with its definition version, window and contributing evidence.
 *
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "MetricResult".
 */
export interface MetricResult {
  schema_version: SchemaVersion
  match_id: MatchId
  metric_id: MetricId
  kind: MetricKind
  definition_version: string
  status: 'ok' | 'unavailable'
  unavailable_reason?: 'insufficient_tracking' | 'missing_events' | 'not_applicable'
  value?: number
  unit?: 'm' | 'ratio' | 'per_min' | 'score_0_100' | 'count' | 'cosine'
  /**
   * Named sub-values (e.g. before/after widths) exposed in Analyst mode.
   */
  components?: {
    [k: string]: number
  }
  subject_ids?: PlayerId[]
  window: {
    start_ms: Milliseconds
    end_ms: Milliseconds
  }
  inputs: {
    event_ids: EventId[]
    frame_ids: FrameId[]
    excluded_count?: number
  }
  params?: {
    [k: string]: number
  }
  /**
   * Key into the narrative catalog for the limitation text shown in the product.
   */
  limitation_key?: string
  state_version: number
}
/**
 * Ranked replay playlist + concise text + timed overlay track for a studio graphics system.
 *
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "Recap".
 */
export interface Recap {
  schema_version: SchemaVersion
  recap_id: string
  match_id: MatchId
  mode: ViewerMode
  language: Language
  pinned_player_id?: PlayerId
  generated_at_state_version: number
  summary: string
  /**
   * @minItems 1
   * @maxItems 8
   */
  items: {
    rank: number
    moment_id: MomentId
    insight_id: InsightId
    replay_window: {
      start_ms: Milliseconds
      end_ms: Milliseconds
    }
    title: string
    pinned_player_involvement?: 'direct' | 'off_ball' | 'none'
    /**
     * @minItems 1
     */
    evidence_ids: EvidenceId[]
  }[]
  /**
   * Timed overlays on a recap-relative clock (ms from recap start).
   */
  overlay_track: {
    start_ms: Milliseconds
    end_ms: Milliseconds
    insight_id: InsightId
    text: string
    annotations: AnnotationId[]
  }[]
}
/**
 * All four (mode x language) variants of one insight version so switching is instant and consistent.
 *
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "InsightBundle".
 */
export interface InsightBundle {
  insight_id: InsightId
  insight_version: number
  /**
   * @minItems 1
   * @maxItems 4
   */
  variants: InsightPacket[]
}
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "InsightRevoked".
 */
export interface InsightRevoked {
  insight_id: InsightId
  insight_version: number
  reason: 'late_event_revision' | 'expired' | 'superseded'
}
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "NarrativeStatus".
 */
export interface NarrativeStatus {
  moment_id: MomentId
  stage: 'analysing' | 'verifying' | 'producing' | 'checking' | 'released' | 'fallback' | 'abstained'
  fallback_reason?:
    | 'timeout'
    | 'verifier_rejected'
    | 'output_check_failed'
    | 'model_error'
    | 'expired'
    | 'insufficient_tracking'
  trace_id?: TraceId
}
/**
 * This interface was referenced by `TactiStreamContracts`'s JSON-Schema
 * via the `definition` "Snapshot".
 */
export interface Snapshot {
  metadata: MatchMetadata
  state_version: number
  session_clock_ms: Milliseconds
  events: MatchEvent[]
  latest_frame: TrackingFrame | null
  moments: CandidateMoment[]
  insights: InsightBundle[]
  playback: {
    state: 'playing' | 'paused' | 'ended'
    speed: number
    seed: number
  }
}
