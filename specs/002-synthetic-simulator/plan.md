# Implementation Plan: Synthetic Simulator

**Branch**: `002-synthetic-simulator` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-synthetic-simulator/spec.md`

## Summary

Build a deterministic, NumPy-based match simulator under `tactistream.simulator`. A possession state machine with an
explicit legal-transition table makes event sequences legal. Kinematics with spline keyframes for scripted actors and
clamped followers for everyone else keeps speed ≤ 9.5 m/s and acceleration ≤ 6 m/s². Seven scenario families (three
positives, three negatives, one missing-data fixture) plus a filler produce the hero sequence and a 4–5 minute `demo_match`
program. Every output passes `validate_output` before it is written. Ground-truth labels go to a separate manifest that
live-path code can never import. The replay path gains scenario/seed sessions, speed (0.5/1/2) and seek. The frontend gains
`SessionControls`. The 001 skeleton fixture keeps working through the same `FeedReplayer`.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend)

**Primary Dependencies**: NumPy (PCG64, vectorized tracks), Pydantic v2 contract models from 001, typer (CLI), FastAPI;
dev: hypothesis (property tests, `derandomize=True`), pytest, Vitest, Playwright

**Storage**: Generated files under `data/generated/` (git-ignored); golden hashes in `backend/tests/golden/simulator_hashes.json`;
in-process LRU cache of generated envelopes (8 configs)

**Testing**: pytest unit/integration (FakeClock, InMemoryBus), golden SHA-256, parametrized validation and intent checks
(210 outputs default, 4,200 in `-m slow`), import-scan test, Vitest for `SessionControls`, Playwright `simulator.spec.ts`

**Target Platform**: Linux container (Codespace / Azure Container Apps), Chromium for e2e

**Project Type**: Web application (backend + frontend), plus a CLI

**Performance Goals**: single family ≤ 0.5 s, `demo_match` ≤ 3 s to simulate; uncached `demo_match` session creation ≤ 4 s

**Constraints**: byte-identical output per config; no model calls; no positions fabricated; manifest never on the bus

**Scale/Scope**: 8 scenarios × 6 variants; `demo_match` ≈ 2,800 frames × 23 entities ≈ 65k positions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I Evidence before narrative | PASS | Simulator emits only records; invisible entities have no `pos_m`; `tracking_gap` exists so downstream can prove "insufficient tracking" instead of fabricating |
| II Provenance & synthetic honesty | PASS | `source.kind = synthetic` + `generator_version` + `seed` on every record; fictional Blue/Amber; opaque `sim-…` match IDs; manifest isolated (file-only, import-scan test, never on bus) |
| III Deterministic core | PASS | Pure `simulate(config)`; PCG64 sub-streams; no model calls; replay timing via injected `Clock` |
| IV Contract-first | PASS | No schema changes; every envelope validated against `feed_envelope.schema.json` in `validate_output`; REST additions documented in `contracts/api-delta.md` |
| V Test-first | PASS | Each module has a failing test task first; golden hash, intent checks, property tests, refusal tests, e2e |
| VI Measure, don't claim | PASS | Performance targets recorded as measurements in research R10; validation tolerances stated; synthetic results not presented as real-match accuracy |
| VII Scope discipline | PASS | Scripted families, not a physics engine; no goals; sessions shared per config; seek API without a UI scrubber (005 owns the timeline) |

Post-design re-check: PASS (no violations; Complexity Tracking empty).

## Project Structure

### Documentation (this feature)

```text
specs/002-synthetic-simulator/
├── spec.md · plan.md · research.md · data-model.md · quickstart.md · tasks.md
└── contracts/
    ├── api-delta.md         # /api/scenarios, extended /api/sessions and control
    └── cli.md               # tactistream-sim generate | list, file formats, exit codes
