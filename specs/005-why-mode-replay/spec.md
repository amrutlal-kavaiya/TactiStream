# Feature Specification: Why Mode — evidence-backed 3D tactical replay

**Feature Branch**: `005-why-mode-replay`

**Created**: 2026-10-14

**Status**: Ready for implementation

**Input**: Build plan, "Why Mode" (the central experience): a restrained card "Space opened before the shot" →
"Why?" → replay the preceding 8–12 seconds on a simplified 3D pitch → highlight the runner, the defender's path
and the measured opening → "Evidence" expands timestamps, coordinates, metrics, definitions, source events and the
"Interpretation" vs fact status. Scope-table row: "One polished replay plus two additional event patterns"; "All
visible positions come from supplied or synthetic tracking". Roadmap exit (18–19 Oct): "Off-ball space-creation
sequence works end to end in 3D with evidence drawer; two more patterns replay."

**Depends on**: 001 (WsHub, MatchSession, EvidenceIndex, InsightCard, EvidenceDrawer, matchStore, i18n),
002 (seeded scenarios `space_creation`, `press_turnover`, `switch_escape`, missing-data fixture),
003 (MatchSnapshot, MetricEngine, `moments/detector.py`, `moments/ranking.py`, metric kinds `channel`,
`defender_follow`, `off_ball_run`, `pressure`, `receiver_separation`), 004 (`explain_moment`, ProducerOutput
ModePlans with `annotations`, InsightBundle with 4 variants, scripted model client).

**Stop rule (binding, from the roadmap)**: if Why Mode is not stable by **19 Oct 2026**, cut upload, screen sharing
and forecasts completely (they are already outside the MVP) and spend the freed time here. No "after essentials"
work starts while any acceptance scenario below fails.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask "Why?" and watch the hero replay (Priority: P1) 🎯 MVP

A viewer starts the demo match (scenario `space_creation`, seed 42). Blue 9 makes a diagonal off-ball run, an Amber
defender moves with him, the central channel between Blue 8 and Blue 11 widens, the forward pass goes through, and
the move ends with a shot. A calm card appears: "Space opened before the shot". The viewer presses **Why?**. The main
surface switches from the match to a tactical replay of the preceding 8–12 s on a simplified 3D pitch. Blue 9 is
ringed, the defender's path is drawn as a trail, and a channel band between passer and receiver visibly widens from
the measured "before" clearance to the measured clearance at the moment of the pass. The viewer can pause, scrub,
switch 0.5×/1×, loop, change camera (broadcast / top-down / follow runner) and return to live.

**Why this priority**: This is the product. Without it TactiStream is a ticker with captions. It is also the
0:08–0:30 segment of the demo video.

**Independent Test**: With `TACTISTREAM_AGENTS=scripted`, run Playwright `why-mode.spec.ts`: start the demo → card
"Space opened before the shot" → click **Why?** → `[data-testid="replay-view"]` visible with a canvas, replay state
`playing`, and the screen-reader scene description lists the highlighted runner, the defender path and the channel.
Backend golden test `test_scene_golden.py` proves every drawn coordinate comes from frames and every number from
the metric engine.

**Acceptance Scenarios**:

1. **Given** the hero insight is released for moment `mom-NNNN` (pattern `space_creation`), **When** the viewer
   activates **Why?** (click, or Enter on the focused button), **Then** within 1.5 s the main surface shows the
   tactical replay of window `[start_ms, end_ms]` with `8000 ≤ end_ms − start_ms ≤ 12000` (shorter only if the match
   is younger than 8 s), playing at 1×, and the live surface is hidden but keeps receiving messages.
2. **Given** the replay is open, **When** time passes, **Then** the runner (`highlight_blue_09`) carries a ring that
   follows his interpolated position, the defender's path (`path_amber_04`) is revealed up to the current replay
   time, and the channel band (`show_channel_0042`) animates its half-width from `clearance_before_m` to
   `clearance_at_pass_m` between the two keyframe times supplied by the server.
3. **Given** the replay is open, **When** the viewer pauses, drags the scrubber, sets 0.5×, toggles loop, or picks a
   camera preset, **Then** the scene reflects the new cursor/speed/camera within one rendered frame; scrubbing outside
   the window clamps to its bounds.
