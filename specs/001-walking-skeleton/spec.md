# Feature Specification: Walking Skeleton — one event, one verified card, one evidence link

**Feature Branch**: `001-walking-skeleton`

**Created**: 2026-10-14

**Status**: Ready for implementation

**Input**: Build plan, "first build milestone": one synthetic pass enters the pipeline, one verified
explanation reaches the browser, and one evidence reference opens correctly. Day-one exit: one event
reaches a browser and one real Foundry call succeeds.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See a verified card for a synthetic pass (Priority: P1)

A viewer opens TactiStream, presses **Start demo match**, and watches a four-event synthetic fixture
(kickoff, carry, forward pass, carry after receipt) play at 1× speed. When the pass completes, a calm card
appears: "Blue 8 played a forward pass to Blue 11 (13.1 m forward)." The persistent **Synthetic** badge is
visible. Selecting the evidence reference `evt-0042` opens the raw event record in an evidence drawer.

**Why this priority**: Proves the complete loop (feed → bus → state → narrative → checks → WebSocket → UI →
evidence) before any feature depth is added. Every later feature plugs into this path.

**Independent Test**: Start the app locally with the in-memory bus and no Azure credentials, run the
Playwright smoke test; it asserts the card text, the Synthetic badge, and the evidence drawer contents.

**Acceptance Scenarios**:

1. **Given** the app is running with `TACTISTREAM_BUS=memory`, **When** the viewer presses Start demo match,
   **Then** within 2 s of the pass event's server receipt a card with `claim_status = verified_fact` is shown.
2. **Given** the card is visible, **When** the viewer activates evidence `evt-0042` (mouse or keyboard),
   **Then** the drawer shows the event's type, players, coordinates, clocks and `source.kind = synthetic`.
3. **Given** the match is playing, **When** the viewer presses Pause then Reset,
   **Then** playback stops, then the feed restarts from sequence 0 and the card disappears until re-triggered.
4. **Given** the WebSocket drops mid-match, **When** the browser reconnects with its last `seq`,
   **Then** it receives a snapshot plus later messages, and no event appears twice in the UI event list.

---

### User Story 2 - Prove Azure dependencies on day one (Priority: P1)

The builder runs two smoke commands against the real Azure resources: one sends a structured prompt to the
Foundry model deployment through the chosen agent runtime and receives schema-valid JSON; the other
publishes one `FeedEnvelope` to Event Hubs and reads it back through consumer group `live-state`.

**Why this priority**: The build plan's day-one stop rule. Discovering access, quota, region or SDK problems
on day 16 would be fatal; on day 1 it costs an hour.

**Independent Test**: `uv run tactistream-smoke foundry` and `uv run tactistream-smoke eventhubs` each exit 0
and print measured latency; results are recorded in `research.md`.

**Acceptance Scenarios**:

1. **Given** `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_MODEL_DEPLOYMENT` are set and `az login` is done,
   **When** the builder runs the Foundry smoke, **Then** it prints the deployment name, region, latency in ms,
   token usage, and a JSON object that validates against a tiny test schema.
2. **Given** Event Hubs env vars are set, **When** the builder runs the Event Hubs smoke,
   **Then** the envelope read back equals the one sent (same `record_id`, same payload) and round-trip ms is printed.
3. **Given** credentials are missing, **When** either smoke runs, **Then** it exits non-zero with a message naming
   the missing variable, without a stack trace.

---

### User Story 3 - Contract-first guardrails in CI (Priority: P2)

Every push runs CI that validates all contract examples against the JSON Schemas, round-trips them through
the Pydantic models, regenerates TypeScript types and fails on drift, and runs lint, types, unit tests,
frontend build and the Playwright smoke.

**Why this priority**: Constitution IV and V. Protects every subsequent feature from silent contract drift.

**Independent Test**: Introduce a deliberate field rename in one Pydantic model on a branch; CI fails on the
contract test. Revert; CI passes.

**Acceptance Scenarios**:

1. **Given** a schema change without regenerated TS types, **When** CI runs, **Then** the drift job fails.
2. **Given** a clean `main`, **When** CI runs, **Then** all jobs pass in under 10 minutes.

### Edge Cases

- Duplicate delivery of `evt-0042` → exactly one card, one event in the list (dedupe by `kind`+`record_id`).
- Pass event arrives with `outcome = null` → factual card says the pass was attempted; no progress number shown.
- Output check finds a number in card text absent from evidence → card is not released; `narrative_status = fallback`
  with `fallback_reason = output_check_failed` is sent and the plain event row remains visible.
