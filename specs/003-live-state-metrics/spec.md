# Feature Specification: Live State & Metrics — reliable ingest, explainable metrics, candidate moments

**Feature Branch**: `003-live-state-metrics`

**Created**: 2026-10-14

**Status**: Ready for implementation

**Input**: Build plan, "Define metrics before writing narrative prompts" and "Treat reliability as part of the demonstration":
deduplicate by event ID, check sequence ordering, buffer modest out-of-order delivery, reconcile late events through state
revisions, persist a resumable checkpoint and archive the original feed, return `unavailable` rather than a reassuring low
score. Roadmap exit: ingest dedupes/reorders; metrics are explainable with event/frame references; candidate moments
detected; reconnect resumes from the last seq.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reliable ingest yields one consistent match state (Priority: P1)

The live-state consumer receives the synthetic feed from the bus with duplicates, small reorderings and occasional gaps.
The Ingestor stamps receipt time, validates, drops duplicates, releases events in sequence order (waiting up to 500 ms for a
missing sequence), orders frames, and keeps the whole match (all events and frames) for replay windows. Repeated delivery
never inflates a pass count, and the final state is identical however the feed was delivered.

**Why this priority**: Every metric, moment and narrative depends on state being right. Replay consistency is a published
release gate ("Identical metric state for identical inputs").

**Independent Test**: Feed `demo_match` seed 42 through `Ingestor` 20 times with block-shuffled order and 20% duplicates;
assert identical `metric_state_hash` and pass counts equal to the in-order baseline.

**Acceptance Scenarios**:

1. **Given** events 10, 12, 11 arrive within 200 ms, **When** they are ingested, **Then** they are applied in the order
   10, 11, 12 with no gap flag, and 12 is held until 11 arrives.
2. **Given** event 12 arrives and 11 never does, **When** 500 ms pass on the ingest clock, **Then** 12 is applied, the delta
   carries `gap = (11, 11)`, `IngestStats.gaps` increments, and clients receive `error{error:"sequence_gap"}`.
3. **Given** every envelope is delivered twice, **When** the feed ends, **Then** `IngestStats.duplicates` equals the number
   of extra copies, each `event` WS message is broadcast exactly once, and `pass_completion` for Blue equals the in-order
   value.
4. **Given** frame 431 arrives after frame 440 was applied, **When** it is ingested, **Then** it is stored (available to
   `snapshot().frames_between`) but not broadcast as a live `frame` message.
5. **Given** 20 delivery runs with different shuffles and duplicates of `demo_match` seed 42, **When** each run is flushed
   and reconciled, **Then** all 20 produce the same `metric_state_hash` as the in-order baseline.

---

### User Story 2 - Explainable metrics with evidence references (Priority: P1)

For any anchor event, the metric engine computes pass completion, forward progress, rhythm, local pressure, passing-lane
(channel) change, receiver separation, defender follow, off-ball run and player contribution as `MetricResult`s. Each one
carries its definition version, window, parameters, contributing event and frame IDs, named components, and a limitation
key. When tracking is insufficient it returns `unavailable` with a reason — never a low number. `docs/metrics.md` documents
every formula, parameter and limitation.

**Why this priority**: Constitution I — every number shown later (cards, Analyst drawer, agent claims) must come from here
and be traceable to records.

**Independent Test**: Unit tests per metric with hand-built snapshots (exact expected values), hypothesis property tests for
geometry, and golden values on 002 outputs.

**Acceptance Scenarios**:

1. **Given** three visible defenders 1.0, 2.0 and 3.0 m from the carrier and 10+ opponents visible, **When** `pressure` is
   computed, **Then** `value = 47.4`, `unit = score_0_100`, components `d1_m = 1.0`, `d2_m = 2.0`, `d3_m = 3.0`,
   `subject_ids[0]` = carrier, `params = {scale_m: 2.5, k: 3, min_visible_opponents: 10}`.
2. **Given** only 9 opponents are visible at the anchor, **When** `pressure` is computed, **Then** `status = unavailable`,
   `unavailable_reason = insufficient_tracking`, and no `value` is present.
