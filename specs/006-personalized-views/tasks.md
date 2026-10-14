---
description: "Task list for 006 personalized views"
---

# Tasks: Personalized Views — Fan/Analyst, English/Hindi, player pinning, automated recap

**Input**: `specs/006-personalized-views/` (spec, plan, data-model, contracts/recap-api.md, contracts/ws-ranking.md,
glossary-plan.md, quickstart)

**Prerequisites**: 001–005 merged (InsightBundle with 4 variants, `ProducerOutput`, `explain_moment`, scripted model
client, `rank()`, `ReplayView`, `Timeline`, `Annotations`, `replay_window`).

**Tests**: REQUIRED (constitution V). Each implementation task is preceded by a test task that must fail first for the
stated reason.

**Format**: `[ID] [P?] [Story] Description` — `[P]` = parallelizable (different files, no unmet dependency).

## Phase 1: Setup

- [ ] T001 [P] Add dev dependency `hypothesis` and console script `tactistream-catalog = tactistream.narrative.preview:app` to `backend/pyproject.toml`; refresh `backend/uv.lock`
- [ ] T002 [P] Add `@fontsource/noto-sans-devanagari` (exact pin) to `frontend/package.json`; import weights 400/600 in `frontend/src/main.tsx`; set font stack `"Inter", "Noto Sans Devanagari", system-ui, sans-serif` and `:lang(hi) { line-height: 1.6 }` in `frontend/src/styles/tokens.css`
- [ ] T003 [P] Add Noto Sans Devanagari (SIL OFL 1.1, source URL, version, "self-hosted UI font for Hindi") to `docs/permitted-assets.md`

**Checkpoint**: `make install && make test` green.

---

## Phase 2: Foundational (blocks all stories)

### Contracts

- [ ] T004 Write failing rows in `backend/tests/contract/test_examples.py`: `ws_ranking.json` validates as `ServerMessage` (type `ranking`) and round-trips through the Pydantic model; negatives rejected by schema and model: entry with `pinned_involvement="maybe"`, `rank=0`, extra field; `ViewerPrefs.model_validate({"mode":"fan","language":"hi","pinned_player_id":null})` ok, `{"mode":"coach"}` → `ValidationError`
- [ ] T005 Extend `contracts/schemas/ws_message.schema.json` per `specs/006-personalized-views/contracts/ws-ranking.md` (`"ranking"` in `ServerMessage.type`, `$defs/Ranking`, payload `if/then`); add `contracts/examples/ws_ranking.json`; note the minor bump in `contracts/README.md`
- [ ] T006 Implement `RankingEntry`, `RankingPayload` and the `ranking` server message in `backend/src/tactistream/contracts/ws.py`, and `ViewerPrefs` in `backend/src/tactistream/contracts/prefs.py`; export from `contracts/__init__.py`. Run T004 → green
- [ ] T007 Run `npm run contracts:gen`; commit regenerated `frontend/src/contracts/generated.ts` (`make contracts` clean)

### Shared primitives

