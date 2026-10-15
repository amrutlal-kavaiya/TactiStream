---
description: "Task list for 009 submission"
---

# Tasks: Submission

**Input**: `specs/009-submission/` (spec, plan, demo-script.md, submission-checklist.md)

**Tests**: REQUIRED (constitution V). Code tasks (demo route, session cap, gates check, optional export) are test-first. Docs are
verified by the CI `docs` workflow (link check, Mermaid render, claims test) and a fresh-clone run; media by the recording checklist.

**Format**: `[ID] [P?] [Story] Description` — `[P]` = parallelizable (different files, no unmet dependency).

**Calendar (IST)**: T001 by 19 Oct · Phase 3 (demo route) as early as 21–23 Oct, at the latest 24 Oct · Phase 4 on 24 Oct (feature
freeze at end of day) · Phase 5 on 25 Oct · Phase 6 on 26–27 Oct and availability through 10 Nov PT · Phase 7 only if gated in.

## Phase 0: External deadline (do now)

- [ ] T001 Complete hackathon registration for every team member (≤ 4) before 20 Oct (closes 21 Oct 00:30 IST); save the confirmation and record its reference and date in `specs/009-submission/submission-checklist.md` "Key dates"

---

## Phase 1: Setup

- [ ] T002 [P] Add `LICENSE` (MIT, copyright "TactiStream contributors 2026") unless organizer instructions require another license
- [ ] T003 [P] Create `.github/workflows/docs.yml` (on push/PR touching `README.md`, `docs/**`, `specs/009-submission/**`): job `links` with `lycheeverse/lychee-action@v2` over `README.md docs/**/*.md` (`--accept 200,206,429`, exclude `localhost`, `127.0.0.1`, the live app URL until deployed); job `mermaid` extracting every ```mermaid block from `README.md` and `docs/*.md` and rendering with `npx -p @mermaid-js/mermaid-cli mmdc` (fail on error); job `claims` running `uv run pytest backend/tests/docs`
- [ ] T004 Write failing `backend/tests/docs/test_docs_claims.py`: required files exist (`README.md`, `LICENSE`, `docs/{architecture,agents,metrics,limitations,permitted-assets,judge-guide,operations,business,results}.md`, `docs/deployment-inventory.json`, `docs/submission-description.md`); README contains the pitch line verbatim and links `/demo?seed=42`, `docs/results.md`, `/evidence`; banned-phrase regexes from plan.md produce 0 matches across README, `docs/`, `docs/submission-description.md`; architecture Mermaid services ⊆ inventory (alias table: "Azure Event Hubs" → `Microsoft.EventHub/namespaces`, "Container Apps" → `Microsoft.App/containerApps`, "Blob Storage" → `Microsoft.Storage/storageAccounts`, "Application Insights" → `Microsoft.Insights/components`, "Fabric Eventstream"/"Eventhouse" → inventory key `fabric_items`, "Foundry" → `foundry.deployment`); `p95`/percentage statements outside `results.md`, `metrics.md` and captioned target tables equal values in `eval/results/latest/report.json`; `docs/business.md` contains "No customer validation has been conducted yet."; `docs/limitations.md` mentions every gate whose status is not `pass`

**Checkpoint**: T004 fails (docs not written yet); docs workflow runs.

---

## Phase 3: User Story 1 — One-click judge demo (P1) 🎯

**Goal**: `/demo?seed=42` auto-starts the hero match with Judge tools; sessions are capped and evicted safely.

**Independent Test**: `frontend/tests/e2e/demo-route.spec.ts` passes locally and 5/5 against the deployed URL.

- [ ] T005 [P] [US1] Write failing `backend/tests/unit/test_session_registry_cap.py` (FakeClock): with `max_sessions=2`, a third `create` raises `CapacityReached` while both are connected; after one session has no WebSocket for `idle_ttl_s` (900 s) `create` evicts it and succeeds; eviction cancels its replayer/consumer tasks and removes its evidence index; `touch` on WS activity resets idle time; `POST /api/sessions` at capacity → 503 `{"error":"capacity_reached","detail":"The live demo is busy — retry in a minute"}`; injected fixtures on session A do not affect session B (FR-005)
- [ ] T006 [US1] Implement `SessionRegistry` cap, idle eviction background task (every 60 s, started in `create_app` lifespan) and `CapacityReached` in `backend/src/tactistream/api/session.py`, the 503 mapping in `api/routes_sessions.py`, `touch` calls in `api/ws.py`, and `Settings.max_sessions` / `session_idle_ttl_s` in `settings.py` (+ names in `.env.example`); run T005 → green
- [ ] T007 [P] [US1] Write failing `frontend/tests/unit/demoParams.test.ts`: `""` → `{seed: 42, scenario: "space_creation"}`; `"?seed=10500&scenario=press_turnover&variant=D"` parsed; `seed=abc`, `seed=0`, `seed=100000`, unknown scenario, `variant=Z` → defaults for the bad field plus a `notice` string; extra params ignored
- [ ] T008 [US1] Implement `frontend/src/routes/demoParams.ts` (`parseDemoParams`, `DEMO_DEFAULTS`, `UNSEEN_SEQUENCE = {scenario: "press_turnover", seed: 10500, variant: "D"}`, `TRACKING_GAP = {scenario: "tracking_gap", seed: 42}`); run T007 → green
- [ ] T009 [P] [US1] Write failing `frontend/tests/unit/JudgePanel.test.tsx`: renders a labelled region "Judge tools" with six buttons (Restart demo, Load another sequence, Simulate model timeout, Inject bad claim, Load tracking-gap example, Open Evidence) reachable by Tab in that order; fixture buttons call `injectFixture(matchId, "model_timeout"|"bad_claim")` and show "Fixture active" until `onFixtureConsumed`; sequence buttons call `onNavigate` with the right params; panel collapses/expands with `aria-expanded`
- [ ] T010 [US1] Implement `frontend/src/components/JudgePanel.tsx` and `injectFixture(matchId, inject)` in `frontend/src/api/client.ts` (`POST /api/matches/{id}/fixtures`); run T009 → green
- [ ] T011 [P] [US1] Write failing `frontend/tests/unit/DemoPage.test.tsx` (mock client + socket): on mount calls `createSession({scenario, seed, variant})`, connects, sends `play` without user action; invalid params show the notice and normalize the URL via `history.replaceState`; Restart closes the socket and creates a new session with the same params; 503 `capacity_reached` renders BusyNotice with the `VITE_DEMO_VIDEO_URL` link
- [ ] T012 [US1] Implement `frontend/src/routes/DemoPage.tsx` (reuses the main match layout, adds `JudgePanel`, `BusyNotice`) and register `/demo` in `frontend/src/routes/router.tsx`; add `VITE_DEMO_VIDEO_URL` to `frontend/.env.example`; run T011 → green
- [ ] T013 [US1] Write and pass `frontend/tests/e2e/demo-route.spec.ts`: open `/demo?seed=42` with no clicks → Synthetic badge, playback running, hero card ("Space opened before the shot" or labelled fallback) within 15 s of page load; Restart demo → card disappears then reappears; Simulate model timeout → next narrative shows the fallback label while event rows keep appearing; Inject bad claim → trace view lists a rejected/revised claim; Load tracking-gap example → "Insufficient tracking for this explanation"; Open Evidence → `/evidence`; keyboard-only pass through Judge tools
- [ ] T014 [US1] Deploy and run `BASE_URL=$APP_URL npx playwright test tests/e2e/demo-route.spec.ts --repeat-each=5` (SC-001); record the result in `submission-checklist.md`

**Checkpoint**: judge route works on the deployed app.

---

## Phase 4: User Story 2 — Judge-first repository and docs (P1) — 24 Oct

**Goal**: README + docs set that are accurate, linked and machine-checked; fresh clone runs.

**Independent Test**: CI `docs` workflow green (T004 passes); fresh-clone run reaches the hero card.

- [ ] T015 [US2] Run `infra/scripts/inventory.sh rg-tactistream-prod > docs/deployment-inventory.json` (007) and add Fabric items (`fabric_items: [{type: "Eventstream", name}, {type: "Eventhouse", name}]`) only if they are running and receiving data today
- [ ] T016 [P] [US2] Write `docs/architecture.md`: build-plan Mermaid flowchart with only inventory-backed nodes (Fabric nodes removed if absent — stop rule), consumer groups `live-state` / `fabric`, fast path vs narrative path, actual model deployment name + model/version + region, app region, one-replica statement, "Planned (not deployed)" list, link to `docs/operations.md`
- [ ] T017 [P] [US2] Write `docs/agents.md`: authority table (build-plan wording adjusted to the implementation), prompts copied verbatim from 004 prompt files (with file paths), handoff types (`AnalystOutput`, `VerifierOutput`, `ProducerOutput`) with IDs + `trace_id`, bounded workflow diagram (one repair, 8 s deadline, fallback), output checks list, tools with as-of enforcement (incl. `get_history` if deployed), shared state contents, and the 008 comparison summary — narrowed wording when `comparison.claim_narrowed` (see 008 T059)
- [ ] T018 [P] [US2] Write `docs/metrics.md` from 003: each metric kind (definition, formula, `definition_version`, units, inputs, `unavailable` conditions, limitation text shown in product), pressure prototype formula `P = (100 / 3) × Σ exp(−dᵢ / 2.5)` with its caveats, pitch convention, and the latency method (ack-based upper bound, 001 R10)
- [ ] T019 [P] [US2] Write `docs/limitations.md` per FR-010, generated list of non-passing gates copied from `eval/results/latest/report.json`, Hindi review statement (who reviewed), and "Later" items (uploaded clip alignment, screen share, forecasting, full video auto-eventing)
- [ ] T020 [P] [US2] Write `docs/permitted-assets.md`: every npm/PyPI dependency with license (generated via `npx license-checker --summary` and `uv pip list` + `pip-licenses`), fonts (incl. Devanagari font) with license, icons, any 3D textures/models, video music/voice (own voice; no third-party music unless licensed), statement on fictional teams/players and no Premier League marks
- [ ] T021 [P] [US2] Write `docs/judge-guide.md` per FR-012 with exact button names from the UI, expected visible outcomes per Judge tool, restart instructions, local run, busy/backup video guidance
- [ ] T022 [P] [US2] Finalize `docs/operations.md` (from 007): submission-time inventory link, uptime workflow, availability log pointer (`submission-checklist.md`), on-call steps (rollback command, quota fallback behaviour), teardown not before 12 Nov 2026
- [ ] T023 [P] [US2] Write `docs/business.md` per FR-014 (first buyer, job, pilot design with counterbalanced order and the three measures, value model formula verbatim with variable definitions, cost drivers using measured usage from `docs/results.md`, pricing hypothesis, defensible assets, "No customer validation has been conducted yet.")
- [ ] T024 [US2] Rewrite `README.md` per FR-006 (first screen: name, tagline, pitch line, live link, `/demo?seed=42`, video link placeholder, Synthetic statement; "For judges" five-criteria table from `submission-checklist.md`; "What is live / synthetic / cached / planned" table; quick start `make install && make dev`; links to all docs, `/evidence`, `docs/results.md`; "If the live demo is busy" with backup video link)
- [ ] T025 [US2] Make CI `docs` workflow green: fix broken links, Mermaid errors and any T004 failure by correcting the docs (never by loosening the test); run T004 → green (SC-003)
- [ ] T026 [US2] UI polish pass limited to the rehearsal list (copy, focus rings, empty/loading states, contrast ≥ 4.5:1, Hindi font fallback) — each change with an updated unit/e2e assertion; full CI green
- [ ] T027 [US2] Fresh-clone verification: new Codespace (or `git clone` into `/tmp/ts-fresh`), only README instructions, `make install && make dev`, open `http://localhost:5173/demo?seed=42`, run `npm run e2e -- tests/e2e/demo-route.spec.ts`; fix gaps, repeat until clean; record date and result in `submission-checklist.md` (SC-004)
- [ ] T028 [US2] Feature freeze: tag `v1.0.0-rc1` on `main` at end of 24 Oct; from now only blocking fixes with tests (FR-021)

**Checkpoint**: repository is judge-ready; freeze in effect.

---

## Phase 5: User Story 3 — 115-second demo video (P1) — 25 Oct

**Goal**: final video per `demo-script.md`, captions, labelled backup.

**Independent Test**: recording checklist complete; `ffprobe` duration 110–119 s at 1920×1080.

- [ ] T029 [US3] Fresh-session rehearsal per `demo-script.md` "Rehearsal": new browser profile, README → `/demo?seed=42` → judge-guide path with a timer (SC-002 ≤ 3 min); file blocker issues and fix only blockers (with tests)
- [ ] T030 [P] [US3] Write captions `docs/media/demo.srt` from the narration in `demo-script.md` with the planned timings
- [ ] T031 [US3] Record the final take following the shot list and recording checklist; edit only cuts between beats (no fabricated screens); export H.264 MP4 1920×1080
- [ ] T032 [US3] Verify: `ffprobe -v error -show_entries format=duration:stream=width,height -of json demo.mp4` → duration 110–119 s, 1920×1080; frame-scan for secrets (watch at 1× with the checklist); re-sync captions; tick every checklist item in `demo-script.md` (SC-005)
- [ ] T033 [US3] Record the backup take labelled "Backup recording — TactiStream deployed app, recorded 25 Oct 2026" (title + first frame)
- [ ] T034 [US3] Upload both videos per organizer instructions (default YouTube unlisted, captions attached); verify playback logged out; put links in `README.md`, `docs/judge-guide.md`, `VITE_DEMO_VIDEO_URL` (redeploy), and `submission-checklist.md`

**Checkpoint**: video ready; links live.

---

## Phase 6: User Story 4 — Submit, verify, stay available (P1) — 26 Oct → 10 Nov PT

**Goal**: confirmed submission with verified links and a daily availability record.

**Independent Test**: checklist fully ticked; uptime workflow green daily.

- [ ] T035 [US4] Write `docs/submission-description.md` from the draft in `submission-checklist.md`, filling every `{…}` from `docs/results.md` (same `report_id` as `/evidence`), applying narrowed multi-agent wording if required, dropping the Fabric sentence if Fabric is not in the inventory; run T004 (claims test) → green
- [ ] T036 [US4] Final pre-submit check: `main` CI green, deploy workflow green, `tactistream-smoke deployed` pass, T014 e2e 5/5 pass, `/evidence` `report_id` equals `docs/results.md`; tag `v1.0.0`
- [ ] T037 [US4] Submit on 26 Oct through the official channel with every field in `submission-checklist.md` "Submission fields" (category Best Multi-Agent System; team ≤ 4; English); save confirmation and record reference + timestamp (SC-006)
- [ ] T038 [US4] Logged-out verification on a second device and network for every link (repo, `/demo?seed=42`, video, `/evidence`); record results in the checklist "Link verification" table; fix and re-verify any failure the same day
- [ ] T039 [US4] 27 Oct buffer: re-run T036 checks, confirm uptime workflow schedule active, confirm budget alert and Foundry quota headroom for judging traffic, confirm Fabric capacity end date ≥ 11 Nov (or stop-rule note in `docs/operations.md`); no feature changes
- [ ] T040 [US4] From 26 Oct to 10 Nov PT: record daily uptime workflow result and a manual `/demo?seed=42` check every 3 days and on 10 Nov in the checklist "Availability log"; any incident → fix, log in `docs/operations.md` incident table (SC-007)

**Checkpoint**: submission complete and monitored.

---

## Phase 7: User Story 5 — Optional MP4 recap export (P3, gated)

**Goal**: own-rendered recap MP4 + WebVTT with matching timestamps. **Do not start unless T042 exits 0.**

- [ ] T041 [P] [US5] Write failing `backend/tests/unit/eval/test_gates_check.py`: report with 8 `pass` gates → 0; any `fail` or `not_measured` → 1 and prints the gate ids; missing/invalid report → 2
- [ ] T042 [US5] Implement `backend/src/tactistream/eval/gates_check.py` and CLI `tactistream-eval gates-check`; run T041 → green; run it on the published report and record "started" or "skipped (gate: …)" in `submission-checklist.md` — if skipped, stop Phase 7 here
- [ ] T043 [P] [US5] Write failing `frontend/tests/unit/RecapRenderPage.test.tsx`: given a `Recap` with 2 items, the page plays windows back-to-back on a fake clock, shows overlay text exactly between each cue's `start_ms` and `end_ms`, and sets `window.__recapDone = true` at the sum of window durations
- [ ] T044 [US5] Implement `frontend/src/routes/RecapRenderPage.tsx` at `/render/recap?match_id=&recap_id=` (fetches recap via 006 API, reuses replay scene, hides chrome) and register the route; run T043 → green
- [ ] T045 [US5] Write failing `frontend/tests/e2e/recap-export.spec.ts` (requires ffmpeg on PATH; skipped with reason otherwise): run `node scripts/export-recap.mjs --base-url http://localhost:8000 --seed 42 --out exports/`; assert MP4 exists, `ffprobe` duration = Σ replay windows ± 200 ms, 1920×1080; VTT cue start/end equal `overlay_track` ± 40 ms
- [ ] T046 [US5] Implement `frontend/scripts/export-recap.mjs` (create session seed 42, play to end, `POST /api/matches/{id}/recap`, Playwright `recordVideo` of `/render/recap`, ffmpeg WebM → MP4, VTT writer) and `npm run export:recap`; run T045 → green; add ffmpeg and its license to `docs/permitted-assets.md`; mention the export (with "rendered from TactiStream's own synthetic replay") in README and judge guide

---

## Phase 7b: User Story 6 — Presenter page (P1, pulled forward 15 Oct, user request)

**Goal**: `/presenter` to rehearse, check, upload/link and publish the demo media; judges watch via header button and `/watch`.

**Independent Test**: `cd frontend && npx playwright test tests/e2e/presenter.spec.ts`.

- [ ] T048 [P] [US6] Write failing `backend/tests/unit/test_media_store.py`: `LocalMediaStore` put/get/delete round-trip, streamed write (chunks) with sha256 and byte count, size cap raises `MediaTooLarge` and leaves no partial file, `state.json` persists slots + published across new instances; `BlobMediaStore` same contract against an injected fake blob client (parametrized shared contract)
- [ ] T049 [US6] Implement `backend/src/tactistream/media/{__init__,store,models}.py` (`MediaSlot` = main|backup|captions, `MediaRecord`, `MediaState`, `MediaStore` protocol, `LocalMediaStore`, `BlobMediaStore`, `build_media_store(settings)`); add `presenter_key: SecretStr | None` (env `TACTISTREAM_PRESENTER_KEY`) to Settings and the name to `.env.example`; gitignore `data/media/`; run T048 → green
- [ ] T050 [P] [US6] Write failing `backend/tests/unit/test_presenter_api.py`: key unset → every `/api/presenter/*` 404; wrong/missing key → 401 `presenter_key_invalid`; upload `main` mp4 stream → 200 record with sha256/bytes; non-mp4 content type → 422 `unsupported_media`; > cap → 413 `media_too_large`; captions `.srt` saved as VTT; `{"url":"http://…"}` → 422 (https only); publish toggle; `GET /api/presenter/state`; `GET /api/config` hides media until published; `GET /media/main` with `Range: bytes=0-99` → 206 with 100 bytes and `Content-Range`; `/media/x` unknown → 404; key never appears in logs (caplog)
- [ ] T051 [US6] Implement `backend/src/tactistream/api/routes_presenter.py` (presenter routes, `GET /api/config`, `GET /media/{slot}` with Range) and wire into `create_app` (media store in lifespan; `/media` added to SPA reserved prefixes); run T050 → green
- [ ] T052 [P] [US6] Write failing `frontend/tests/unit/{router,PresenterPage,WatchDemo}.test.tsx`: path router renders App at `/`, PresenterPage at `/presenter`, WatchPage at `/watch`; PresenterPage disabled notice on 404 state; key prompt stores in sessionStorage only; selecting a file shows duration/resolution (mock `HTMLVideoElement` metadata) and warns outside 110–119 s or ≠ 1920×1080; checklist ticks persist; rehearsal timer highlights the beat for elapsed time; Publish switch calls API; header "Watch demo video" only when config published; dialog has `<video>` + `<track kind="captions" default>`; `/watch` shows not-published message
- [ ] T053 [US6] Implement `frontend/src/routes/{router.tsx,PresenterPage.tsx,WatchPage.tsx}`, `frontend/src/components/{WatchDemoButton,DemoVideoPlayer,MediaSlotCard,RehearsalTimer}.tsx`, `frontend/src/presenter/{beats.ts,api.ts}` (upload with progress via `XMLHttpRequest`), `frontend/src/api/config.ts`; mount router in `main.tsx`; i18n strings (en; hi draft); run T052 → green
- [ ] T054 [US6] Write `frontend/tests/e2e/presenter.spec.ts` (webServer env sets `TACTISTREAM_PRESENTER_KEY=e2e-key`, temp `TACTISTREAM_DATA_DIR`): wrong key refused; right key → upload `tests/e2e/fixtures/sample.mp4` (2 s, generated by `scripts/make-sample-video.mjs` with Playwright `recordVideo`→ffmpeg if available, else a committed ≤ 200 KB sample) and `sample.vtt` → publish → `/` header button → dialog video `readyState ≥ 2` and `textTracks[0].mode == "showing"`; `/watch` shows player + backup link; unpublish hides button; axe scan of `/presenter` and `/watch` (dark + light) zero serious/critical; run `--repeat-each=3` (SC-009)
- [ ] T055 [US6] Docs: `docs/presenter.md` (set the secret: `az containerapp secret set … presenter-key=…` + env `TACTISTREAM_PRESENTER_KEY=secretref:presenter-key`; open `/presenter`; recording specs; upload or YouTube link; publish; `/watch` is the one link for README/judge guide/checklist); add the secret + env var (empty → disabled) to `infra/modules/containerapps.bicep` behind a `@secure() param presenterKey string = ''`; Bicep build 0 warnings and infra tests green; README "Demo video: /watch" placeholder line

**Checkpoint**: presenter flow green end to end locally; deployed use documented.

---

## Phase 8: Polish

- [ ] T047 Update `specs/README.md` feature table row 009: mark exit conditions (24 Oct freeze, 25 Oct video, 26 Oct submitted, 27 Oct buffer) with dates and the submission confirmation date; note whether US5 was built or skipped

---

## Dependencies & Execution Order

- T001 is independent and urgent (≤ 19 Oct).
- Setup (T002–T004) → US1 (T005–T014; can start once 004 fixtures + 008 router exist) → US2 (T015–T028; T016/T017/T019/T024 need the published 008 report and 007 inventory) → US3 (T029–T034; needs US1 deployed + US2 docs) → US4 (T035–T040) → optional US5 (T041–T046, only if gated in) → Polish (T047).
- Within US2, T016–T023 are parallel; T024 (README) after them; T025 after all docs; T027 after T025.
- External: 004 fixtures endpoint + trace view (T013), 005 replay (T013, T044), 006 recap API (T044–T046), 007 deploy/inventory/uptime/operations (T014, T015, T022, T040), 008 report + `/evidence` + router (T012, T017, T019, T035).

## Parallel Example

```text
21–23 Oct (spare slots): T005–T012 (session cap, demo route, panel)
24 Oct morning:          T016 || T017 || T018 || T019 || T020 || T021 || T022 || T023
24 Oct afternoon:        T024 → T025 → T026 → T027 → T028 (freeze)
25 Oct:                  T029 → T030 || T031 → T032 → T033 → T034
26 Oct:                  T035 → T036 → T037 → T038
```

## Implementation Strategy

Ship the judge route first (it is also the recording surface), then the docs that judges read, then the video, then submit with
two days of buffer. If anything slips, cut in this order: optional export (US5) → UI polish beyond blockers → second-reviewer
items in docs; never cut logged-out link verification or the availability log.
