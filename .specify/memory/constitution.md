<!--
Sync Impact Report
- Version change: 1.1.0 → 1.2.0 (2026-10-14, user-requested Microsoft-style UI)
- Modified: Technology & Platform Constraints → Frontend: Fluent UI React v9 (+ Fluent icons) is the component
  library; dark theme default with light toggle
- Templates: no changes required. Affected specs: 001 (Phase 7, T057–T063), 005/006/008 (use the Fluent component
  map in specs/README.md). Design: docs/superpowers/specs/2026-10-14-fluent-ui-design.md

Previous report
- Version change: 1.0.0 → 1.1.0 (2026-10-14, spec review)
- Modified: Technology & Platform Constraints → Security: one bounded exception for the Fabric Eventstream source
- Templates: no changes required. Affected spec: 007-azure-platform (Complexity Tracking, T061)

Previous report
- Version change: template → 1.0.0
- Added principles: I–VII (all new)
- Added sections: Technology & Platform Constraints, Development Workflow & Quality Gates, Governance
- Templates reviewed: plan-template.md (Constitution Check gate uses principles below) ✅,
  spec-template.md ✅, tasks-template.md (tests are REQUIRED in this project, overriding the template's "optional") ✅
- Deferred TODOs: none
-->

# TactiStream Constitution

TactiStream turns a synthetic football event and tracking feed into evidence-backed tactical
stories, synchronized 3D replays, and personalized recaps. Source of product intent:
`TactiStream_Winning_Build_Plan.md`. This constitution governs every spec, plan, task and line of code.

## Core Principles

### I. Evidence Before Narrative (NON-NEGOTIABLE)

- Every factual statement shown to a user MUST reference event IDs, frame IDs or metric IDs that exist
  in the frozen match snapshot it was derived from.
- Numbers, units, player identities and timestamps in user-facing text MUST come from the metric
  engine or validated events. Models never invent measurements, coordinates or annotations.
- Tactical conclusions MUST be labelled "Interpretation". Movement correlation is described as
  "contributing to" or "helping create" space — never as proof of intent or causation.
- Missing tracking MUST produce "Insufficient tracking for this explanation" (or the mode/language
  equivalent) while the ordinary event card remains available. A metric that cannot be computed returns
  `unavailable`, never a reassuring default.
- No uncalibrated confidence percentages, xG labels, scoring probabilities or next-action forecasts in
  the MVP.

### II. Provenance & Synthetic Honesty

- Every record carries `source.kind` (`synthetic` | `event_feed_aligned_to_video` |
  `video_derived`). The UI shows a persistent source badge; the MVP only emits `synthetic`.
- Teams and players are fictional (Blue, Amber). No Premier League marks, real player names, real
  club identities or implied official integration.
- Scenario labels, intended explanations and future outcomes (generation manifest) MUST NEVER be
  passed to agents or to live-path metric code.
- Only permitted assets are used; every third-party asset is listed in `docs/permitted-assets.md`.

### III. Deterministic Core, Bounded Agents

- The match engine (simulation, ingestion, state, metrics, candidate ranking, geometry, rendering
  annotations) is deterministic, pure where practical, and contains no model calls.
- Exactly three agents hold distinct authority: Analyst (propose claims), Verifier (approve / revise /
  reject), Producer (select and adapt approved claims). They exchange typed, versioned payloads with a
  trace ID. One repair loop maximum.
- The fast path (event → state → metrics → overlay) MUST NOT wait on a model call or a historical
  query. Narrative has an 8-second deadline from server receipt; on timeout, failed check or expiry,
  a deterministic factual template is shown and the attempt is kept only in diagnostics.
- Deterministic output checks run after the Producer. Anything adding a new factual proposition,
  number, name, unit or annotation not present in approved claims is rejected.
- Agents call read-only typed tools; the server enforces as-of access (no future data for live claims).

### IV. Contract-First, Spec-Driven

- JSON Schemas in `contracts/schemas/` are the canonical data contracts. Pydantic models
  (backend) and TypeScript types (frontend, generated) MUST validate against them; contract tests
  in CI fail on drift.
- Every schema carries `schema_version`. Breaking changes bump the major version and update
  every example in `contracts/examples/`.
- Work flows spec → plan → tasks → implementation (`/speckit-specify`, `/speckit-plan`,
  `/speckit-tasks`, `/speckit-implement`). No production code without a task ID that traces to a
  functional requirement (FR) or success criterion (SC).

### V. Test-First (NON-NEGOTIABLE)

- Tests are REQUIRED for every task that changes behavior. Write the test, watch it fail for the
  expected reason, then implement the minimum to pass, then refactor (Red–Green–Refactor).
- Simulator, metrics and state are tested with fixed seeds and golden fixtures; identical inputs
  MUST yield byte-identical outputs.
- Agents are tested with a scripted model client (no network); live-model tests are marked
  `@pytest.mark.live` and excluded from default CI.
- Every enumerated failure mode (missing positions, late events, duplicated events, model timeout,
  unsupported claim, reconnect) has a fixture and a test asserting useful degradation.

### VI. Measure, Don't Claim

- Performance numbers in the plan are targets (hypotheses) until measured. Published results state
  sample size, hardware, network conditions and failures.
- Timed-out or fallback narratives are counted in latency statistics and reported separately, never
  silently dropped.
- Coverage is reported alongside accuracy so universal abstention cannot look like success.
- Reviews without a football expert are labelled "internal review", not "expert validated".
- Architecture claims in docs and the demo include only services that are actually deployed and used.

### VII. Scope Discipline & Simplicity

- Build the essentials in roadmap order (`specs/README.md`). "After essentials" items start only when
  every essential release gate passes. Stop rules in the roadmap are binding.
- YAGNI: one always-ready Container Apps replica, one match per session, in-memory live state with
  checkpoints. No AKS, Cosmos DB, Custom Vision, screen capture or forecasting in the MVP.
- Prefer small focused modules with one responsibility and explicit typed interfaces.

## Technology & Platform Constraints

- Backend: Python 3.12, FastAPI, Pydantic v2, NumPy, uv for dependency management (lockfile committed).
- Frontend: TypeScript 5 (strict), React 19, Vite, three.js via @react-three/fiber, Zustand.
  UI components: Fluent UI React v9 (`@fluentui/react-components`, `@fluentui/react-icons`, exact-pinned) with a
  TactiStream brand theme; dark by default with a light toggle. No other UI component library.
- Agents: Microsoft Agent Framework (Python) with models served by a Microsoft Foundry deployment.
  The exact package version and model deployment are pinned in `specs/001-walking-skeleton/research.md`.
- Transport: Azure Event Hubs (partition key = `match_id`; consumer groups `live-state`, `fabric`).
  An in-memory bus with identical semantics is used for local runs and tests.
- Analytics: Microsoft Fabric Eventstream → Eventhouse (KQL). Files: Azure Blob Storage.
  Observability: OpenTelemetry → Application Insights. Hosting: Azure Container Apps (min=max=1 replica).
- Security: no secrets in git; `.env.example` lists names only; Azure access via managed identity /
  `DefaultAzureCredential`; GitHub Actions deploys via OIDC federation.
  Single exception: if Fabric Eventstream cannot authenticate to Event Hubs with Entra ID, one Listen-only
  shared-access policy scoped to the `tactistream-feed` hub may be used, stored only in the Fabric connection, never
  in git or app settings, and removed as soon as Entra authentication works.
- Pitch convention: 105 m × 68 m, origin at bottom-left corner, x along length, y across width,
  metres. Times are integer milliseconds. Tracking frames at 10 Hz.
- Languages: English and Hindi. User-facing narrative text is rendered from reviewed template
  catalogs; numbers use Western Arabic digits in both languages.

## Development Workflow & Quality Gates

- Each feature lives in `specs/NNN-name/` with `spec.md`, `plan.md`, `tasks.md` (plus research,
  data-model, quickstart and contracts where the plan needs them). Set the active feature in
  `.specify/feature.json` before `/speckit-implement`.
- Branch per feature (`NNN-name`), merged to `main` via PR; commit after each task or small group.
- CI (GitHub Actions) MUST pass before merge: `ruff check`, `ruff format --check`, `mypy --strict`
  (backend `src/`), `pytest` (non-live), contract drift check, `tsc --noEmit`, `eslint`, `vitest`,
  frontend build, and the Playwright smoke test.
- A feature is done when its success criteria are demonstrated by tests or recorded measurements
  and its quickstart runs on a fresh clone.

## Governance

- This constitution supersedes other practices. Plans MUST include a Constitution Check that lists each
  principle as PASS or as a justified entry in Complexity Tracking.
- Amendments: edit this file with a Sync Impact Report, bump the version (MAJOR: principle removed or
  redefined; MINOR: principle or section added; PATCH: clarification), and update affected templates/specs.
- Organizer rules (official hackathon rules and Innovation Studio instructions) override this document
  wherever they conflict.

**Version**: 1.2.0 | **Ratified**: 2026-10-14 | **Last Amended**: 2026-10-14