- [ ] T008 [P] Write failing `backend/tests/unit/test_consistency.py::test_extract_*`: `extract_numbers("Blue 9's run … 13.1 m forward", names)` → `["13.1"]` (the 9 belongs to "Blue 9"); hi "ब्लू 9 … 1.9 मीटर से 5.3 मीटर" → `["1.9","5.3"]`; negative and integer values; `extract_player_ids` maps "Blue 9"/"ब्लू 9"/"Amber 4"/"एम्बर 4" to `blue-09`/`amber-04` in order of appearance, longest name first ("Blue 11" never matched as "Blue 1")
- [ ] T009 [P] Implement `extract_numbers` and `extract_player_ids` in `backend/src/tactistream/narrative/consistency.py`. Run T008 → green
- [ ] T010 [P] Write failing `frontend/tests/unit/prefsStorage.test.ts` and `frontend/tests/unit/matchStore.prefs.test.ts`: `loadPrefs()` defaults `{mode:"fan", language:"en", pinnedPlayerId:null}`; corrupt JSON → defaults; `savePrefs` writes key `tactistream.prefs.v1`; `setMode`, `setLanguage`, `pin(id|null)` update store and persist; `applyMessage(ranking)` replaces `ranking`; `rankedMoments()` follows `ranking.entries` order when present, else `rank_score` desc then `moment_id`
- [ ] T011 [P] Implement `frontend/src/store/prefsStorage.ts` and extend `frontend/src/store/matchStore.ts` (`prefs.pinnedPlayerId`, `ranking`, `setMode`, `setLanguage`, `pin`, `rankedMoments`). Run T010 → green
- [ ] T012 [P] Write failing `frontend/tests/unit/socket.prefs.test.ts` (mock WebSocket): `sendPrefs(p)` sends `{"type":"prefs","mode","language","pinned_player_id"}`; after every received `snapshot` (initial and resume) the last prefs are re-sent once; a `ranking` message does not change `lastSeq`
- [ ] T013 [P] Implement `sendPrefs` and post-snapshot resend in `frontend/src/api/socket.ts`; subscribe the store so every prefs change calls `sendPrefs`. Run T012 → green

**Checkpoint**: contracts, prefs plumbing and text extraction ready.

---

## Phase 3: User Story 1 — Fan and Analyst see the same facts at different depth (P1) 🎯 MVP

**Goal**: identical claims/evidence across variants; different depth; instant switching.

**Independent Test**: `test_consistency.py`, `test_bundle_release_consistency.py`, `personalize.spec.ts --grep mode`.

### Backend

- [ ] T014 [US1] Write failing `backend/tests/unit/test_consistency.py::test_unify_*` and `::test_bundle_*`: fan `["clm-0045-2"]` + analyst `["clm-0045-1","clm-0045-2"]` → both `["clm-0045-1","clm-0045-2"]`; analyst annotations become the union, fan unchanged; hero bundle from `contracts/examples` expanded to 4 variants passes; failures with codes: one variant missing → `variant_missing`; hi body "5.4" vs en "5.3" → `numbers_differ_language`; fan shows "Blue 7" absent from analyst → `players_not_subset_mode`; fan has number analyst lacks → `numbers_not_subset_mode`; differing `evidence_ids` → `evidence_differ`; differing `claim_status` → `status_differ`; fan annotations ⊄ analyst → `annotations_not_subset`; "५.३" anywhere → `devanagari_digit`
- [ ] T015 [US1] Implement `unify_mode_plans` and `check_bundle_consistency` in `backend/src/tactistream/narrative/consistency.py`. Run T014 → green
- [ ] T016 [US1] Write failing `backend/tests/integration/test_bundle_release_consistency.py` (scripted model client, FakeClock): scripted Producer returns fan with 1 claim, analyst with 2 → released `insight` bundle has 4 variants each with both claim IDs; a monkeypatched renderer that alters one hi number → no `insight` message, `narrative_status {stage:"fallback", fallback_reason:"output_check_failed"}`, plain event card still present; consistency failures counted in diagnostics
- [ ] T017 [US1] Call `unify_mode_plans` before rendering and `check_bundle_consistency` after per-variant `check_packet` in `backend/src/tactistream/agents/workflow.py` (fallback path also passes the check). Run T016 → green
- [ ] T018 [US1] Write failing `backend/tests/unit/test_mode_templates.py` then adjust fan/analyst template pairs in `backend/src/tactistream/narrative/catalog/en.json`: for hero, press and switch slot values, every key's fan rendering has numbers ⊆ analyst numbers and ≤ analyst count; analyst renderings of `interp.*` include every metric value referenced by the claim's metric slots

### Frontend

