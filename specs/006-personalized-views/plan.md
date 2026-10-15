# Implementation Plan: Personalized Views

**Branch**: `006-personalized-views` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-personalized-views/spec.md`

## Summary

Make the same verified facts useful to different viewers. (1) Fan/Analyst: enforce that all four variants of an
insight carry identical claims and evidence (`unify_mode_plans` + `check_bundle_consistency` in the release path), then
render different depth and interaction on the client with instant, model-free switching. (2) English/Hindi: reviewed
catalogs and chrome strings, a glossary with machine-checked consistency, Western digits, Noto Sans Devanagari, and a
Hypothesis property test proving numbers and player IDs survive every template in every variant. (3) Player pinning:
per-connection prefs on the server, pinned-involvement ranking in `moments/ranking.py`, and a connection-scoped
`ranking` WebSocket message driving the timeline. (4) Recap: deterministic `build_recap` with ranked items, catalog
summaries and a non-overlapping overlay track, a cached `POST …/recap`, and a `RecapPanel` that plays the playlist
through the 005 replay and downloads the overlay JSON.

## Technical Context

**Language/Version**: Python 3.12, TypeScript 5.x strict, Node 22

**Primary Dependencies**: existing stack; new backend dev dep `hypothesis`; new frontend dep
`@fontsource/noto-sans-devanagari` (exact pin)

**Storage**: in-memory per session (connection prefs in WsHub, RecapCache LRU 64); client `localStorage` for prefs

**Testing**: pytest + Hypothesis (property), httpx ASGI + FakeClock integration with two WS clients; Vitest + Testing
Library; Playwright (`personalize.spec.ts`, `recap.spec.ts`)

**Target Platform**: as 001/005

**Project Type**: Web application, registry layout

**Performance Goals**: mode/language switch ≤ 100 ms p95 with zero requests; ranking message ≤ 500 ms after `prefs`;
recap ≤ 300 ms uncached, ≤ 50 ms cached (server time)

**Constraints**: no model calls for switching, ranking or recap; facts identical across variants; recap uses only
released, checked insights; per-connection personalization never alters the shared message log

**Scale/Scope**: 1 match, ≤ 10 connections, ≤ ~30 moments, ≤ 8 recap items, 2 languages × 2 modes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | How |
|---|---|---|
| I Evidence before narrative | PASS | Bundle consistency check blocks variants that differ in claims, evidence, numbers or identities; property test across all templates; recap only uses released checked insights; recap summary numbers are counts derived from listed items; Hindi templates keep hedged causality |
| II Provenance | PASS | Synthetic label in both languages ("सिंथेटिक"); fictional teams ब्लू/एम्बर; Noto Sans Devanagari (OFL) in `docs/permitted-assets.md`; overlay JSON carries the same evidence IDs |
| III Deterministic core | PASS | Ranking, recap assembly, summary and timing are pure functions; switching selects pre-rendered variants; no new agent authority (Producer's ModePlans remain the only model input to presentation) |
| IV Contract-first | PASS | `ranking` added to `ws_message.schema.json` (minor, additive) with example + Pydantic + generated TS before use; recap validated against `recap.schema.json` in tests |
| V Test-first | PASS | Each implementation task is preceded by a failing test; property + integration + e2e |
| VI Measure | PASS | Switch latency measured (p95, 20 toggles); Hindi review labelled "internal review" unless a named reviewer exists |
| VII Scope | PASS | No profiles/persistence beyond localStorage and connection; no MP4 export (after essentials); stop rule for Hindi recorded |

Post-design re-check: PASS (no violations).

## Project Structure

### Documentation (this feature)

```text
specs/006-personalized-views/
├── spec.md · plan.md · data-model.md · quickstart.md · glossary-plan.md · tasks.md
└── contracts/
    ├── recap-api.md         # POST recap, selection, summary, overlay timing, caching
    └── ws-ranking.md        # prefs handling + connection-scoped ranking message
