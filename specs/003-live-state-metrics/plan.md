# Implementation Plan: Live State & Metrics

**Branch**: `003-live-state-metrics` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-live-state-metrics/spec.md`

## Summary

Put a guarded `Ingestor` between the bus and `MatchState`. It stamps receipt time, validates, dedupes, waits up to 500 ms
to reorder events, stores late frames, and turns late events into revisions. `MatchState` keeps the whole match, and an
immutable `MatchSnapshot` gives an as-of view to every consumer. A deterministic `MetricEngine` computes nine metric kinds
on top of a small, property-tested geometry module. Each result carries evidence IDs, parameters, components and a
limitation key, and comes back `unavailable` when tracking is insufficient. A pure `detect_moments` finds space creation,
press turnovers, switch escapes and shots, with explicit windows, settle rules, coverage and a deterministic ranking.
A `MomentPipeline` turns state changes into new/revised/removed moments, and the session broadcasts them, revoking affected
insights through an `InsightLedger`. Checkpoints and a raw feed archive go through an `ArtifactStore` protocol (local now,
Blob in 007) and allow restore after restart. An as-of snapshot REST endpoint is added.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend)

**Primary Dependencies**: Pydantic v2 contract models (001), NumPy (vectorized distances), FastAPI; dev: hypothesis, pytest,
pytest-asyncio, httpx; Vitest

**Storage**: In-memory whole-match state; `LocalArtifactStore` under `settings.data_dir / "artifacts"` (default `.data/artifacts`,
git-ignored) for checkpoints and archives

**Testing**: unit per metric with exact expected values; hypothesis geometry properties (`derandomize=True`); golden JSON
on 002 outputs; replay-consistency runs (20 shuffles); restore tests; session/WS integration with FakeClock; REST snapshot
contract validation; Vitest for store and `MomentList`

**Target Platform**: Linux container (Codespace / Azure Container Apps)

**Project Type**: Web application (backend + frontend)

**Performance Goals**: cold full recompute < 1 s; ingest ≥ 2,000 records/s; moment broadcast ≤ 1.5 s after trigger receipt;
restore < 2 s

**Constraints**: no model calls or manifest access in state/metrics/moments; fast path (event → WS) never waits on metrics
or checkpoints; deterministic outputs

**Scale/Scope**: one match per session, ≈ 2,800 frames + ≈ 150 events for `demo_match`, ≤ 10 viewers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I Evidence before narrative | PASS | Every `MetricResult` lists event/frame IDs and params; `unavailable` with reason instead of defaults (10/11 visibility rule, missing frames); moments carry `metric_ids` and `tracking_coverage`; limitation keys per metric; revocation removes cards the data no longer supports |
| II Provenance & synthetic honesty | PASS | Records keep `source`; manifest never read (import-scan test from 002 covers `state/`, `metrics/`, `moments/`, `api/`); contribution documented as not a rating; rhythm never called momentum |
| III Deterministic core | PASS | Pure metric functions and `detect_moments`; memoized by snapshot version; no model calls; WS broadcast of events does not wait for metrics; checkpoints run in the background |
| IV Contract-first | PASS | Outputs validated against `metric_result`, `candidate_moment`, `ws_message` schemas in tests; the only schema change (per-player MetricId) is proposed as cross-cutting with a minor version bump, and `contribution` is held back from broadcast until it is accepted |
| V Test-first | PASS | Every module has its failing test first; failure fixtures: duplicates, reorder, gaps, late events, late frames, missing tracking, restart, reconnect |
| VI Measure, don't claim | PASS | Thresholds (35.0 press, 2.0 m channel, 5.0 m separation) are documented prototype params; performance figures recorded in research R11 as measurements |
| VII Scope discipline | PASS | In-memory state + local checkpoints; no Cosmos/Redis; one replica; minimal frontend (store + list), timeline left to 005 |

Post-design re-check: PASS (no violations; Complexity Tracking empty).

## Project Structure

### Documentation (this feature)

```text
specs/003-live-state-metrics/
├── spec.md · plan.md · research.md · data-model.md · quickstart.md · tasks.md
└── contracts/
    └── api-delta.md          # snapshot endpoint, evidence clarifications, WS message usage and ordering
```

### Source Code (repository root)

```text
.gitignore                                    MODIFY: add .data/
.env.example                                  MODIFY: TACTISTREAM_DATA_DIR=.data, TACTISTREAM_REORDER_WINDOW_MS=500,
                                                      TACTISTREAM_CHECKPOINT_EVERY_RECORDS=100, TACTISTREAM_CHECKPOINT_EVERY_MS=10000,
                                                      TACTISTREAM_RESTORE_ON_START=true