4. **Given** the replay is open, **When** the viewer selects **Back to live** (or presses Escape), **Then** the main
   surface returns to the live pitch at the current session clock, and focus returns to the **Why?** button.
5. **Given** any frame of the replay, **When** an entity is drawn, **Then** its position equals a supplied tracking
   position or a linear interpolation between two consecutive supplied frames in which it is visible; no position
   is invented by the client or by any model.

---

### User Story 2 - Inspect the evidence behind the explanation (Priority: P1)

From the card or the replay the viewer opens **Evidence**. The drawer lists every evidence ID on the card. For the
channel metric it shows its definition and limitation, the time window, the value with unit, the named components
(`clearance_before_m`, `clearance_at_pass_m`), the contributing events (as links) and frames, and the scene geometry
used for the band (passer, receiver and nearest-defender coordinates at both keyframes). The header clearly separates
"Verified fact" records from the card's "Interpretation" status.

**Why this priority**: Constitution I ("Evidence before narrative"); the 0:30–0:43 demo segment; judges must be able
to challenge every number.

**Independent Test**: `EvidenceDrawer.replay.test.tsx` (component) and the Evidence step of `why-mode.spec.ts`:
drawer contains an ID matching `metric-channel-\d{4}`, a value matching `\d+\.\d m`, the definition text, and the
label "Interpretation".

**Acceptance Scenarios**:

1. **Given** the hero card is visible, **When** the viewer activates **Evidence**, **Then** a labelled dialog lists
   all `evidence_ids` of the active variant, each resolvable through `GET /api/matches/{id}/evidence/{evidence_id}`.
2. **Given** a `channel` metric record, **When** it is expanded, **Then** the drawer shows definition, limitation,
   window (`mm:ss.s – mm:ss.s` session clock), value and unit, components with units, input event IDs as links,
   frame count with first/last frame IDs, and `definition_version`.
3. **Given** the drawer was opened from the replay, **When** the channel record is expanded, **Then** a "Scene
   geometry" section shows the passer, receiver and nearest-defender coordinates (metres, 1 decimal) for both
   keyframes, identical to the `SceneAnnotations` payload.
4. **Given** the card's `claim_status` is `interpretation_supported`, **When** the drawer opens, **Then** the header
   shows "Interpretation" for the card's conclusion and each event/metric record is labelled "Verified fact"
   (measured); for `verified_fact` cards no "Interpretation" label appears.
5. **Given** an event link inside a metric record, **When** activated, **Then** the drawer navigates to that event
   record and offers Back; focus is managed and returns to the trigger on close.

---

### User Story 3 - Honest degradation when tracking is missing (Priority: P2)