- [ ] T019 [P] [US1] Write failing `frontend/tests/unit/TopBar.prefs.test.tsx`: radio groups "Fan/Analyst" and "EN/हिं" (arrow keys move selection); selecting calls `setMode`/`setLanguage`; `fetch` spy never called; labels localized
- [ ] T020 [P] [US1] Implement the mode and language switches in `frontend/src/components/TopBar.tsx`. Run T019 → green
- [ ] T021 [P] [US1] Write failing `frontend/tests/unit/InsightCard.modes.test.tsx` with a 4-variant bundle: fan shows title + body, Why and Evidence buttons, no evidence chips, no window; analyst shows window `00:36.0–00:46.5`, evidence chips, claim-status label; both expose identical `data-claim-ids` and `data-evidence-ids`; switching mode re-renders without fetching
- [ ] T022 [P] [US1] Extend `frontend/src/components/InsightCard.tsx` for mode-specific detail and the `data-*` attributes. Run T021 → green
- [ ] T023 [P] [US1] Write failing `frontend/tests/unit/EvidenceDrawer.modes.test.tsx`: analyst shows tabs Evidence / Definitions / Agent trace and renders `AgentTrace` with the packet `trace_id`; fan shows plain summaries ("Measured fact", "Interpretation") with no component tables, no Agent trace, and a "Show analyst details" button that calls `setMode("analyst")`
- [ ] T024 [P] [US1] Extend `frontend/src/components/EvidenceDrawer.tsx` with mode-specific layouts and the `AgentTrace` tab (`frontend/src/components/AgentTrace.tsx` from 004). Run T023 → green
- [ ] T025 [P] [US1] Write failing `frontend/tests/unit/Annotations.modes.test.tsx` (test-renderer): `detail="fan"` draws only fan `render.annotations`, no numeric label text, one pulse animation on the first highlight (none under reduced motion); `detail="analyst"` draws analyst annotations, channel label `"1.9 m → 5.3 m"`, path time ticks every 1 s
- [ ] T026 [P] [US1] Add the `detail` prop to `frontend/src/scene/Annotations.tsx` and pass `prefs.mode` and the active variant's annotations from `frontend/src/components/ReplayView.tsx`. Run T025 → green
- [ ] T027 [US1] Write `frontend/tests/e2e/personalize.spec.ts` (mode part): hero seed with scripted agents; toggle Fan↔Analyst 20×, measuring click → card text change with a `MutationObserver`; assert p95 < 100 ms, card `data-claim-ids`/`data-evidence-ids` identical in both modes, and `page.on("request")` records 0 HTTP requests during toggling (SC-004, SC-005)

**Checkpoint**: Fan/Analyst demonstrable; facts provably identical.

---

## Phase 4: User Story 2 — English and Hindi preserve every number and identity (P1)

**Goal**: reviewed Hindi with machine-checked preservation and glossary consistency.

**Independent Test**: `test_catalog_parity.py`, `test_glossary_consistency.py`, `test_variant_property.py`, `i18n.test.ts`, `personalize.spec.ts --grep language`.