```

### Source Code (repository root)

```text
contracts/
├── schemas/ws_message.schema.json                 EXTEND ranking type + $defs/Ranking (minor bump)
└── examples/ws_ranking.json                       NEW
docs/
├── glossary-hi.md                                 NEW canonical terms + review status
└── permitted-assets.md                            EXTEND Noto Sans Devanagari (OFL 1.1)
backend/
├── pyproject.toml                                 EXTEND dev dep hypothesis; console script tactistream-catalog
├── src/tactistream/
│   ├── contracts/prefs.py                         NEW ViewerPrefs
│   ├── contracts/ws.py                            EXTEND RankingEntry, RankingPayload, "ranking" ServerMessage
│   ├── narrative/consistency.py                   NEW extract_numbers, extract_player_ids, unify_mode_plans, check_bundle_consistency
│   ├── narrative/catalog/{en,hi}.json             REVISE reviewed text, _meta.review, recap.summary.* text
│   ├── narrative/catalog/spec.json                EXTEND (004 format) metadata for recap.summary.*, metric_title.*, metric_def.*, unit.*, label.* keys
│   ├── narrative/preview.py                       NEW `tactistream-catalog preview|lint`
│   ├── agents/workflow.py                         EXTEND unify before render; bundle check before release
│   ├── moments/ranking.py                         EXTEND Involvement, EvidenceLookup, pinned_involvement, rank(pinned), rank_for_viewer
│   ├── recap/__init__.py · timing.py · summary.py · builder.py · cache.py   NEW
│   └── api/{ws_hub.py,ws.py,session.py,routes_recap.py,app.py}             EXTEND/NEW prefs, ranking, recap route
└── tests/
    ├── contract/test_examples.py                  EXTEND ws_ranking example; recap combos
    ├── unit/{test_consistency,test_mode_templates,test_variant_property,test_catalog_parity,test_glossary_consistency,
    │         test_catalog_cli,test_ranking_pinned,test_recap_timing,test_recap_summary,test_recap_builder,test_recap_cache}.py
    └── integration/{test_bundle_release_consistency,test_ws_prefs,test_recap_api}.py
frontend/
├── package.json                                   EXTEND @fontsource/noto-sans-devanagari
├── src/
│   ├── main.tsx                                   EXTEND font import
│   ├── styles/tokens.css                          EXTEND font stack, Devanagari line-height
│   ├── i18n/{en,hi,useT}.ts                       REVISE reviewed hi strings; html lang sync
│   ├── store/{matchStore.ts,prefsStorage.ts}      EXTEND prefs.pinnedPlayerId, ranking, recap; NEW storage
│   ├── api/{client.ts,socket.ts}                  EXTEND createRecap; sendPrefs + resend after snapshot
│   ├── replay/RecapSequencer.ts                   NEW
│   ├── components/{TopBar,InsightCard,EvidenceDrawer,Timeline,ReplayView}.tsx   EXTEND
│   ├── components/{PlayerFocus,RecapPanel}.tsx    NEW
│   └── scene/Annotations.tsx                      EXTEND detail="fan"|"analyst"
└── tests/
    ├── unit/{prefsStorage,matchStore.prefs,socket.prefs,i18n,RecapSequencer,client.recap}.test.ts
    ├── unit/{TopBar.prefs,InsightCard.modes,EvidenceDrawer.modes,Annotations.modes,PlayerFocus,Timeline.ranking,RecapPanel}.test.tsx
    └── e2e/{personalize,recap}.spec.ts
```

**Structure Decision**: Registry layout. Consistency logic sits in `narrative/` (it is about rendered text) and is
invoked from `agents/workflow.py` at release time so every bundle — model-produced or fallback — passes the same
gate. Recap is its own package (`recap/`) per the registry; ranking stays in `moments/ranking.py` per the decision.

## Key Design Notes

**Variant consistency**

```python
def unify_mode_plans(output: ProducerOutput) -> ProducerOutput:
    claim_ids = list(dict.fromkeys([*output.analyst.claim_ids, *output.fan.claim_ids]))   # ≤ 2 (Analyst max 2 claims)
    annotations = sorted(set(output.analyst.annotations) | set(output.fan.annotations))
    return output.model_copy(update={
        "fan": output.fan.model_copy(update={"claim_ids": claim_ids}),
        "analyst": output.analyst.model_copy(update={"claim_ids": claim_ids, "annotations": annotations}),
    })