A moment whose spatial evidence is missing (002's missing-data fixture) still shows its ordinary event card.
Pressing **Why?** shows "Insufficient tracking for this explanation" together with the moment's events; no 3D
geometry is drawn. When only some players are missing for part of a window, the replay still plays, those players
are simply not drawn while unavailable, and a "Partial tracking" badge is shown.

**Why this priority**: Constitution I and the 1:13–1:28 demo segment ("Trigger a labeled missing-data fixture").
A reassuring fake replay would be worse than none.

**Independent Test**: `test_replay_insufficient.py` (409 with events) and Playwright `why-mode-insufficient.spec.ts`.

**Acceptance Scenarios**:

1. **Given** a moment with `tracking_coverage < 0.6` or a required spatial metric `unavailable` with reason
   `insufficient_tracking`, **When** the client requests its replay, **Then** the API answers 409
   `insufficient_tracking` whose body still contains `moment` and the window's `events`.
2. **Given** that 409, **When** the replay view renders, **Then** it shows "Insufficient tracking for this
   explanation" (in the current UI language), the ordinary event card(s) for the moment's events, and no canvas.
3. **Given** a window where `amber-06` is invisible from 40.0 s to 41.0 s, **When** the replay passes that interval,
   **Then** `amber-06` is not drawn at any time strictly between its last visible frame before and its first visible
   frame after the gap, and the "Partial tracking" badge is visible for the whole replay.
4. **Given** an annotation whose player is invisible for the entire window, **When** the scene is built, **Then**
   the annotation appears in `unresolved` with reason `player_not_visible` and nothing is drawn for it.

---

### User Story 4 - Two more patterns replay correctly (Priority: P2)

The same Why flow works for a pressing trap that ends in a turnover (`press_turnover`) and a switch of play that
escapes local pressure (`switch_escape`). Each replay shows pattern-appropriate annotations: a pressure ring around
the pressed carrier and the ball winner highlighted for the press; the pressed passer's ring plus the switch
receiver's highlight and path for the switch.

**Why this priority**: Scope-table completion condition ("one polished replay plus two additional event
patterns") and the 0:58–1:13 demo segment ("Load an unseen seed or alternate sequence").

**Independent Test**: `test_replay_patterns.py` (parametrized) and `why-mode-patterns.spec.ts`.

**Acceptance Scenarios**:

1. **Given** scenario `press_turnover` seed 42 has released a moment of pattern `press_turnover`, **When** its replay
   is requested, **Then** the response is 200 with at least one resolved `pressure_ring` annotation whose `radius_m`
   equals the largest distance among the (up to three) nearest visible opponents to the carrier at the anchor frame.
2. **Given** scenario `switch_escape` seed 42 has released a moment of pattern `switch_escape`, **When** its replay is
   requested, **Then** the response is 200 with a resolved `highlight` for the switch receiver and a `pressure_ring`
   for the passer.
3. **Given** either replay, **When** it plays in the browser, **Then** no console errors occur and the scene
   description lists the same annotations as the response.

---

### User Story 5 - Live 3D pitch, keyboard timeline and comfortable motion (Priority: P3)

During live play the main surface shows the same simplified 3D pitch fed by live 10 Hz frames. A bottom timeline
marks key moments; the viewer can seek ±1 s with ←/→, jump with Home/End, and press Enter on a focused moment
marker to open its Why replay. Viewers who prefer reduced motion get instant camera cuts, no pulsing emphasis and a
replay that starts paused. A developer-only FPS overlay and a capture script measure rendering performance.

**Why this priority**: Makes the demo feel like one product and satisfies keyboard/accessibility expectations; it
builds on US1's scene components and can be cut back (live list view) without breaking Why Mode.

**Independent Test**: `Timeline.test.tsx`, `MainSurface.test.tsx`, `a11y.spec.ts` (axe), and running
`node frontend/scripts/capture-fps.mjs` which writes an FPS report JSON.

**Acceptance Scenarios**:

1. **Given** a live match, **When** frames arrive, **Then** the live pitch draws only visible players and the ball at
   their supplied positions, with team colour, team-specific marker shape and shirt-number labels.
2. **Given** focus on the timeline slider, **When** the viewer presses → / ← / Home / End, **Then** the active clock
   moves +1 s / −1 s / to start / to end (live: via the match `seek` control; replay: via the replay cursor).
3. **Given** focus on a key-moment marker, **When** the viewer presses Enter, **Then** that moment's Why replay
   opens (same as US1 scenario 1).
4. **Given** `prefers-reduced-motion: reduce`, **When** a replay opens, **Then** it starts paused at the window start,
   camera preset changes cut instantly, and emphasis animations are static.
5. **Given** a new insight is released, **When** it becomes the active card, **Then** it is announced through a polite
   `aria-live` region exactly once.

### Edge Cases

- **Moment unknown or not yet detected as of the session clock** → 404 `moment_not_found`; the **Why?** button is only
  rendered when the store holds a `CandidateMoment` with the packet's `moment_id` (001 fact-only cards whose moment
  was never detected show no Why button).
- **No released insight for the moment yet** (narrative still analysing, or fallback) → the replay uses deterministic
  `default_annotations(moment)` and reports `annotation_source = "default"`; the view still works.
- **Model-requested annotation that cannot be resolved** (unknown player, metric unavailable, outside window) → listed in
  `scene.unresolved` with a reason; never drawn; never causes a 500.
- **Window starts before the first frame** (moment within first 8 s) → `start_ms` clamps to the first frame time; the
  window may be shorter than 8 s and the UI shows its true length.
- **Frame gap** (consecutive frames > 150 ms apart) → nothing is interpolated across the gap; entities are drawn only
  on frames inside the gap boundaries; `partial_tracking = true`.
- **Ball invisible** → ball not drawn; ball height used when present (`height_m`), else 0.11 m (ball radius).
- **Higher-priority insight released while a replay is open** → the replay is not interrupted; the new card is queued
  to the timeline with a "New" badge; Back to live shows it if still valid.
- **Insight revoked (`insight_revoked`) while its replay is open** → replay stays (frames are facts) but the card
  panel shows "This explanation was withdrawn" and the Interpretation label is removed.
- **Reset of the match while replaying** → the replay closes, surface returns to live, cached replays are cleared.
- **WebGL unavailable** → the main surface shows the event list (001 behaviour) and a notice "3D replay unavailable in
  this browser"; Evidence still works.
- **Two viewers on one match** → replays are read-only per client; no control message is sent by opening Why.
- **Very slow device** → the FPS overlay (dev) shows the measured rate; rendering never blocks WebSocket processing
  (frames are applied to refs, not React state, per animation frame).

## Requirements *(mandatory)*

### Functional Requirements

**Backend — replay endpoint and scene annotations**

- **FR-001**: System MUST expose `GET /api/matches/{match_id}/replay/{moment_id}` returning
  `{moment, frames, events, scene}` per `contracts/replay-api.md`, where `frames` are all 10 Hz tracking frames with
  `session_clock_ms` in the replay window (inclusive) and `events` are all events with `session_clock_ms` in the
  window plus the moment's trigger event; responses only include records with `session_clock_ms ≤` the current
  session clock (as-of rule).
- **FR-002**: The replay window MUST be computed by `replay_window(moment, first_frame_ms)`:
  `end = moment.window.end_ms`, `start = clamp(moment.window.start_ms, end − 12000, end − 8000)`, then
  `start = max(start, first_frame_ms)`.
- **FR-003**: `SceneAnnotations` MUST be computed deterministically server-side in
  `backend/src/tactistream/moments/scene.py` from annotation IDs only; identical inputs MUST produce byte-identical
  JSON. No model call occurs on the replay path.
- **FR-004**: Annotation IDs MUST be resolved as: `highlight_{team}_{NN}` → player ID `{team}-{NN}`;
  `path_{team}_{NN}` → polyline of that player's supplied positions in the window, split into segments at every
  invisibility or frame gap; `show_channel_{seq}` → metric `metric-channel-{seq}` keyframes at its two input frames
  (`before`, `at_pass`) with passer/receiver segment endpoints taken from those frames, `clearance_m` copied exactly
  from components `clearance_before_m` / `clearance_at_pass_m`, and the nearest visible defender (to the segment)
  with its position and closest point on the segment; `pressure_ring_{team}_{NN}` → carrier `{team}-{NN}`, the
  matching `pressure` metric, anchor frame, carrier centre and `radius_m` = largest distance among the up to three
  nearest visible opponents at the anchor frame (0.1 m precision).
- **FR-005**: The set of annotation IDs MUST be the union of `render.annotations` over all variants of the latest
  released insight bundle for the moment (`annotation_source = "insight"`), or, when none is released,
  `default_annotations(moment, metrics)` (`annotation_source = "default"`) using the pattern rules in
  `contracts/replay-api.md`.
- **FR-006**: Unresolvable annotations MUST be returned in `scene.unresolved` with one of the reasons
  `unknown_player`, `player_not_visible`, `metric_missing`, `metric_unavailable`, `outside_window`,
  `inconsistent_geometry`, and MUST NOT be drawn.
- **FR-007**: If `moment.tracking_coverage < 0.6` or any `channel`/`pressure`/`defender_follow`/`off_ball_run` metric
  needed by the requested annotations is `unavailable` with reason `insufficient_tracking`, the endpoint MUST answer
  409 `{"error":"insufficient_tracking", "moment", "events"}` (events still included).
- **FR-008**: `scene.partial_tracking` MUST be `true` when any player or the ball is invisible in any window frame or
  any frame gap > 150 ms exists in the window.
- **FR-009**: The endpoint MUST answer 404 `match_not_found` / `moment_not_found` for unknown IDs, cache built responses
  by `(moment_id, moment.state_version, annotation-set hash)`, and compress responses ≥ 1 KB (gzip).
- **FR-010**: The evidence endpoint MUST accept `?language=en|hi` and, for metric records, add
  `presentation {definition, limitation, unit_label, language}` rendered from catalog keys `metric_def.{kind}` and
  the record's `limitation_key`.

**Frontend — scene, replay controller, views**

- **FR-011**: Frontend MUST render a simplified pitch in `frontend/src/scene/PitchScene.tsx` (React Three Fiber): a
  105 × 68 m plane with standard markings (touch/goal lines, halfway line, centre circle 9.15 m, penalty areas
  16.5 × 40.32 m, goal areas 5.5 × 18.32 m, penalty spots, goals 7.32 m), metres as world units, mapped by
  `toWorld([x, y], h) = [x − 52.5, h, 34 − y]`.
- **FR-012**: `Players.tsx` MUST draw players with one instanced mesh per team, team colour from metadata, a
  team-specific marker shape (Blue disc, Amber diamond) and a shirt-number text label, so colour is never the only
  cue; invisible players are not drawn. `Ball.tsx` draws the ball only when visible.
- **FR-013**: `Annotations.tsx` MUST draw highlight rings (following the player), path trails (revealed up to the
  cursor, per segment), the channel band (segment between passer and receiver with half-width = clearance, animating
  linearly between keyframes and labelled "before → at pass" values in metres) and pressure rings (carrier-centred,
  fixed radius, visible ±1.5 s around the anchor); geometry is computed by pure functions in
  `frontend/src/scene/annotationGeometry.ts`.
- **FR-014**: `frontend/src/replay/ReplayController.ts` MUST be a framework-free time cursor with play, pause, seek
  (clamped to the window), speed (0.5× or 1× only), loop, `tick(dtMs)` and `sample(tMs)` that linearly interpolates
  each entity only between two consecutive frames ≤ 150 ms apart in which it is visible, and never across
  invisibility or frame gaps.
- **FR-015**: `CameraRig.tsx` MUST offer presets `broadcast`, `top_down`, `follow_runner` (follows the first highlighted
  player; disabled when there is none); transitions animate ≤ 600 ms or cut instantly under reduced motion.
- **FR-016**: `WhyButton.tsx` MUST appear on the insight card when the store holds the packet's moment, open the replay
  via `matchStore.openReplay(momentId)`, and be keyboard-operable.
- **FR-017**: `ReplayView.tsx` MUST fetch the replay through `api/client.ts#getReplay`, drive `PitchScene` with a
  `ReplayController`, filter drawn annotations to the active variant's `render.annotations` (all resolved
  annotations when no variant), show "Tactical replay", the Synthetic badge and, when flagged, "Partial tracking",
  and render the 409 state with "Insufficient tracking for this explanation" plus the ordinary event card(s).