```

### Source Code (repository root)

```text
.gitignore                                     MODIFY: add data/generated/
.env.example                                   MODIFY: TACTISTREAM_MAX_SESSIONS=8
Makefile                                       MODIFY: target `sim-hero` (generate hero into data/generated/hero)
backend/
├── pyproject.toml                             MODIFY: console script tactistream-sim; dev dep hypothesis; pytest marker `slow` (excluded by default)
├── src/tactistream/
│   ├── settings.py                            MODIFY: max_sessions: int = 8
│   ├── simulator/
│   │   ├── __init__.py                        exports simulate, SimulationConfig, SimulationOutput, validate_output
│   │   ├── config.py                          SimulationConfig, VariantSpec, VARIANTS, ConfigError, HERO_MATCH_IDS
│   │   ├── roster.py                          build_metadata, FORMATION_433, slots
│   │   ├── possession.py                      Phase, PossessionState, LEGAL_TRANSITIONS, transition, check_sequence
│   │   ├── kinematics.py                      spline_track, follow_track, check_bounds, ball_track, plan_reposition
│   │   ├── script.py                          SegmentBuilder (beats → events via possession; keyframes → tracks; scene transform)
│   │   ├── scenarios/__init__.py              FAMILIES registry: name → build(builder, variant_spec) -> SegmentResult
│   │   ├── scenarios/space_creation.py
│   │   ├── scenarios/press_turnover.py
│   │   ├── scenarios/switch_escape.py
│   │   ├── scenarios/run_no_channel.py
│   │   ├── scenarios/press_no_turnover.py
│   │   ├── scenarios/switch_closed.py
│   │   ├── scenarios/tracking_gap.py
│   │   ├── scenarios/circulation.py           program filler only
│   │   ├── program.py                         Segment, MatchProgram, DEMO_MATCH
│   │   ├── manifest.py                        SegmentLabel, TrackingGap, GenerationManifest
│   │   ├── engine.py                          simulate(config) -> SimulationOutput
│   │   ├── validate.py                        ValidationIssue, ValidationReport, validate_output, validate_envelopes
│   │   ├── io.py                              to_envelopes, canonical_line, write_output, WrittenFiles
│   │   └── cli.py                             typer app: generate, list
│   ├── transport/replayer.py                  MODIFY: wall_ms re-stamp, set_speed, seek, duration_ms, on_rewind
│   └── api/
│       ├── scenarios.py                       ScenarioInfo, list_scenarios, load_scenario_envelopes (lru_cache 8)
│       ├── routes_sessions.py                 MODIFY: scenario/seed/variant body, GET /api/scenarios, control speed/seek
│       └── session.py                         MODIFY: SessionRegistry.get_or_create + LRU limit; MatchSession.seek (bulk mode), set_speed
└── tests/
    ├── golden/simulator_hashes.json           {"space_creation/42/A": sha, "demo_match/42/A": sha}
    ├── simulator/intent.py                    test-only geometry + intent checks per family
    ├── unit/simulator/{test_config,test_roster,test_possession,test_kinematics,test_validate,test_io,test_manifest_isolation}.py
    ├── unit/simulator/{test_space_creation,test_negatives_and_gap,test_press_switch,test_program,test_variants_eval}.py
    ├── unit/simulator/test_determinism.py     golden hashes + run-twice identity
    ├── unit/simulator/test_library_matrix.py  7 families × 6 variants × seeds (slow: 100 seeds)
    ├── unit/simulator/test_cli.py
    ├── unit/test_replayer_speed_seek.py
    └── integration/{test_sim_sessions,test_sim_seek}.py
frontend/
├── src/
│   ├── api/client.ts                          MODIFY: listScenarios, createSession({scenario, seed, variant}), control speed/seek
│   ├── store/matchStore.ts                    MODIFY: session {scenario, seed, variant, speed}
│   ├── components/SessionControls.tsx         NEW: scenario select, seed input, New seed, speed segmented control
│   ├── i18n/{en,hi}.ts                        MODIFY: chrome strings for the controls
│   └── App.tsx                                MODIFY: render SessionControls; Start uses selected config
└── tests/
    ├── unit/SessionControls.test.tsx
    └── e2e/simulator.spec.ts
docs/simulator.md                              NEW: conventions, families, variants, intent checks, determinism policy
```

**Structure Decision**: Registry layout (`simulator/`, `transport/`, `api/`). Scenario families are one module each behind a
`FAMILIES` registry so 008 can enumerate them; `script.py` holds the shared builder so families stay small and declarative.

## Key Design Notes

- **Builder pattern** (`simulator/script.py`):
  `SegmentBuilder(rng, variant, focus_team, start: Kickoff | Restart, t0_ms)` with
  `beat(t_ms, event_type, actor, **fields)` (each call runs `possession.transition`, so illegal sequences fail immediately),
  `keyframes(player_id, [(t_ms, (x, y)), …])`, `gap(player_ids, start_ms, end_ms)`, `label(...)`, and
  `build() -> SegmentResult(events, tracks, ball_phases, gaps, label, end_positions, end_state)`. Families write nominal
  coordinates in the "focus attacks +x, not mirrored" frame; the builder applies the scene transform and jitter.
- **Engine**: `simulate(config)` → `FAMILIES[scenario]` (or `DEMO_MATCH.run`) → frames sampled at 100 ms from tracks
  (gap players set invisible) → events/frames as 001 contract models → `GenerationManifest` with `feed_sha256` computed from
  `io.to_envelopes` bytes. `simulate` does no file I/O.
- **Validation is always on**: `cli generate` and `api.scenarios.load_scenario_envelopes` both call `validate_output` and
  refuse to serve or write failing output.
- **Manifest isolation**: `test_manifest_isolation.py` parses every module under `src/tactistream/{state,metrics,moments,agents,narrative,api,transport}`
  with `ast` and fails on any import of `tactistream.simulator.manifest` or of `GenerationManifest`; it also asserts that
  `to_envelopes(output)` contains no key named `scenario`, `variant`, `segments`, `expected_pattern` or `intended_explanation`.
- **Replayer speed**: session time = `anchor_session_ms + (clock.now_ms() − anchor_wall_ms) × speed`; `set_speed`
  re-anchors, so the clock is continuous.
- **Seek in the session**: `MatchSession.seek(to_ms)` sets `bulk = True`; `on_rewind` clears state as `reset` does;
  `replayer.seek` returns `SeekResult.last_record_id`; the consumer flips `bulk = False` once it applies that record id, then
  `hub.broadcast_snapshot()`. In bulk mode, per-record WS messages and fact cards are suppressed (state and evidence still update).
- **Session config**: `SessionRegistry.get_or_create("space_creation", 42, "A")` → `(session, shared)`; skeleton maps to the
  001 fixture path.
- **Frontend**: `SessionControls` reads `GET /api/scenarios` once. The seed input is a number field 1–9999. New seed uses
  `crypto.getRandomValues` and re-draws on collision, then creates a new session and reconnects the socket. Speed is a
  three-option radio group sending `control({action:"speed"})`. All controls have labels and keyboard support.

## Complexity Tracking

No violations.