3. **Given** `space_creation` seed 42 variant A, **When** `channel` is computed for the Blue 8 → Blue 11 forward pass
   (`evt-0005`), **Then** `status = ok`, `value ≥ 2.0` m, `value = clearance_at_pass_m − clearance_before_m`,
   `inputs.frame_ids = [frame at t−4000, frame at t]`, and `subject_ids = ["blue-08", "blue-11"]`.
4. **Given** the same pass, **When** `off_ball_run` and `defender_follow` are computed, **Then** the runner is `blue-09`
   (displacement ≥ 8.0 m, angle 20–70°) and the follower is `amber-04` with cosine ≥ 0.7.
5. **Given** `run_no_channel` seed 42 variant A, **When** `channel` is computed for its forward pass, **Then** the value
   is < 2.0 m.
6. **Given** any `ok` metric, **When** its `inputs` IDs are requested from the evidence endpoint, **Then** every ID resolves.

---

### User Story 3 - Candidate moments detected, ranked and broadcast (Priority: P1)

As the match plays, the system detects moments worth explaining: a shot whose preceding 8–12 s contain an off-ball run plus
a channel gain of at least 2.0 m before a forward pass (space creation); a turnover preceded by high pressure (press
turnover); a completed switch with |Δy| ≥ 30 m that reaches a separated receiver (switch escape); or a plain shot. Moments
carry their window, involved players, metric IDs, tracking coverage and a deterministic rank score, and are broadcast over
WebSocket as `moment`. Negatives do not produce their positive pattern.

**Why this priority**: The agent workflow (004), Why Mode (005) and recaps (006) all start from candidate moments.

**Independent Test**: Run detection on 002 outputs: the hero yields one `space_creation` moment; negatives yield none of
their positive pattern; `tracking_gap` yields a `shot` moment with coverage < 0.9 and unavailable spatial metrics.

**Acceptance Scenarios**:

1. **Given** `space_creation` seed 42 variant A has played past the shot plus 200 ms of frames, **When** detection runs,
   **Then** exactly one moment exists: `moment_id = mom-0007`, `pattern = space_creation`,
   `trigger_event_id = evt-0007`, `involved_player_ids ⊇ {blue-08, blue-11, blue-09, amber-04}`,
   `metric_ids ⊇ {metric-off_ball_run-0005, metric-defender_follow-0005, metric-channel-0005}`, `tracking_coverage = 1.0`,
   `rank_score ≥ 0.85`.
2. **Given** `run_no_channel`, `press_no_turnover` or `switch_closed` (seeds 1–20, variants A–C), **When** detection runs,
   **Then** no moment has pattern `space_creation`, `press_turnover` or `switch_escape` respectively.
3. **Given** `tracking_gap` seed 42 variant A, **When** detection runs, **Then** there is no `space_creation` moment; the shot
   moment has `pattern = shot`, `tracking_coverage < 0.9`, and its `channel`, `off_ball_run`, `defender_follow` metrics
   (anchored on the forward pass) plus `pressure` at the pass are `unavailable/insufficient_tracking`.
4. **Given** `demo_match` seed 42 variant A has ended, **When** moments are listed, **Then** there are exactly 4 —
   one each of `space_creation`, `press_turnover`, `switch_escape`, and one `shot` (from the run_no_channel segment) — and
   the space_creation moment ranks first.
5. **Given** a connected client, **When** a moment is detected, **Then** the client receives `metric` messages for each of
   its `metric_ids` and then one `moment` message, within 1.5 s of the trigger event's server receipt.

---

### User Story 4 - Late events revise state and revoke affected insights (Priority: P2)

A forward pass arrives late, after the shot that followed it was already classified as a plain shot. The state applies the
late event as a revision, moments are recomputed, the insight attached to the changed moment is revoked
(`insight_revoked{reason: "late_event_revision"}`), and the corrected moment is re-broadcast. The app never silently keeps a
statement that the data no longer supports.

**Why this priority**: The build plan's reliability demonstration; the "late events" failure fixture required by the
constitution. Depends on US3.

**Independent Test**: Session test that withholds `evt-0005` of the hero beyond the reorder window, registers an insight
for `mom-0007`, then delivers `evt-0005`.

**Acceptance Scenarios**:

1. **Given** `evt-0005` is withheld, **When** the shot settles, **Then** `mom-0007` is broadcast with `pattern = shot`.
2. **Given** an insight `ins-0007` v1 is registered for `mom-0007`, **When** `evt-0005` arrives, **Then** clients receive
   `insight_revoked{insight_id:"ins-0007", insight_version:1, reason:"late_event_revision"}` followed by `moment` `mom-0007`
   with `pattern = space_creation` and a higher `state_version`, within one ingest tick (100 ms).
3. **Given** a late frame inside an existing moment's window, **When** it is stored, **Then** the moment is recomputed and
   revised only if its content (excluding `state_version`) changed.

---

### User Story 5 - Checkpoint, restore, as-of snapshots and reconnect (Priority: P2)

The service checkpoints match state every 100 accepted records or 10 s and archives every received envelope. After a
restart it restores the latest checkpoint, replays the archive tail and resumes paused at the checkpointed session time.
Clients reconnecting with their last seq get a fresh snapshot including moments. Any component can fetch an as-of snapshot
over REST.

**Why this priority**: Roadmap exit ("reconnect resumes from last seq") and the build plan's resumable checkpoint. 007 swaps
in Blob storage behind the same protocol.

**Independent Test**: Interrupt ingestion of `demo_match` after N records, restore from `LocalArtifactStore`, continue,
compare hashes with an uninterrupted run; REST snapshot tests with `as_of_ms`.

**Acceptance Scenarios**:

1. **Given** 250 records have been accepted, **When** the checkpointer runs, **Then** checkpoints exist at
   `checkpoints/{match_id}/00000100.json` and `…/00000200.json` (state versions on the 100-record boundary), and
   `feed-archive/{match_id}/{session_id}.jsonl` has one line per received envelope including duplicates.
2. **Given** a crash after record N ∈ {150, 1234, 2500} of `demo_match`, **When** the match is restored and the rest of the
   feed is delivered, **Then** `full_state_hash` and `metric_state_hash` equal those of an uninterrupted run.
3. **Given** a running match, **When** a client calls `GET /api/matches/{id}/snapshot?as_of_ms=12000`, **Then** the response
   validates as `Snapshot`, contains only events and frames with `session_clock_ms ≤ 12000`, and its moments are those
   detectable as of 12000.
4. **Given** `as_of_ms` beyond the current session clock, **When** requested, **Then** the snapshot is clamped to the
   current session clock (no future data).
5. **Given** a client that saw seq K and reconnects with `resume{last_seq: K}`, **When** moments exist, **Then** the snapshot
   lists each moment once and later live messages have seq > snapshot seq.

### Edge Cases

- Duplicate with identical (`kind`, `record_id`) but different payload → first one wins; second counted as duplicate and logged with `payload_conflict=true`.
- Schema-invalid envelope → not applied, `IngestStats.invalid` +1, archived (archive is the raw record), no WS message.
- Events or frames before metadata → held (bounded 10,000 records) until metadata arrives; no gap timer runs without metadata.
- First event of a match: released immediately if `sequence ∈ {0, 1}`; otherwise held up to 500 ms, then the lowest buffered sequence is released (the 001 skeleton starts at 40).
- Envelope kinds `insight`, `agent_trace`, `latency` on the bus → ignored by live-state (`status = ignored`).
- Anchor event not in the snapshot (future or unknown) → `AnchorNotFound`; REST/tools map it to 404 / `future_evidence`.
- Anchor of the wrong type (e.g. `channel` on a carry, `pressure` on a tackle) → `unavailable/not_applicable`.
- No qualifying off-ball run with full tracking → `off_ball_run` `unavailable/not_applicable`; `defender_follow` inherits the run's reason.
- Stationary defender (displacement < 1.0 m) in `defender_follow` → `ok`, `value = 0.0` (a stationary defender is not "following").
- `pass_completion` with zero attempted passes in the window → `unavailable/missing_events`; passes with `outcome = null` excluded and counted in `inputs.excluded_count`.
- `rhythm` before 60 s of play → `unavailable/not_applicable`.
- Frame missing at a required time (no frame within ±50 ms) → `unavailable/insufficient_tracking`.
- Moment removed by a revision → its insights revoked with `late_event_revision`, and a fresh `snapshot` broadcast (there is no "moment removed" message type).
- Reset or backward seek → state, ingestor, pipeline and ledger cleared; the match's checkpoints and archive are deleted.
- Checkpoint write fails → logged and counted; the live path never blocks or raises.
- `resume.last_seq` greater than the head after a restart → treated like any resume: fresh snapshot (hub seq restarts at stored head + 10,000, so later seq values stay above anything sent before the crash).