- **FR-018**: The main surface (`MainSurface.tsx`) MUST switch between the live pitch (fed by the latest live frame)
  and the tactical replay; the WebSocket keeps processing while replaying.
- **FR-019**: `Timeline.tsx` MUST show key-moment markers (from store moments), act as a slider for the active clock
  with ←/→ = ∓/±1 s, Home/End, and Enter on a focused marker opening its Why replay; in replay mode it spans the
  replay window and shows event ticks.
- **FR-020**: `EvidenceDrawer.tsx` MUST show, per record kind, the fields listed in US2 scenarios 2–4 including
  definitions, windows, coordinates, components, source events and evidence status labels.
- **FR-021**: The UI MUST honour `prefers-reduced-motion`, announce new active cards via a polite `aria-live` region,
  provide a text alternative of the scene (`SceneDescription.tsx`), and keep all controls keyboard-operable with
  visible focus.
- **FR-022**: A dev-only FPS overlay (`import.meta.env.DEV` or `?fps=1`) MUST display the measured frame rate and
  expose samples on `window.__tactistreamFps`; `frontend/scripts/capture-fps.mjs` MUST open a replay with Playwright,
  collect samples for a given duration and write `eval/results/fps/fps-<ISO timestamp>.json`.
- **FR-023**: `three`, `@react-three/fiber` and `@react-three/drei` MUST be added with exact pinned versions (no
  ranges) and listed in `docs/permitted-assets.md`.
