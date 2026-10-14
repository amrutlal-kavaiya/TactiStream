# Feature Specification: Submission — judge-ready repo, demo route, 115-second video, verified entry

**Feature Branch**: `009-submission`

**Created**: 2026-10-14

**Status**: Ready for implementation

**Input**: Build plan sections "The verified event constraints shape the build", "Use the first seconds of the demo to show the
value", "Choose one initial buyer", "Finish with proof that someone else can run it", and the calendar rows 24–27 Oct (IST):
**24 Oct** feature freeze + UI polish + documentation (optional export only if stable); **25 Oct** record the 115-second demo +
fresh-session rehearsal; **26 Oct** submit and verify links; **27 Oct** buffer and final availability checks. External dates:
registration must be completed **before 20 Oct** (closes 21 Oct 00:30 IST); submission closes **28 Oct 12:29 IST**; judging access
through **10 Nov 2026 Pacific Time**. Organizer and Innovation Studio instructions override this spec wherever they differ.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A judge reaches the hero moment in one click (Priority: P1)

A judge opens `https://<app>/demo?seed=42` from the README. The hero synthetic match (Blue vs Amber, space creation, seed 42)
starts automatically; within seconds the "Space opened before the shot" card appears. A compact **Judge tools** panel offers:
Restart demo, Load another sequence (unseen seed), Simulate model timeout, Inject bad claim, Load tracking-gap example, and
Open Evidence. Restarting never requires editing a database: each visit or restart creates a fresh in-memory session.

**Why this priority**: "Working judging experience" is an official rule; judges have little time, so the first click must show
value. The route is also the recording surface for the video.

**Independent Test**: Playwright `demo-route.spec.ts` opens `/demo?seed=42` with no other interaction and asserts autoplay, the
hero card, the Synthetic badge, and each Judge tools action's visible outcome.

**Acceptance Scenarios**:

1. **Given** a fresh browser, **When** the judge opens `/demo?seed=42`, **Then** a session is created for scenario
   `space_creation` seed 42, playback starts without a click, and the hero card appears within the narrative deadline of its
   trigger (fallback template allowed, labelled).
2. **Given** a running demo, **When** the judge presses **Restart demo**, **Then** a new session with the same seed starts from 0
   and the previous session's cards are gone; the URL stays `/demo?seed=42`.
3. **Given** the Judge tools panel, **When** the judge presses **Simulate model timeout** before the next moment, **Then** the next
   narrative shows the labelled fallback template and the event overlays keep updating.
4. **Given** the Judge tools panel, **When** the judge presses **Inject bad claim**, **Then** the trace view shows the rejected
   claim with its reason and the released card contains no unsupported value.
5. **Given** `/demo?seed=abc` or an unknown scenario, **When** loaded, **Then** the page falls back to seed 42 / `space_creation`
   and shows a one-line notice.
6. **Given** the server is at its session limit, **When** a new judge opens `/demo`, **Then** the page shows "The live demo is busy —
   retry in a minute" with a link to the demo video, not a blank screen.

---

### User Story 2 - A judge understands and can run the project from the repository (Priority: P1)

The public repository opens with a judge-first README: the pitch line, the live link and `/demo` link, the video link, a
one-command local run, a "What is live / synthetic / cached / planned" table, the Best Multi-Agent System rationale, and links to
the docs set: architecture (deployed services only, actual model deployment and region), agents, metrics, results, limitations,
permitted assets, judge guide, operations and business. A fresh clone runs locally with one command.

**Why this priority**: Official rules require a public repository and the five criteria are judged from it; "proof that someone
else can run it" is a build-plan requirement.

**Independent Test**: CI `docs` job passes (link check, Mermaid render, claims test); a fresh Codespace runs `make install && make dev`
and the `/demo?seed=42` Playwright test passes against it.

**Acceptance Scenarios**:

1. **Given** the README, **When** a judge reads the first screen, **Then** it shows the pitch line "TactiStream turns a football event
   stream into a tactical story you can inspect, replay, and personalize.", the live link, the demo route, the video link and the
   Synthetic-data statement.
2. **Given** `docs/architecture.md`, **When** compared with `docs/deployment-inventory.json`, **Then** every Azure/Fabric service in the
   diagram is in the inventory and used; anything not deployed is absent or under "Planned".
3. **Given** a fresh clone with only Node 22 and uv installed, **When** the judge runs `make install && make dev` and opens
   `http://localhost:5173/demo?seed=42`, **Then** the hero card appears with the in-memory bus and deterministic templates (no Azure needed).
4. **Given** the docs set, **When** the claims test scans it, **Then** no banned claim appears (official Premier League integration,
   production accuracy, xG, forecasts, "expert validated" without an expert, multi-instance scale) and every number cites
   `docs/results.md`.