## Requirements *(mandatory)*

### Functional Requirements

**Ingest & state**

- **FR-001**: `state/ingest.py` `Ingestor` MUST stamp `server_receipt_ms` (wall clock) when absent, validate each envelope against `feed_envelope.schema.json`, and drop duplicates by (`kind`, `record_id`), counting each outcome in `IngestStats`.
- **FR-002**: The Ingestor MUST release events in `sequence` order, holding out-of-order events until the missing sequence arrives or 500 ms (`TACTISTREAM_REORDER_WINDOW_MS`, monotonic `Clock`) elapse; on timeout it releases in order and flags `gap = (first_missing, last_missing)`.
- **FR-003**: Frames MUST be applied immediately when `frame_index` exceeds the highest applied index; lower-index (late) frames are stored but not broadcast live.
- **FR-004**: An event whose `sequence` is lower than the highest applied sequence MUST be applied as a revision: inserted in sequence order, `state_version` incremented, and `StateDelta.revision` set.
- **FR-005**: `MatchState` MUST retain all events (sorted by sequence) and all frames (by index) for the whole match, keep 001's `apply`/`state_version`/`latest_frame` behaviour, and expose `snapshot(as_of_ms=None) -> MatchSnapshot`.
- **FR-006**: `MatchSnapshot` MUST be immutable, contain only records with `session_clock_ms ≤ as_of_ms`, carry `state_version` and `as_of_ms`, and provide `event`, `events_between`, `frames_between`, `frame_at(t, tolerance_ms=50)`, `position(player_id, t)`, `attack_direction(team_id, period)`.
- **FR-007**: `state/checkpoint.py` MUST write a full checkpoint every 100 accepted records or 10,000 ms (whichever first) to `checkpoints/{match_id}/{state_version:08d}.json` through `ArtifactStore`, keep the latest 3, append every received envelope to `feed-archive/{match_id}/{session_id}.jsonl`, and never block the live path.
- **FR-008**: `restore(store, match_id)` MUST rebuild `MatchState`, the ingest cursor and dedupe keys from the latest checkpoint, then replay archive lines after the checkpoint's `archive_lines` through the Ingestor; `create_app` MUST restore checkpointed sessions on startup (paused at the restored session clock) when `TACTISTREAM_RESTORE_ON_START=true`.
- **FR-009**: `storage/base.py` MUST define `ArtifactStore` (`put`, `get`, `exists`, `list`, `append`, `delete`) and `ArtifactNotFound`; `storage/local.py` `LocalArtifactStore(root)` MUST implement it with atomic puts and key validation; a reusable contract suite `tests/unit/artifact_store_contract.py` MUST cover the protocol.
- **FR-010**: `GET /api/matches/{match_id}/snapshot?as_of_ms=` MUST return a `Snapshot` as of `min(as_of_ms, current session clock)`; 404 `match_not_found`; 422 `invalid_as_of` for negative or non-integer values.

**Metrics**