- **FR-024**: All new UI chrome strings MUST exist in both `frontend/src/i18n/en.ts` and `hi.ts` (Hindi drafted here,
  reviewed in 006).

### Key Entities

- **ReplayResponse**: `{moment: CandidateMoment, frames: TrackingFrame[], events: MatchEvent[], scene: SceneAnnotations}`.
- **ReplayUnavailable**: 409 body `{error: "insufficient_tracking", detail, moment, events}`.
- **SceneAnnotations**: schema-versioned, deterministic description of drawable annotations for one moment: window,
  `annotation_source`, `partial_tracking`, `tracking_coverage`, resolved `annotations[]` (discriminated by `kind`:
  `highlight`, `path`, `channel`, `pressure_ring`) and `unresolved[]`.
- **ChannelKeyframe**: phase (`before` | `at_pass`), time, frame ID, passer/receiver positions, `clearance_m`, nearest
  defender ID/position, closest point on segment.
- **ReplayController / SampledFrame**: client-side cursor and the interpolated drawable state at a time.
- **FrameSource**: interface consumed by `PitchScene` (`tick?`, `sample`), implemented by `ReplayController` and the live
  frame source.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Playwright `why-mode.spec.ts` (start demo seed 42 → card → Why → replay visible → Evidence shows
  `metric-channel-\d{4}` with a metre value and the "Interpretation" label) passes 5/5 consecutive runs on a fresh
  clone; the replay view is visible ≤ 1.5 s after the Why click in every run.