---

### User Story 3 - The 115-second demo video tells the story (Priority: P1)

The builder records the working deployed app following `demo-script.md` (0:00–1:55): shot, Why replay, evidence, Fan→Analyst→Hindi,
pin, unseen sequence, fixture with blocked claim and fallback, recap with overlay JSON, measured results and live link. The final
video is under 2 minutes, 1080p, English narration with captions, no secrets on screen. A backup recording is labelled as such.

**Why this priority**: The video is mandatory and carries the User Experience & Presentation criterion.

**Independent Test**: The recording checklist in `demo-script.md` is completed and `ffprobe` reports duration < 120 s and 1920×1080;
a second person (or the builder after 2 h) watches it once and can name the three agents and the evidence check.

**Acceptance Scenarios**:

1. **Given** the script, **When** the take is reviewed, **Then** each beat starts within ±3 s of its planned time and the total is
   1:50–1:58.
2. **Given** the recorded frames, **When** checked against the checklist, **Then** no key, connection string, email inbox, or portal
   secret is visible, and the cursor is visible in every interaction shot.
3. **Given** a backup recording exists, **When** it is published or played, **Then** its title and first frame say "Backup recording"
   with the recording date.

---

### User Story 4 - The entry is submitted, verified and kept available (Priority: P1)

Registration is confirmed before 20 Oct. On 26 Oct the builder submits through the official channel with the repository URL,
live URL, video URL, description (draft in `submission-checklist.md`), team members (≤ 4) and category Best Multi-Agent System,
then verifies every link from a logged-out browser on another device and network. Availability is checked on 27 Oct and daily
through 10 Nov PT.

**Why this priority**: A missed field or broken link nullifies the work; the deadline is fixed.

**Independent Test**: `submission-checklist.md` is fully ticked with timestamps and the confirmation reference; the uptime workflow
(007) is green every day through 10 Nov.

**Acceptance Scenarios**:

1. **Given** 26 Oct, **When** the form is submitted, **Then** the confirmation (email or page) is saved and its reference is recorded
   in the checklist, at least 40 hours before the 28 Oct 12:29 IST close.
2. **Given** a logged-out browser on a different network, **When** each submitted link is opened, **Then** the repository is public,
   the live app reaches the hero card via `/demo?seed=42`, and the video plays without sign-in.
3. **Given** the five equal-weight criteria, **When** a judge reads the README "For judges" table, **Then** each criterion maps to
   concrete evidence (repo path, demo timestamp, evidence page section).

---

### User Story 5 - Export an MP4 recap from our own rendered match (Priority: P3, optional — gated)

Only if every essential release gate in the published 008 report passes: a producer exports the recap of the current match as an
MP4 rendered from TactiStream's own replay with permitted assets only, plus a WebVTT overlay track whose cue times match the recap's
`overlay_track`.

**Why this priority**: Build plan "After essentials"; it strengthens the studio-workflow story but must not risk the essentials.

**Independent Test**: `npm run export:recap -- --base-url http://localhost:8000 --seed 42` produces `exports/recap-*.mp4` and `.vtt`;
the e2e test checks duration and cue alignment.

**Acceptance Scenarios**:

1. **Given** any 008 gate is `fail` or `not_measured`, **When** the builder considers US5, **Then** it is not started (recorded in
   the checklist as "skipped: gate X").
2. **Given** all gates pass, **When** the export runs, **Then** MP4 duration equals the sum of recap replay windows ± 200 ms and
   every VTT cue start/end equals the corresponding `overlay_track` entry ± 40 ms.

### Edge Cases

- Live app down during judging → README shows the backup video link and judge guide explains local run; incident recorded in
  `docs/operations.md`.
- Model quota exhausted during judging → narratives fall back to labelled factual templates; the demo remains usable; judge guide
  explains the fallback label.
- Organizer changes requirements (video length, fields) → organizer instructions win; spec and checklist updated the same day.
- Registration not confirmed by 19 Oct evening → escalate to organizers immediately via the event channel; no other work blocks on it.
- Video exceeds 1:59 after export → cut from beats 0:58–1:13 first (unseen sequence), never the evidence or fixture beats.
- Feature freeze violated by a "small" change → only fixes for blocking defects found in rehearsal are allowed after 24 Oct, each
  with a test.
- Judges on mobile → `/demo` is usable at ≥ 375 px width with the 3D replay degraded to the 2D/events view if WebGL is unavailable
  (005 behaviour); the judge guide recommends a desktop browser.
- `/demo` deep link on the container → served by SPA fallback (007 FR-011).
- Two judges on the same seed → separate sessions; no shared state; model calls bounded per session.

## Requirements *(mandatory)*

### Functional Requirements

**Demo route (US1)**