- **FR-011**: `metrics/registry.py` `MetricEngine.compute(kind, snapshot, anchor_event_id, *, subject_id=None, moments=())` MUST return a contract-valid `MetricResult` with `metric_id = metric-{kind}-{anchor_sequence:04d}`, `definition_version = "{kind}.v1"`, `limitation_key = "limitation.{kind}"`, `state_version = snapshot.state_version`, deterministic for identical inputs, and memoized.
- **FR-012**: `metrics/geometry.py` MUST provide attack-direction normalization (180° rotation for −x), point-to-segment distance, nearest visible opponents, visible counts, displacement, folded angle to the attack axis and cosine similarity.
- **FR-013**: `pass_completion` MUST be completed ÷ attempted passes by the anchor's team in `[t − 300000, t]`, unit `ratio` (3 dp), components `completed` and `attempted`; `outcome = null` passes excluded and counted in `inputs.excluded_count`.
- **FR-014**: `forward_progress` MUST reuse 001's `compute_forward_progress` unchanged, wrapped by the engine (non-pass anchors → `unavailable/not_applicable`).
- **FR-015**: `rhythm` MUST report completed passes per minute as `value` (unit `per_min`, 2 dp) and turnovers per minute as a separate component (`completed_passes_per_min`, `turnovers_per_min`, `completed_passes`, `turnovers`, `window_min`), never combined into one score, over `min(300000, t − first event)` ms.
- **FR-016**: `pressure` MUST be `(100/3)·Σ exp(−d_i/2.5)` over the 3 nearest visible opponents to the carrier at the anchor (pass, carry or shot), 1 dp, unit `score_0_100`; `unavailable/insufficient_tracking` if the carrier is invisible, the frame is missing, or fewer than 10 of 11 opponents are visible.
- **FR-017**: `channel` MUST be lane clearance (minimum perpendicular distance of visible opponents to the passer→receiver segment) at pass time minus 4,000 ms before, with components `clearance_before_m` and `clearance_at_pass_m` rounded to 0.1 m first; unavailable if passer or receiver is invisible, a frame is missing, or fewer than 10 opponents are visible at either time.
- **FR-018**: `receiver_separation` MUST be the receiver's nearest-opponent distance at pass time minus 4,000 ms before, with components `separation_before_m`, `separation_at_pass_m`, and `separation_at_reception_m` when the reception frame is in the snapshot.
- **FR-019**: `off_ball_run` MUST find, in `[t − 6000, t]` before a pass anchor, the attacking outfield player other than passer and receiver with the largest displacement ≥ 8 m over a span ≤ 4,000 ms, mean speed (displacement ÷ duration) ≥ 4 m/s and folded angle 20–70° to the attack axis; value = displacement (m); `unavailable/insufficient_tracking` if any candidate is invisible in > 20% of window frames; `unavailable/not_applicable` if none qualifies.
- **FR-020**: `defender_follow` MUST take the opponent nearest the runner at run start and report cosine similarity of defender vs runner displacement over the run window (unit `cosine`, 2 dp), components `defender_displacement_m`, `runner_displacement_m`, `subject_ids = [defender, runner]`.
- **FR-021**: `contribution` MUST count, for one player, direct events (actor or completed-pass recipient) inside the windows of the given moments plus moments in which the player is the subject of an `ok` `off_ball_run`; unit `count`, components `direct_events`, `off_ball_involvements`, `moments_considered`; documented as not a rating.
- **FR-022**: `docs/metrics.md` MUST list, for every kind, the formula, parameters with defaults, unit, rounding, unavailable conditions and limitation text; narrative catalogs (`en`, `hi`) MUST contain every `limitation.{kind}` key.

**Moments**

- **FR-023**: `moments/detector.py` `detect_moments(snapshot, metrics) -> list[CandidateMoment]` MUST be a pure function of the snapshot implementing the trigger, window, settle, suppression and coverage rules in data-model.md.
- **FR-024**: `moments/ranking.py` `rank(moments, pinned_player_id=None)` MUST apply `score = base[pattern] + 0.25·strength + 0.15·tracking_coverage + (0.30 if pinned player involved)`, round to 4 dp, and order by (−score, `window.end_ms`, `moment_id`).
- **FR-025**: `moments/pipeline.py` `MomentPipeline` MUST re-detect on new settled triggers and on revisions, diff by `moment_id` ignoring `state_version`, and emit `MomentChange(new | revised | removed)`; it MUST call registered `on_moment` / `on_moment_revised` hooks (used by 004).
- **FR-026**: The session MUST broadcast each moment's metrics as `metric` messages, then `moment`, add metrics to the `EvidenceIndex`, and include moments in WS and REST snapshots.
- **FR-027**: `api/insight_ledger.py` `InsightLedger` MUST record released insight bundles with their `moment_id` and evidence IDs; on a revision the session MUST revoke every affected latest insight version with `insight_revoked{reason: "late_event_revision"}` before re-broadcasting the moment.
- **FR-028**: Moment detection, metrics and ingest MUST NOT read the generation manifest or call any model (constitution II, III).

**Frontend**