- **SC-002**: For the hero moment, 100% of channel keyframe endpoints equal the passer/receiver positions in the
  referenced frames, both `clearance_m` values equal the metric components exactly, and the golden file
  `backend/tests/golden/scene_space_creation_42.json` is byte-identical across 3 consecutive runs.
- **SC-003**: In automated tests, 100% of sampled player/ball positions at frame times equal supplied positions, and 0
  positions are drawn for invisible entities or inside frame gaps (missing-data and partial fixtures).
- **SC-004**: The missing-data fixture yields 409 `insufficient_tracking` with events in 100% of requests, and the UI
  shows the insufficient-tracking message plus the ordinary event card (Playwright).
- **SC-005**: `press_turnover` and `switch_escape` (seed 42) each return 200 with their pattern-specific annotations
  resolved, and their Playwright replays run with 0 console errors.
- **SC-006**: `capture-fps.mjs` produces a report; on the builder's development machine the hero replay's measured mean
  is ≥ 30 fps (recorded with hardware, browser and duration in `research.md`; the release measurement on the named demo
  machine belongs to 008).
- **SC-007**: Replay endpoint server time p95 ≤ 300 ms for a 12 s window over 20 local requests (measured in the
  integration test and recorded; a target, not a claim).
- **SC-008**: axe-core reports 0 serious or critical violations on the live and replay views, and every replay control
  and timeline action in US5 is completable with the keyboard alone (Playwright).

## Assumptions

- 002 provides scenario IDs `space_creation`, `press_turnover`, `switch_escape` and a missing-data fixture selectable via
  `POST /api/sessions {"scenario": …, "seed": 42}`; the hero roles are Blue 9 (runner), an Amber defender (`amber-04`
  in `contracts/examples`), Blue 8 (passer) and Blue 11 (receiver). Exact IDs come from seed 42 and are frozen in the
  golden file; the illustrative IDs in this spec are the ones in `contracts/examples/`.
- 003's `channel` metric lists exactly two `inputs.frame_ids` ordered `[before, at_pass]` and `subject_ids`
  `[passer, receiver]`; `pressure` metrics have `subject_ids[0]` = carrier; `defender_follow` and `off_ball_run` list the
  runner (and, for `defender_follow`, the defender) in `subject_ids`; `CandidateMoment.tracking_coverage` is the share
  of window frames in which the moment's involved players are visible.
- 003's `MatchSnapshot` can return frames and events between two session times; if its method names differ, only
  `moments/scene.py` and `api/replay.py` adapt.
- 004's scripted model client releases the hero interpretation (`interp.space_opened_by_run`) deterministically, so e2e
  tests run without network; requested annotations already passed 004's output checks.
- Replays are client-side views; opening Why never pauses or seeks the shared match.
- The 3D scene is intentionally simplified (no stadium, crowd or player models); stadium work is out of scope.
- WebGL 2 is available on the demo machine; a non-WebGL fallback (event list) is sufficient elsewhere.