```

- `check_bundle_consistency` compares the four packets field-by-field (FR-001), then per claim-free text checks:
  `numbers(en) == numbers(hi)` and `players(en) == players(hi)` per mode (multisets, `collections.Counter`),
  `numbers(fan) ⊆ numbers(analyst)` and `players(fan) ⊆ players(analyst)` per language (Counter subtraction empty),
  and no Devanagari digits. Text = title + body.
- `extract_numbers` first masks all localized player display names (both languages) so shirt numbers inside names are
  counted as identities, then applies `NUMBER_RE`; numbers are compared as their exact rendered strings ("5.3").

**Property test** (`test_variant_property.py`): strategies generate `MatchMetadata` roster subsets, player slots
(`sampled_from(roster)`), metric slots (`floats(0, 105)` rounded per slot precision, components likewise), counts
(`integers(0, 8)`); for every catalog key × slot set: render 4 variants via `render_claim`/`render_title`/
`render_recap_summary`; assert language invariance and mode subset; also assert `RenderedText.numbers`/`player_ids`
equal what `extract_*` finds in the text (guards against literal numbers in templates). `@settings(max_examples=200,
derandomize=True)` so CI is deterministic.

**Ranking**

```python
def pinned_involvement(moment, player_id, lookup) -> Involvement:
    events = lookup.events_between(moment.window.start_ms, moment.window.end_ms)
    if any(player_id in (e.player_id, e.recipient_id) for e in events): return "direct"
    for mid in moment.metric_ids:
        m = lookup.metric(mid)
        if m and m.status == "ok" and m.kind in ("off_ball_run", "defender_follow") and player_id in (m.subject_ids or []):
            return "off_ball"
    return "none"
```

- `rank(...)` with a pin sorts by `(inv == "none", -rank_score, moment_id)`; without a pin keeps 003 behaviour.
- `api/ws.py` handles `PrefsMsg`: validate roster → `hub.set_prefs(conn_id, prefs)` → `hub.send_to(conn_id,
  ranking_message(...))`. `WsHub.broadcast(moment)` triggers `hub.send_rankings()` for connections with prefs.
  `send_to` uses the current head seq and bypasses the log.
- `EvidenceLookup` is implemented by `MatchSession.lookup()` over `MatchSnapshot` (events) and `EvidenceIndex`
  (metrics), as of the session clock.

**Recap**

- Route: `prefs = ViewerPrefs.model_validate(body)` → roster check → `moments = rank_for_viewer(session.moments(),
  prefs, session.lookup())` → `bundles = {b.variants[0].moment_id: b for b in session.released_bundles()}` →
  `content_version = max(...)` → `cache.get_or_build((content_version, mode, language, pin), lambda: build_recap(...))`
  → `Response(bytes, media_type="application/json")`.
- `build_recap` raises `NoMomentsYet` when no eligible item → 409.
- Summary slots: `player` (PlayerId → display name via `render.py` slot resolution), `count`, `direct_count`,
  `off_ball_count`; templates live under `recap.summary.*` in both catalogs (fan + analyst).

**Frontend**

- `variantFor(prefs)` (001) already selects the packet; `InsightCard`, `EvidenceDrawer`, `Annotations` read
  `prefs.mode`; components never fetch on prefs change. Switch latency is measured in Playwright with a
  `MutationObserver` on the card body resolving the time from click to text change.
- `PlayerFocus`: native `<select>` with `<optgroup>` per team (accessible by default) + Pin/Unpin toggle button
  (`aria-pressed`); shows "Focus: Blue 9" (localized).
- `RecapSequencer` is master clock during recap playback; `ReplayView` gets `controlledTimeMs` and `overlay` props
  (005 component extended) and seeks its `ReplayController` instead of ticking it; speed fixed 1×.
- `RecapPanel`: Generate (uses current prefs) → list → Play/Pause → Download (`URL.createObjectURL(new Blob([json]))`,
  `a.download = ${recap_id}.json`); "Recap for: Fan · English · Blue 9" with Regenerate when prefs differ.
- Fonts: `import "@fontsource/noto-sans-devanagari/400.css"` and `600.css` in `main.tsx`; `useT` effect sets
  `document.documentElement.lang`.

## Complexity Tracking

No violations. The new connection-scoped `ranking` message is the minimum needed to honour "server per-connection
preferences re-rank moments" without corrupting the shared resumable log; it is documented in
`contracts/ws-ranking.md` and added to the schema as an additive minor change.