- **FR-029**: `matchStore` MUST handle `moment` (upsert by `moment_id`, keeping the higher `state_version`), `metric` (by `metric_id`), `insight_revoked` (hide the card if active, mark the insight revoked) and `error{sequence_gap}` (feed-gap indicator).
- **FR-030**: `MomentList.tsx` MUST list moments by `rank_score` with pattern name (EN/HI chrome strings), session time and a "Partial tracking" badge when `tracking_coverage < 1.0`.

### Key Entities

- **Ingestor / IngestResult / IngestStats**: the guarded entry from bus to state, with per-outcome counts.
- **MatchState / StateDelta / Revision**: whole-match store; deltas report revisions, late frames and gaps.
- **MatchSnapshot**: immutable as-of view consumed by metrics, moments, agent tools and replays.
- **CheckpointData / FeedArchive / Checkpointer**: resumable state and raw feed archive behind `ArtifactStore`.
- **MetricEngine / MetricDefinition / MetricResult**: deterministic measurements with evidence and limitations.
- **CandidateMoment / MomentChange / MomentPipeline**: ranked windows worth explaining, and their lifecycle.
- **InsightLedger**: which released insight depends on which moment and evidence, for revocation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 20/20 shuffled-and-duplicated deliveries of `demo_match` seed 42 produce the in-order `metric_state_hash`; 0 duplicate `event` broadcasts; Blue and Amber completed-pass counts equal the baseline.
- **SC-002**: Hero metrics (`space_creation` 42 A) match the committed golden JSON byte-for-byte, and satisfy channel ≥ 2.0 m, off_ball_run runner `blue-09` ≥ 8.0 m at 20–70°, defender_follow `amber-04` ≥ 0.7; `run_no_channel` 42 A channel < 2.0 m.
- **SC-003**: Over dev seeds 1–20 × variants A–C, positives yield their pattern in 60/60 runs each, negatives yield their positive counterpart in 0/60 runs each, and `tracking_gap` yields no `space_creation` and coverage < 0.9 in 60/60.
- **SC-004**: In every `tracking_gap` run, `pressure`, `channel`, `off_ball_run` and `defender_follow` at the forward pass are `unavailable/insufficient_tracking` (never `ok` with a low value).
- **SC-005**: The late-event test revokes exactly one insight and re-broadcasts `mom-0007` as `space_creation` within one 100 ms tick of the late arrival.
- **SC-006**: Restore after N ∈ {150, 1234, 2500} records reproduces both hashes of the uninterrupted run; restoring `demo_match` takes < 2 s on the Codespace (measured, recorded in research.md).
- **SC-007**: 100% of `ok` metrics in the hero and `demo_match` reference ≥ 1 event ID (and ≥ 1 frame ID for tracking-based kinds), and every referenced ID resolves via the evidence endpoint.
- **SC-008**: Cold full recompute (`detect_moments` on the final `demo_match` snapshot with an empty metric cache) < 1 s; ingest throughput ≥ 2,000 records/s (both measured on the Codespace, recorded in research.md).

## Assumptions

- 002 is merged: `simulate`, all families, `tracking_gap`, `demo_match`, golden hashes; tests use simulator outputs as fixtures (tests may read manifests; live code never does).
- Hero event IDs come from 002 (forward pass `evt-0005`, shot `evt-0007`); if 002's frozen output differs, tests use the manifest's `key_event_ids` and the golden JSON, not hard-coded literals.
- Narrative stays 001's deterministic fact template (cards on completed forward passes) until 004; 003 adds the ledger and revocation mechanics that 004 uses.
- `insight_revoked.reason = late_event_revision` is used for late events *and* late frames (the enum has no separate value); the ledger records which record triggered it.
- The per-player contribution metric uses the MetricId pattern extension in `common.schema.json` (`metric-contribution-0045-blue-09`), accepted on 2026-10-14.
- `tracking_coverage` = share of expected window frames (100 ms grid) in which every involved player is visible and each team has ≥ 10 of 11 players visible; missing frames count as uncovered. This is stricter than "involved players visible" so hidden nearby defenders also lower coverage.
- Press threshold 35.0 and switch separation 5.0 m are prototype parameters, exposed in `params` and documented; they are not validated football statistics.
- One replica, in-memory live state; checkpoints are for restart recovery, not multi-instance coordination (constitution VII).