- **FR-001**: Frontend MUST provide route `/demo` (`frontend/src/routes/DemoPage.tsx`) reading `seed` (default 42, integer 1–99999),
  `scenario` (default `space_creation`; allowed: the 002 scenario names) and optional `variant`, creating a session via
  `POST /api/sessions`, connecting the WebSocket and sending `play` automatically.
- **FR-002**: `/demo` MUST render the normal match experience plus `JudgePanel` with actions: Restart demo (new session, same params),
  Load another sequence (`scenario=press_turnover`, `seed=10500`, `variant=D` — an eval-range seed not in `heldout.yaml` or dev),
  Simulate model timeout and Inject bad claim (004 `POST /api/matches/{id}/fixtures`), Load tracking-gap example
  (`scenario=tracking_gap`, `seed=42`), Open Evidence (`/evidence`). Every action is a labelled button reachable by keyboard; fixture
  actions show a "Fixture active" label until consumed.
- **FR-003**: Invalid query values MUST fall back to defaults with a visible notice; the URL is normalized with `history.replaceState`.
- **FR-004**: `SessionRegistry` MUST cap concurrent sessions (`TACTISTREAM_MAX_SESSIONS`, default 20), evict sessions idle (no
  WebSocket) for `TACTISTREAM_SESSION_IDLE_TTL_S` (default 900 s), and return 503 `{"error":"capacity_reached"}` when full; the
  frontend shows the busy message with the video link.
- **FR-005**: Injected fixtures MUST affect only the session they were posted to and MUST NOT be written to any shared narrative cache.

**Repository and docs (US2)**

- **FR-006**: `README.md` MUST start with: name + tagline "See the move behind the moment.", the pitch line verbatim, live link,
  `/demo?seed=42` link, video link, Synthetic-data statement; then sections Quick start (`make install && make dev`), For judges
  (criteria table), What is live / synthetic / cached / planned, Architecture (link), Multi-agent design (link), Results (link to
  `docs/results.md` and `/evidence`), Limitations, Permitted assets, License, Team.
- **FR-007**: `docs/architecture.md` MUST contain the build-plan Mermaid flowchart edited to show only deployed and used services (from
  `docs/deployment-inventory.json`, 007 `inventory.sh`), the actual model deployment name, model + version and region, the app region,
  the consumer-group split, and a "Planned (not deployed)" list.
- **FR-008**: `docs/agents.md` MUST contain the authority table (Analyst, Verifier, Producer: decisions and tools, output, prohibited
  behaviour), the three prompts verbatim from the code, the handoff payload types with IDs and `trace_id`, the bounded workflow
  (one repair, 8 s deadline, fallback), the output checks, the tool list with as-of enforcement, and the 008 comparison result — narrowed
  wording if `comparison.claim_narrowed` is true.
- **FR-009**: `docs/metrics.md` MUST document every metric kind from 003 (definition, formula, version, units, limitation shown in product),
  the pressure prototype formula, `unavailable` semantics, and the latency measurement method (ack-based upper bound).
- **FR-010**: `docs/limitations.md` MUST list: synthetic data only; controlled-environment results; internal review label (unless expert);
  one replica / one match per session; no video understanding, upload, screen share, forecasting or xG; metric heuristics not official
  statistics; language templates reviewed by the builder (state reviewer for Hindi); every gate that failed or was not measured.
- **FR-011**: `docs/permitted-assets.md` MUST list every third-party asset (fonts, icons, libraries with licenses, 3D/texture assets,
  audio in the video, ffmpeg if US5) with source URL and license; state that teams/players are fictional and no Premier League marks are used.
- **FR-012**: `docs/judge-guide.md` MUST give a 3-minute path: open `/demo?seed=42`, what to watch, Why, Evidence, mode/language/pin, Judge
  tools (what each fixture demonstrates and the expected visible result), Evidence page, recap; how to restart; local run; what to do if busy.
- **FR-013**: `docs/operations.md` (from 007) MUST be finalized with the submission-time inventory, availability log and teardown date.
- **FR-014**: `docs/business.md` MUST name the first buyer (digital football producer preparing tactical segments and short recaps), the
  job to be done, the pilot design (small number of willing producers/editors, same clips with and without the tool, counterbalanced order,
  measures: time to publishable output, correction count, reviewer acceptance), the value model formula verbatim from the build plan with
  variables defined, cost drivers (inference, container, Event Hubs, Fabric capacity, storage, egress) using measured usage from
  `docs/results.md`, pricing hypothesis (per production workspace plus match usage, after pilot), defensible assets, and the sentence
  "No customer validation has been conducted yet."
- **FR-015**: A CI `docs` workflow MUST run a link check over `README.md` and `docs/**/*.md` (external links allowed to be rate-limited
  but not 404), render every Mermaid block, and run `backend/tests/docs/test_docs_claims.py` (banned phrases; architecture-vs-inventory;
  numbers in README/docs/description reference `docs/results.md` values).