- Browser connects after the match ended → snapshot contains all events and the released card.
- Unknown evidence ID requested → HTTP 404 with `{"error":"evidence_not_found"}`; drawer shows "Evidence unavailable".

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load the fixture `data/fixtures/skeleton.jsonl` (metadata + 4 events + 10 Hz frames for 6 s) and replay it on the `FeedBus` at 1× session speed with play, pause and reset.
- **FR-002**: System MUST provide `FeedBus` with an `InMemoryBus` implementation supporting independent consumer groups and an `EventHubsBus` implementation with identical semantics (partition key = `match_id`).
- **FR-003**: Ingest MUST stamp `server_receipt_ms`, validate envelopes against contracts, and drop duplicates by (`kind`, `record_id`).
- **FR-004**: Match state MUST keep metadata, ordered events, latest frame and a monotonically increasing `state_version`.
- **FR-005**: For each completed forward pass the system MUST compute `forward_progress` (end − start along the team's attack direction, metres, 1 decimal) as a `MetricResult` with input event IDs.
- **FR-006**: For each such pass the system MUST produce an `InsightPacket` via the deterministic fact template `fact.forward_pass` for all four (mode × language) variants, with `claim_status = verified_fact`.
- **FR-007**: Output checks MUST verify every number, player name and evidence ID in packet text exists in the referenced evidence before release.
- **FR-008**: API MUST expose `GET /healthz`, `POST /api/sessions`, `POST /api/matches/{match_id}/control`, `GET /api/matches/{match_id}/evidence/{evidence_id}` and WebSocket `/ws/matches/{match_id}` per `contracts/rest-api.md` and `contracts/ws-protocol.md`.
- **FR-009**: WebSocket MUST send a `snapshot` on connect, then `event`, `frame`, `metric`, `insight` messages with a monotonic `seq`; on `resume` with `last_seq` it MUST send a fresh snapshot and only messages with `seq > last_seq` that are not covered by the snapshot.
- **FR-010**: Frontend MUST show top bar (session clock, Synthetic badge, mode and language placeholders), main surface (event list for now), one insight card at a time, and an evidence drawer resolving IDs through the evidence endpoint.
- **FR-011**: Frontend MUST send `display_ack` when a card is first rendered; server MUST record `fast_overlay_latency_ms = ack_received_ms − server_receipt_ms` (an upper bound, documented as such) to telemetry.
- **FR-012**: `tactistream-smoke foundry` MUST call the Foundry model deployment through the agent runtime selected in `research.md` and validate structured JSON output.
- **FR-013**: `tactistream-smoke eventhubs` MUST publish and consume one envelope via consumer group `live-state`.
- **FR-014**: CI MUST run backend lint/type/test, contract validation, TS drift check, frontend lint/type/test/build, and the Playwright smoke.
- **FR-015**: Repository MUST include `.env.example` (names only), `README.md` quickstart and a single command to run the demo locally (`make dev`).

### Key Entities

- **FeedEnvelope**: transport wrapper (kind, match_id, record_id, timestamps, payload). See `contracts/schemas/feed_envelope.schema.json`.
- **MatchEvent / TrackingFrame / MatchMetadata**: synthetic match records.
- **MetricResult**: `forward_progress` only in this feature.
- **InsightPacket / InsightBundle**: render instruction for one or all variants.
- **MatchSession**: one running replay + state + WebSocket hub for one `match_id`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a fresh clone, `make dev` then Start demo match shows the verified card within 2 s of pass receipt (Playwright smoke passes 5/5 consecutive runs).
- **SC-002**: The evidence drawer opens the correct record for 100% of evidence IDs on the card.
- **SC-003**: Foundry smoke and Event Hubs smoke each succeed once against real Azure; deployment name, region, SDK versions and measured latency are recorded in `research.md`.
- **SC-004**: Replaying the fixture with every envelope duplicated and adjacent pairs swapped yields the same final `state_version`-independent state hash and exactly one card.
- **SC-005**: CI passes on `main`; a deliberate contract drift makes CI fail.

## Assumptions

- Azure subscription, Foundry project with a deployed chat model, and Event Hubs rights are available (user confirmed).
- The walking skeleton uses a hand-authored fixture; the real simulator arrives in 002 and replaces it behind the same replayer.
- No agents are used for the card yet; the deterministic fact template is the same fallback path 004 will reuse.
- Hindi text for `fact.forward_pass` is drafted now and reviewed in 006.