backend/src/tactistream/
├── settings.py                               MODIFY: data_dir, reorder_window_ms, checkpoint_every_records, checkpoint_every_ms, restore_on_start
├── state/
│   ├── ingest.py                             NEW  Ingestor, IngestResult, IngestStats
│   ├── match_state.py                        MODIFY: whole-match stores, Revision, StateDelta fields, snapshot(), checkpoint (de)serialization, full_state_hash
│   ├── snapshot.py                           NEW  MatchSnapshot
│   └── checkpoint.py                         NEW  FeedArchive, Checkpointer, restore, clear, key helpers
├── storage/
│   ├── __init__.py                           NEW
│   ├── base.py                               NEW  ArtifactStore protocol, ArtifactNotFound
│   └── local.py                              NEW  LocalArtifactStore
├── metrics/
│   ├── geometry.py                           NEW
│   ├── pass_completion.py · rhythm.py · pressure.py · channel.py · receiver_separation.py
│   ├── defender_follow.py · off_ball_run.py · contribution.py          NEW
│   ├── forward_progress.py                   unchanged (wrapped by registry)
│   └── registry.py                           NEW  MetricParams, MetricDefinition, MetricEngine, AnchorNotFound
├── moments/
│   ├── __init__.py                           NEW
│   ├── detector.py                           NEW  DetectionParams, detect_moments, sequence_start_ms, moment_window, tracking_coverage
│   ├── ranking.py                            NEW  BASE, PINNED_BONUS, strength, score, rank
│   └── pipeline.py                           NEW  MomentChange, MomentPipeline, metric_state_hash
├── transport/replayer.py                     MODIFY: set_cursor(to_ms) (no publish) for restore
├── narrative/catalog/{en,hi}.json            MODIFY: limitation.<kind> × 9
└── api/
    ├── insight_ledger.py                     NEW  InsightLedger
    ├── evidence.py                           MODIFY: resolve evt/frm via state snapshot; metric map latest-wins
    ├── session.py                            MODIFY: Ingestor, tick task, MomentPipeline, ledger, checkpointer, archive, revocation, bulk compatibility
    ├── routes_snapshot.py                    NEW  GET /api/matches/{id}/snapshot
    └── app.py                                MODIFY: include snapshot router; LocalArtifactStore; restore on startup
backend/tests/
├── fixtures/sim.py                           cached simulator outputs (hero, negatives, tracking_gap, demo_match) for tests
├── fixtures/snapshots.py                     hand-built snapshot factory (frames with chosen positions/visibility)
├── golden/metrics_space_creation_42_A.json   committed golden metric/moment dump
├── unit/artifact_store_contract.py           reusable ArtifactStore contract suite (007 reuses)
├── unit/state/{test_ingest,test_match_state_store,test_snapshot,test_checkpoint,test_local_store}.py
├── unit/metrics/{test_geometry,test_pass_completion,test_rhythm,test_pressure,test_channel,test_receiver_separation,test_off_ball_run,test_defender_follow,test_contribution,test_registry}.py
├── unit/moments/{test_detector_rules,test_ranking,test_pipeline,test_insight_ledger}.py
├── unit/metrics/test_golden_sim.py           golden values on 002 outputs + discrimination matrix
├── integration/{test_replay_consistency,test_moments_ws,test_late_event_revision,test_restore,test_snapshot_api,test_ws_resume_moments}.py
└── perf/test_state_perf.py                   @slow: recompute, throughput, restore timings
frontend/src/
├── store/matchStore.ts                       MODIFY: moments, metrics, revoked insights, feed gaps
├── components/MomentList.tsx                 NEW
├── i18n/{en,hi}.ts                           MODIFY: pattern names, "Partial tracking", "Feed gap"
└── App.tsx                                   MODIFY: render MomentList in side panel
frontend/tests/unit/{matchStore.moments.test.ts,MomentList.test.tsx}
docs/metrics.md                               NEW
```

**Structure Decision**: Registry layout (`state/`, `storage/`, `metrics/`, `moments/`, `api/`). One module per metric
behind `MetricEngine` keeps each formula independently testable and documentable; `moments/pipeline.py` isolates lifecycle
diffing from the pure detector.

## Key Design Notes

- **Signatures other features consume**: `MatchState.snapshot(as_of_ms=None) -> MatchSnapshot`;
  `MatchSnapshot.events_between/frames_between/frame_at/position/attack_direction`;
  `MetricEngine.compute(kind, snapshot, anchor_event_id, *, subject_id=None, moments=()) -> MetricResult`;
  `MetricEngine.compute_by_id(metric_id, snapshot)`; `detect_moments(snapshot, metrics) -> list[CandidateMoment]`;
  `rank(moments, pinned_player_id=None)`; `MomentPipeline.add_hook(on_moment=…, on_moment_revised=…)`;
  `InsightLedger.register/affected/revoke/released`; `ArtifactStore` + `LocalArtifactStore`; `geometry.*`.
- **Fast path unchanged**: an applied event is broadcast immediately; metrics/moments are computed in the tick task (≤ 100 ms
  later) once frames settle; checkpoints are background tasks on immutable copies.
- **Purity contract**: metric modules and `detect_moments` take a `MatchSnapshot` and return new contract models; no I/O, no
  clock, no globals. The engine cache is keyed by `(as_of_ms, state_version)`, so a revision never serves a stale value.
- **Manifest-free tests of discrimination**: `test_golden_sim.py` may read 002 manifests to know which segment is which;
  production code never does (002's import-scan test already covers these packages).
- **Restore wiring**: `create_app` lifespan lists `checkpoints/` prefixes, restores each match into a paused session using
  `session_config` to rebuild the replayer (`set_cursor(session_clock_ms)`), and then `pipeline.reconcile`. 007 swaps the
  store via its factory without touching this code.
- **Bulk mode (002 seek)**: during a burst, results update state, evidence and pipeline but nothing is broadcast; the closing
  snapshot carries moments.

## Complexity Tracking

No violations.