- **FR-016**: A fresh-clone verification MUST be performed on 24 Oct in a new Codespace or clean directory and recorded in the checklist.

**Demo video (US3)**

- **FR-017**: `demo-script.md` MUST hold the exact 0:00–1:55 table from the build plan, the shot list, narration lines, the recording
  checklist and the backup-recording rule; the recorded video MUST follow it.
- **FR-018**: The video MUST be < 2 minutes (target 1:55, hard maximum 1:59), 1920×1080, English narration, burned-in or uploaded English
  captions, showing the working deployed app (not mock-ups); the Synthetic badge is visible in match shots.

**Submission (US4)**

- **FR-019**: `submission-checklist.md` MUST track dates, registration, every required field, the five-criteria evidence map, the
  submission description draft, link verification, confirmation reference and the availability log through 10 Nov PT.
- **FR-020**: The final submission description (kept public at `docs/submission-description.md`) MUST explain the synthetic source, the three agent responsibilities, deterministic evidence
  checks, the rendered result, measured limits (numbers from `docs/results.md`), and studio use; it MUST NOT claim official Premier League
  integration, production accuracy, or customer validation.
- **FR-021**: No feature work after 24 Oct (feature freeze); after freeze only rehearsal-blocking fixes with tests, docs, and the
  recording. No infrastructure changes after 26 Oct submission except restoring availability.

**Optional export (US5)**

- **FR-022**: US5 MUST start only if `eval/results/latest/report.json` has all eight gates `pass`; a script
  `backend/src/tactistream/eval/gates_check.py` (`tactistream-eval gates-check`) exits 0 only in that case.
- **FR-023**: If built, export MUST render `/render/recap?match_id=&recap_id=` (own replay + overlays, permitted assets only) with Playwright
  video capture, convert to H.264 MP4 with ffmpeg, write a WebVTT file from `overlay_track`, and save both as
  `exports/{match_id}/{recap_id}.{mp4,vtt}` (optionally uploaded to the `artifacts` Blob container under the same key).
- **FR-024**: Uploaded clip alignment, screen share, forecasting and full video auto-eventing are explicitly excluded and listed as
  "Later" in README and limitations.

### Key Entities

- **Demo session parameters**: seed, scenario, variant; mapped to `POST /api/sessions`.
- **Judge fixture action**: one of `model_timeout`, `bad_claim` (server fixtures) or a session switch (`tracking_gap`, unseen sequence).
- **Docs set**: README + nine docs files + generated `docs/results.md` + `docs/deployment-inventory.json`.
- **Demo video / backup recording**: final < 2 min video; labelled backup.
- **Submission record**: fields, links, confirmation reference, verification timestamps.
- **Recap export** (optional): MP4 + VTT pair derived from a `Recap`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `/demo?seed=42` shows the hero card with zero clicks in 5/5 Playwright runs against the deployed app.
- **SC-002**: A person new to the project, given only the README, reaches the hero card, opens one evidence item and the Evidence page in
  ≤ 3 minutes (one rehearsal on 25 Oct, time recorded).
- **SC-003**: CI `docs` job passes: 0 broken links, all Mermaid blocks render, 0 banned claims, architecture services ⊆ inventory.
- **SC-004**: Fresh-clone local run reaches the hero card on 24 Oct without manual fixes (or fixes are committed and the run repeated).
- **SC-005**: Final video duration 1:50–1:59, 1920×1080, checklist 100% ticked.
- **SC-006**: Submission confirmed on 26 Oct IST (≥ 40 h before close) with all links verified from a logged-out browser on a second device
  and network.
- **SC-007**: Availability log shows a passing check every day from 26 Oct to 10 Nov PT (uptime workflow + manual weekly `/demo` check).
- **SC-008**: Every criterion in the five-criteria table cites at least two concrete evidence items that exist at submission time.

## Assumptions

- Team size ≤ 4 (solo builder assumed); materials in English; the repository is new and public under an OSI license (MIT unless the
  organizer requires otherwise).
- Video hosting follows organizer instructions (default: YouTube unlisted or the platform the form requests).
- 004 provides `POST /api/matches/{id}/fixtures` and a trace view; 005 Why Mode; 006 recap + `POST /api/matches/{id}/recap`; 007 deployed
  app, SPA fallback, inventory, uptime workflow and `docs/operations.md`; 008 the published report and `/evidence`.
- The official rules summary in the build plan (synthetic football-realistic data, new project, public repo, working judging experience,
  video < 2 min, team ≤ 4, English, Best Multi-Agent System category, five equal criteria, permitted assets, access through 10 Nov PT) is
  current; any organizer update overrides it.