- [ ] T028 [US2] Write `docs/glossary-hi.md` from `specs/006-personalized-views/glossary-plan.md` (header with review status "internal review — pending", table columns `en | hi | context | rationale | rejected`, all FR-009 terms, reference sentences, "Open issues" section)
- [ ] T029 [P] [US2] Write failing `backend/tests/unit/test_catalog_parity.py` (extends 004's catalog test; `_meta` is excluded from key comparisons): en/hi key sets identical and equal to `spec.json` keys; per key both `fan` and `analyst` exist; placeholder name sets identical per key/mode; no literal digits outside placeholders in any template; no Devanagari digits (U+0966–U+096F) anywhere in `hi.json`; `_meta.review.status ∈ {internal_review, native_review, expert_review}` with `reviewer` and ISO `date`; keys `recap.summary.general|pinned|pinned_off_ball|pinned_none`, `status.insufficient_tracking`, `label.*` present
- [ ] T030 [P] [US2] Write failing `backend/tests/unit/test_glossary_consistency.py`: parse the `docs/glossary-hi.md` table; for each row every en template containing the en term (word boundary, case-insensitive) has its hi counterpart containing the hi term; no hi template contains a term from the `rejected` column; hi `interp.*` templates contain "मदद" whenever en contains "helped"
- [ ] T031 [P] [US2] Write failing `backend/tests/unit/test_variant_property.py` (Hypothesis, `max_examples=200`, `derandomize=True`, parametrized per catalog key so each template gets ≥ 200 slot sets): for every catalog key (fact.*, interp.*, title.*, status.*, recap.summary.*) and generated slot sets (roster players, metric values with per-slot precision, counts 0–8), render fan/analyst × en/hi; assert `Counter(numbers)` and `Counter(player_ids)` equal across languages per mode, fan ⊆ analyst per language, shared values identically formatted, and `RenderedText.numbers/player_ids` equal what `extract_numbers`/`extract_player_ids` find in the text (SC-001)
- [ ] T032 [US2] Revise `backend/src/tactistream/narrative/catalog/en.json` and `hi.json` and add the new keys' metadata to `spec.json` (004 catalog format) (glossary terms, hedged causality, `recap.summary.*` fan/analyst templates, `_meta`) until T029–T031 pass
- [ ] T033 [US2] Write failing `backend/tests/unit/test_catalog_cli.py` then implement `backend/src/tactistream/narrative/preview.py` (typer: `lint` runs parity/digit/glossary checks and exits 1 on violations; `preview --language --scenario --seed` renders every released bundle and recap summary for a simulated scenario)
- [ ] T034 [US2] Internal review session: run `uv run tactistream-catalog preview --language hi` for `space_creation`, `press_turnover`, `switch_escape` seed 42; fix wording; record reviewer initials/date as `internal_review` in `docs/glossary-hi.md` and both catalogs' `_meta.review` (use `native_review`/`expert_review` only if a named reviewer signs off)
- [ ] T035 [P] [US2] Write failing `frontend/tests/unit/i18n.test.ts`: `hi` is typed `Record<keyof typeof en, string>` and has every runtime key of `en`; no value contains Devanagari digits; `useT` returns hi strings immediately after `setLanguage("hi")`; `document.documentElement.lang` becomes `hi`; narrative containers render with `lang="hi"`
- [ ] T036 [P] [US2] Update `frontend/src/i18n/hi.ts` with reviewed chrome strings (glossary terms), and `frontend/src/i18n/useT.ts` to sync `<html lang>`; add `lang` attributes in `InsightCard.tsx`, `EvidenceDrawer.tsx`, `RecapPanel.tsx` text containers. Run T035 → green
- [ ] T037 [US2] Extend `frontend/tests/e2e/personalize.spec.ts` (language part): switch EN→HI and back on the hero card in both modes; numbers extracted from the card are identical multisets; "Blue 9" ↔ "ब्लू 9"; `html[lang=hi]`; computed `font-family` of the card body includes "Noto Sans Devanagari"; 0 HTTP requests during switching
- [ ] T038 [US2] 21 Oct stop-rule check: run `uv run tactistream-catalog lint`; for any template listed under "Open issues" in `docs/glossary-hi.md`, remove it from both catalogs' active set and map its claims to the reviewed factual template (test in `test_catalog_parity.py` that no active key is listed as open); record the outcome in the PR

**Checkpoint**: US1 + US2 = demo segment 0:43–0:58 minus pinning.

---

## Phase 5: User Story 3 — Pin a player and see the stories re-ranked (P2)

**Goal**: per-connection pinned ranking that changes the timeline.

**Independent Test**: `test_ranking_pinned.py`, `test_ws_prefs.py`, `PlayerFocus.test.tsx`, `Timeline.ranking.test.tsx`, `personalize.spec.ts --grep pin`.

- [ ] T039 [P] [US3] Write failing `backend/tests/unit/test_ranking_pinned.py` with a fake `EvidenceLookup`: `pinned_involvement` → `direct` when player is `player_id` or `recipient_id` of an event inside the window (not outside); `off_ball` when only a subject of an `ok` `off_ball_run` or `defender_follow` metric listed in `moment.metric_ids`; `none` when the metric is `unavailable` or not listed; direct beats off_ball; `rank(moments, "blue-09", lookup=…)` puts involved moments first, then `−rank_score`, then `moment_id`; without pin order equals 003 default; pinned call without lookup → `ValueError`; `rank_for_viewer` ranks 1..n with involvement `none` for all when unpinned; deterministic across shuffled input
- [ ] T040 [US3] Implement `Involvement`, `EvidenceLookup`, `RankedMoment`, `pinned_involvement`, pinned branch of `rank`, and `rank_for_viewer` in `backend/src/tactistream/moments/ranking.py`; implement `MatchSession.lookup()` in `backend/src/tactistream/api/session.py`. Run T039 → green
- [ ] T041 [US3] Write failing `backend/tests/integration/test_ws_prefs.py` (two WS clients, `demo_match` seed 42, scripted agents, `seek` to the end): client A sends `prefs` with `blue-09` → within 500 ms A receives `ranking` whose entry 1 is the `space_creation` moment with `off_ball` and differs from A's unpinned entry 1 (SC-002 ranking part); B receives no ranking change; the `seq` of the ranking equals the head seq and the next broadcast seq is head + 1; after a new `moment` broadcast A receives an updated ranking; `pinned_player_id="blue-77"` → `error unknown_player` and ranking with `pinned_player_id=null`; on resume A re-sends prefs and receives a ranking after the snapshot; scripted model client call count unchanged by prefs messages
- [ ] T042 [US3] Implement `ConnectionPrefs`, `set_prefs`, `send_to` (head seq, not logged) and `send_rankings` in `backend/src/tactistream/api/ws_hub.py`; handle `PrefsMsg` (roster validation) in `backend/src/tactistream/api/ws.py`; trigger `send_rankings` after moment broadcasts and snapshots in `backend/src/tactistream/api/session.py`. Run T041 → green
- [ ] T043 [P] [US3] Write failing `frontend/tests/unit/PlayerFocus.test.tsx`: `<select>` with optgroups Blue/Amber listing "9 · Blue 9" (localized names in hi); Pin button `aria-pressed` toggles and calls `pin(id)` / `pin(null)`; side panel shows "Focus: Blue 9"; keyboard-only selection works
- [ ] T044 [P] [US3] Implement `frontend/src/components/PlayerFocus.tsx` and mount it in the side panel in `frontend/src/App.tsx`. Run T043 → green
- [ ] T045 [P] [US3] Write failing `frontend/tests/unit/Timeline.ranking.test.tsx`: "Key moments" list shows top 5 from `rankedMoments()` with badges "Direct"/"Off-ball" (localized); applying a new `ranking` reorders the list; top-ranked marker has `data-top="true"`; Enter on a list item opens Why
- [ ] T046 [P] [US3] Extend `frontend/src/components/Timeline.tsx` with the ranked list and top-marker emphasis. Run T045 → green
- [ ] T047 [US3] Extend `frontend/tests/e2e/personalize.spec.ts` (pin part): start `demo_match` seed 42 and `seek` to the end, record first "Key moments" item, pin Blue 9 → first item changes to the space-creation moment with "Off-ball" badge; unpin → original first item returns (SC-002)

**Checkpoint**: Pinning changes ranking, independently of recap.

---

## Phase 6: User Story 4 — Personalized recap with timed overlay track (P2)

**Goal**: deterministic recap playlist, summary and overlay JSON; playback and download.

**Independent Test**: `test_recap_*.py`, `test_recap_api.py`, `RecapSequencer.test.ts`, `RecapPanel.test.tsx`, `recap.spec.ts`.

### Backend

- [ ] T048 [P] [US4] Write failing `backend/tests/unit/test_recap_timing.py`: windows of 10.5 s and 9.0 s → segments `[0,12000)` and `[12000,22500)`; cues `1500–7500` and `13500–19500` (display 6000); display 1000 → clamped to 2000; window 3 s with display 6000 → cue ends at segment end; body > 200 chars → title used; annotations copied; cues sorted and non-overlapping for 50 Hypothesis-generated window lists (SC-007)
- [ ] T049 [P] [US4] Implement `backend/src/tactistream/recap/timing.py` (`LEAD_IN_MS`, `MIN_CUE_MS`, `MAX_CUE_MS`, `layout_segments`, `layout_overlay_track`). Run T048 → green
- [ ] T050 [P] [US4] Write failing `backend/tests/unit/test_recap_summary.py`: unpinned → `recap.summary.general` with count; pinned with 2 involved items incl. an off_ball `space_creation` `interpretation_supported` item → en fan "Blue 9 was involved in 2 key moments, including an off-ball run that helped create room for a forward pass."; same but item `verified_fact` → no off-ball suffix; pinned none → `recap.summary.pinned_none`; analyst adds direct/off-ball counts; hi rendering has identical numbers and player IDs; length ≤ 600
- [ ] T051 [P] [US4] Implement `backend/src/tactistream/recap/summary.py` (`render_recap_summary` via `narrative/render.py`). Run T050 → green
- [ ] T052 [US4] Write failing `backend/tests/unit/test_recap_builder.py` with fixture moments/bundles: only released, non-revoked, eligible-status bundles included (`insufficient_data` and revoked excluded); ≤ 8 items ranked 1..n in viewer order; off-ball reservation replaces item 8 when the best off_ball moment ranks 9th; item title/evidence/annotations from the `(mode, language)` variant; `replay_window` from packet or `replay_window()`; `pinned_player_involvement` present only when pinned; `recap_id` format; `generated_at_state_version` = given content version; no eligible bundle → `NoMomentsYet`; result validates against `recap.schema.json`; identical inputs → identical JSON
- [ ] T053 [US4] Implement `backend/src/tactistream/recap/builder.py` (`build_recap`, `NoMomentsYet`, constants) and `recap/__init__.py`. Run T052 → green
- [ ] T054 [P] [US4] Write failing `backend/tests/unit/test_recap_cache.py`: same key → builder called once and identical bytes; different language → separate entry; LRU evicts oldest beyond 64; `clear()` empties
- [ ] T055 [P] [US4] Implement `backend/src/tactistream/recap/cache.py` (`RecapCache`). Run T054 → green
- [ ] T056 [US4] Write failing `backend/tests/integration/test_recap_api.py`: before any insight → 409 `no_moments_yet`; unknown match → 404; `{"mode":"coach"}` or pinned `blue-77` → 422 `invalid_prefs`; `demo_match` seed 42 at the end with `blue-09` → item for the `space_creation` moment with `off_ball` and summary containing the off-ball sentence (SC-002 recap part); 24 combinations (2 modes × 2 languages × {null, blue-09} × 3 scenarios) validate with `schema_registry.validate("recap", …)` (SC-003); repeat request → byte-identical body and ≤ 50 ms server time; after a new insight release → different `generated_at_state_version`; scripted model client call count unchanged (SC-008); reset clears cache
- [ ] T057 [US4] Implement `backend/src/tactistream/api/routes_recap.py` (`POST /api/matches/{match_id}/recap`), `MatchSession.released_bundles()`/`moments()`/`recap_cache` in `backend/src/tactistream/api/session.py` (adapt to 004's names if they already exist), register in `backend/src/tactistream/api/app.py`. Run T056 → green

### Frontend

- [ ] T058 [P] [US4] Write failing `frontend/tests/unit/client.recap.test.ts` and `frontend/tests/unit/RecapSequencer.test.ts` (fixture `contracts/examples/recap.json` + a 2-item recap): `createRecap` → `{ok:true, recap}` / `{ok:false, error:"no_moments_yet"}` on 409; sequencer segments match the backend formula; `position(0)` → index 0 `lead_in`, cue null; `position(1500)` → `replay`, `replayTimeMs = window.start`, cue active; `position(7600)` → cue null; `position(12000)` → index 1 `lead_in`; `tick` beyond duration → `done`; `seek` clamps
- [ ] T059 [P] [US4] Implement `createRecap` in `frontend/src/api/client.ts` and `frontend/src/replay/RecapSequencer.ts`. Run T058 → green
- [ ] T060 [US4] Write failing `frontend/tests/unit/RecapPanel.test.tsx` (mock client and ReplayView): Generate uses current prefs; list shows rank, title, involvement badge; empty state "No key moments yet" on 409; Play drives the sequencer and passes `controlledTimeMs`/`overlay` to ReplayView; lead-in slate shows the item title; Download creates a Blob whose parsed JSON deep-equals the recap with filename `${recap_id}.json`; prefs change shows "Recap for: …" stale notice and Regenerate; ReplayView with `controlledTimeMs` seeks instead of ticking (extend `frontend/tests/unit/ReplayView.test.tsx`)
- [ ] T061 [US4] Implement `frontend/src/components/RecapPanel.tsx`, add `controlledTimeMs` and `overlay` props to `frontend/src/components/ReplayView.tsx`, mount RecapPanel in the side panel (`frontend/src/App.tsx`), add recap chrome strings to `frontend/src/i18n/{en,hi}.ts`. Run T060 → green
- [ ] T062 [US4] Write `frontend/tests/e2e/recap.spec.ts`: hero seed, pin Blue 9, Generate recap → item with "Off-ball" badge and summary mentioning the off-ball run; Play → lead-in slate then replay view with overlay text visible between cue times; Download → saved file validates against `recap.schema.json` (ajv in test) and equals the API response; repeat in Hindi/Analyst

**Checkpoint**: All four stories independently demonstrable; demo segments 0:43–0:58 and 1:28–1:45 covered.

---

## Phase 7: Polish & Cross-Cutting

- [ ] T063 [P] Document personalization (variant consistency rules, pinned ranking, recap overlay JSON as a studio graphics integration point, Hindi review status) in `docs/architecture.md` section "Personalized views" (create the section if absent)
- [ ] T064 [P] Run `specs/006-personalized-views/quickstart.md` on a fresh clone and fix gaps
- [ ] T065 Update the 006 row in `specs/README.md` feature table: mark the exit condition met with the date, and note Hindi review status ("internal review") and any stop-rule action from T038

---

## Dependencies & Execution Order

- Setup (T001–T003) → Foundational (T004–T013) → US1 (T014–T027) and US2 (T028–T038) can overlap (different files
  except catalogs: T018 before T032) → US3 (T039–T047) → US4 (T048–T062) → Polish (T063–T065).
- US1: T014 → T015 → T016 → T017; T018 after T015; frontend T019–T026 in parallel pairs after T011/T013; T027 needs
  T017 and T020–T026.
- US2: T028 before T030; T029–T031 parallel; T032 needs T018, T028–T031; T033 → T034; T035/T036 parallel to backend;
  T037 needs T032, T036; T038 on 21 Oct.
- US3: T039 → T040 → T041 → T042; T043–T046 need T011; T047 needs T042, T044, T046.
- US4: T048–T051 and T054–T055 parallel; T052 needs T049, T051, T040; T056 needs T053, T055, T042; T058–T059 parallel
  to backend; T060 → T061 need 005 `ReplayView`; T062 needs T057, T061.

## Parallel Example

```text
20 Oct morning:   T014–T017 (consistency gate)  ||  T019–T026 (mode UI)  ||  T028 (glossary draft)
20 Oct afternoon: T029–T033 (catalog tests + revision)  ||  T039–T042 (pinned ranking)  ||  T043–T046 (pin UI)
21 Oct morning:   T048–T057 (recap backend)  ||  T058–T061 (recap UI)  ||  T034 (Hindi review)
21 Oct afternoon: T027, T037, T047, T062 (e2e), T038 (Hindi stop rule), T063–T065
```

## Implementation Strategy

MVP = Phases 1–3 (Fan/Analyst with the consistency gate). Then Hindi (highest risk, start review early on 20 Oct),
then pinning, then recap. If 21 Oct arrives with recap playback unstable, ship recap generation + list + Download
(overlay JSON is the studio deliverable) and play items one at a time via Why; record the decision in the PR.
