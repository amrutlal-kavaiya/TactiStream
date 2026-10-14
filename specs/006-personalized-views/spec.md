# Feature Specification: Personalized Views — Fan/Analyst, English/Hindi, player pinning, automated recap

**Feature Branch**: `006-personalized-views`

**Created**: 2026-10-14

**Status**: Ready for implementation

**Input**: Build plan viewer-flow steps 6–7 ("Switch Fan to Analyst, then English to Hindi, while retaining the same
facts"; "Pin Blue 9 and generate a player-focused recap that includes the off-ball contribution"), scope-table rows
"Fan and Analyst views", "Player pinning", "English and Hindi", "Automated recap", and the UI guidance: "Fan mode should
use plain-language cards, a simple emphasis animation, and fewer numbers. Analyst mode should show time windows, metric
definitions and evidence references. Pinned-player mode should change the timeline ranking and recap selection, rather
than merely adding a name to the header." Roadmap exit (20–21 Oct): "Fan/Analyst differ in detail with identical facts;
EN/HI switch preserves numbers & identities; pinning changes ranking and recap; recap playlist + overlay JSON."

**Depends on**: 001 (matchStore prefs, MatchSocket, TopBar, InsightCard, EvidenceDrawer, i18n, `render_claim`,
`render_title`, `check_packet`, WsHub), 003 (`moments/ranking.py rank(moments, pinned_player_id=None)`, metric kinds
`off_ball_run`, `defender_follow`, `contribution`), 004 (`explain_moment`, `ProducerOutput {fan, analyst}`,
InsightBundle with 4 variants, catalog keys `fact.*`, `interp.*`, `title.*`, `status.insufficient_tracking`,
`AgentTrace.tsx`), 005 (`ReplayView`, `ReplayController`, `Timeline`, `Annotations`, `replay_window`).

**Stop rule (binding, from the roadmap)**: if Hindi output quality is weak by **21 Oct 2026**, ship reviewed templates
only for both languages. Because all user-facing narrative is already rendered from reviewed template catalogs (no
free-form model prose), the stop rule means: drop any template whose Hindi review is not complete and fall back to the
factual template family for that claim kind in both languages.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fan and Analyst see the same facts at different depth (Priority: P1) 🎯 MVP

A viewer watching the hero sequence sees the Fan card "Blue 9's run helped create room for the pass." with a simple
emphasis pulse on Blue 9 in the replay. They switch to **Analyst**: the same card now reads "The defender shifted toward
Blue 9 while the central channel widened. The next forward pass used that space." with the time window, evidence chips
and, in the drawer, metric definitions, components and the agent trace. Switching back and forth is instant, makes no
network or model call, and never changes which claims, players, numbers or evidence are being presented.

**Why this priority**: The scope table's completion condition ("different detail and interaction, consistent underlying
facts") and the 0:43–0:58 demo segment. It is purely client-side selection over data that 004 already delivers, so it is
the cheapest high-value personalization.

**Independent Test**: `test_consistency.py` + `test_variant_property.py` (backend) and Playwright `personalize.spec.ts`
(toggle 20× with timing and request capture).

**Acceptance Scenarios**:

1. **Given** a released hero bundle, **When** the viewer switches Fan → Analyst, **Then** within 100 ms the card shows the
   analyst variant (title, body, time window `mm:ss.s–mm:ss.s`, evidence chips), with the same `claim_ids`,
   `evidence_ids`, `claim_status` and labels as the fan variant.
2. **Given** Analyst mode, **When** the viewer opens Evidence, **Then** the drawer shows metric definitions, windows,
   components, evidence references and an **Agent trace** tab rendering `AgentTrace` for the packet's `trace_id`; in Fan
   mode the drawer shows plain-language evidence summaries and status labels, no agent trace, and a "Show analyst
   details" link that switches mode.
3. **Given** a replay is open, **When** the mode is Fan, **Then** only the fan variant's annotations are drawn, the
   highlight ring pulses once (static under reduced motion) and the channel band has no numeric label; **When** the mode
   is Analyst, **Then** the analyst variant's annotations are drawn with numeric labels and path time ticks.
4. **Given** any mode switch, **When** the request log is inspected, **Then** no HTTP request and no model call occurred;
   only a WebSocket `prefs` message was sent.
5. **Given** the Producer selected one claim for Fan and two for Analyst, **When** the bundle is assembled, **Then** both
   variants carry both claim IDs (Fan renders them with fan templates), and a bundle whose variants disagree on claims,
   evidence or numbers is not released (fallback `output_check_failed`).

---

### User Story 2 - English and Hindi preserve every number and identity (Priority: P1)

A Hindi-speaking viewer switches **EN → HI**. UI chrome (top bar, buttons, drawer headings, timeline) and the narrative
switch to reviewed Hindi: "ब्लू 9 की बिना गेंद की दौड़ ने पास के लिए जगह बनाने में मदद की।" Team names are ब्लू and
एम्बर; digits stay Western Arabic (1.9, 5.3); player identities, numbers and evidence IDs are identical to the English
variant. Labels read "व्याख्या" (Interpretation) and "सिंथेटिक" (Synthetic). Text renders in Noto Sans Devanagari.

**Why this priority**: Essential scope row ("Reviewed terminology; numbers and identities preserved"); the hackathon
values reach, and preservation of facts across languages is a checkable integrity claim.

**Independent Test**: `test_catalog_parity.py`, `test_variant_property.py` (Hypothesis), `test_glossary_consistency.py`,
`i18n.test.ts`, and the language step of `personalize.spec.ts`.

**Acceptance Scenarios**:

1. **Given** any template in the catalogs and any generated slot set, **When** rendered in `en` and `hi` for the same
   mode, **Then** the multisets of numbers and of player IDs are identical.
2. **Given** the Hindi catalog, **When** scanned, **Then** it contains no Devanagari digits (U+0966–U+096F), has exactly
   the same keys and placeholder names as the English catalog, and uses the glossary's canonical Hindi term wherever the
   English template uses the glossary term.
3. **Given** the viewer selects Hindi, **When** the page re-renders, **Then** `<html lang="hi">` is set, narrative
   containers carry `lang="hi"`, all chrome strings come from `hi.ts`, and Devanagari glyphs render with Noto Sans
   Devanagari (self-hosted, listed in `docs/permitted-assets.md`).
4. **Given** the glossary and catalogs, **When** the review is recorded, **Then** `docs/glossary-hi.md` and catalog
   `_meta.review` state "internal review" with date and reviewer initials unless a named native-speaker or football
   expert reviewer signed off.
5. **Given** 21 Oct, **When** a Hindi template has not passed review, **Then** it is removed from both catalogs' active
   set and claims using it fall back to the reviewed factual template (stop rule).

---

### User Story 3 - Pin a player and see the stories re-ranked around them (Priority: P2)

The viewer opens **Player focus**, picks Blue 9 from the roster and presses **Pin**. The timeline's ranked "Key
moments" list re-orders: the space-creation moment where Blue 9 made the off-ball run moves to the top with an
"Off-ball" badge; moments where Blue 9 touched the ball get a "Direct" badge; others follow. Unpinning restores the
default order. Ranking happens on the server per connection, so other viewers are unaffected.

**Why this priority**: Required by the scope table ("Focus changes the selected stories and recap") and the demo, but it
builds on US1 surfaces and feeds US4.

**Independent Test**: `test_ranking_pinned.py`, `test_ws_prefs.py`, `PlayerFocus.test.tsx`, `Timeline.ranking.test.tsx`,
and the pin step of `personalize.spec.ts`.

**Acceptance Scenarios**:

1. **Given** `demo_match` seed 42 (match `demo-blue-amber-002`) after its last segment, **When** the viewer pins Blue 9,
   **Then** within 500 ms the server sends a connection-scoped `ranking` message whose first entry is the `space_creation`
   segment's moment with `pinned_involvement = "off_ball"`, and the top-ranked timeline moment differs from the unpinned
   top moment. (The standalone hero scenario yields a single moment, so ranking changes are tested on `demo_match`; 002
   guarantees its unpinned rank-1 moment does not involve Blue 9.)
2. **Given** Blue 9 pinned, **When** a moment involves Blue 9 as event actor or recipient in its window, **Then** its
   involvement is `direct`; **When** Blue 9 is only a subject of an `ok` `off_ball_run` or `defender_follow` metric of
   the moment, **Then** it is `off_ball`; otherwise `none`; involved moments always rank above non-involved ones, ties by
   base rank score then moment ID.
3. **Given** two viewers on the same match, **When** one pins Blue 9, **Then** only that connection receives the changed
   ranking; the other connection's ranking and the shared `seq` log are unchanged.
4. **Given** the viewer reconnects, **When** the socket resumes, **Then** the client re-sends its `prefs` and receives a
   fresh ranking after the snapshot.
5. **Given** the roster, **When** the viewer uses the keyboard only, **Then** they can choose a player (grouped by team,
   shirt number and localized name) and pin/unpin; the pinned player is shown in the side panel as "Focus: Blue 9".

---

### User Story 4 - Generate a personalized recap with a timed overlay track (Priority: P2)

The viewer presses **Generate recap**. A ranked playlist (≤ 8 items) appears with a concise summary — for Blue 9:
"Blue 9 was involved in 2 key moments, including an off-ball run that helped create room for a forward pass." Pressing
**Play recap** plays each item through the tactical replay with a 1.5 s title lead-in and the item's overlay text shown
at its scheduled time. **Download overlay JSON** saves the recap document (`recap.schema.json`) that a studio graphics
system could consume.

**Why this priority**: Essential scope row and the 1:28–1:45 demo segment ("Connect the experience to a studio
workflow"); depends on US3 for the pinned variant and 005 for playback.

**Independent Test**: `test_recap_builder.py`, `test_recap_timing.py`, `test_recap_api.py` (24 combinations schema-valid),
`RecapSequencer.test.ts`, `RecapPanel.test.tsx`, and `recap.spec.ts`.

**Acceptance Scenarios**:

1. **Given** released insights exist, **When** the client POSTs `/api/matches/{id}/recap` with `{mode, language,
   pinned_player_id}`, **Then** the response validates against `recap.schema.json`, has 1–8 items ranked 1..n by the
   viewer ranking, uses only released (checked, non-revoked) insights, and its `summary` is rendered from
   `recap.summary.*` catalog templates in the requested mode and language.
2. **Given** Blue 9 is pinned in the hero match, **When** the recap is generated, **Then** it contains an item with
   `pinned_player_involvement = "off_ball"` for the space-creation moment and the summary mentions the off-ball run.
3. **Given** a recap, **When** its `overlay_track` is inspected, **Then** item *i*'s cue starts exactly 1500 ms after
   the start of segment *i* (segments are back-to-back: 1500 ms lead-in + replay window length), ends no later than the
   segment end, and no two cues overlap.
4. **Given** no released insight yet, **When** a recap is requested, **Then** the API returns 409 `no_moments_yet` and the
   panel shows "No key moments yet".
5. **Given** the recap is playing, **When** the viewer presses Download overlay JSON, **Then** a file `<recap_id>.json`
   containing the exact recap document is saved; **When** the same prefs are requested again without new insights,
   **Then** the identical document is returned from cache.

### Edge Cases

- **Producer chose different claims per mode** → `unify_mode_plans` gives both modes the union (≤ 2, analyst order);
  fan annotations ⊆ analyst annotations (analyst gets the union). If unification is impossible (unknown claim ID), the
  bundle fails `check_bundle_consistency` → fallback template, attempt kept in diagnostics.
- **Template value shown only in Analyst** (e.g., clearance metres) → allowed; Fan numbers must be a sub-multiset of
  Analyst numbers and any value shown in both is formatted identically.
- **Player display name contains the shirt number** ("Blue 9") → number extraction ignores digits that are part of a
  resolved player name, so "9" is counted as identity, not as a numeric fact.
- **Pinned player not in roster / from a reset match** → server ignores the pin (`pinned_player_id=null`), sends an
  `error {error:"unknown_player"}` and the client unpins.
- **Pinned player involved in no moment** → ranking unchanged except badges; recap summary uses
  `recap.summary.pinned_none` ("Blue 2 has not been involved in a key moment yet.") and lists the general top moments
  with involvement `none`.
- **More than 8 eligible moments** → top 8 by viewer ranking; if the pinned player's best `off_ball` moment is outside
  the top 8 it replaces item 8 ("off-ball reservation").
- **Insight revoked after recap generation** → next request (cache key changes with content version) excludes it; a
  playing recap skips a now-revoked item and shows "This explanation was withdrawn" during its slot.
- **Item replay returns 409** (tracking degraded later) → the slot shows the lead-in title, overlay text and the
  insufficient-tracking message for the item's duration; timing is unchanged.
- **Overlay text > 200 characters** → cue text uses the variant title instead (never truncated mid-number).
- **Language switch while recap open** → the panel marks the recap "for English" and offers Regenerate (cached server
  side, no model call); Download always exports the displayed document.
- **Reduced motion** → Fan emphasis pulse disabled; recap lead-in is a static slate.

## Requirements *(mandatory)*

### Functional Requirements

**Fan / Analyst (US1)**

- **FR-001**: All four variants of an InsightBundle MUST share `insight_id`, `insight_version`, `moment_id`,
  `state_version`, `claim_ids` (as a set), `evidence_ids` (as a set), `claim_status`, `labels`, `source_kind`,
  `render.replay_window`, `render.show_from_ms/show_until_ms`, `expires_at_session_ms` and `trace_id`; fan
  `render.annotations` MUST be a subset of analyst `render.annotations`.
- **FR-002**: `narrative/consistency.py::unify_mode_plans(output)` MUST set both ModePlans' `claim_ids` to the ordered union
  (analyst order first) and analyst `annotations` to the union; `check_bundle_consistency(bundle, metadata)` MUST enforce
  FR-001 and FR-008 and run in `agents/workflow.py` before release; failures produce `narrative_status fallback` with
  `fallback_reason = output_check_failed`.
- **FR-003**: Fan rendering MUST show title + body, Why and Evidence buttons, at most the numbers present in the fan
  template, and a single emphasis pulse on the first highlighted player in the replay; Analyst rendering MUST add the
  time window, inline evidence chips, claim-status label, numeric annotation labels and path time ticks.
- **FR-004**: The Analyst evidence drawer MUST include metric definitions, windows, components, evidence references and an
  Agent trace tab (`AgentTrace.tsx`, by `trace_id`); the Fan drawer MUST show plain-language evidence summaries with status
  labels and a "Show analyst details" action.
- **FR-005**: Mode and language switching MUST be client-side selection of the matching variant from the stored
  InsightBundle (`variantFor(prefs)`), MUST NOT trigger HTTP requests or model calls, and MUST re-render within 100 ms.
- **FR-006**: Prefs (`mode`, `language`, `pinned_player_id`) MUST persist in `localStorage` (`tactistream.prefs.v1`) and be
  sent as a WebSocket `prefs` message on change and after every (re)connect snapshot.

**English / Hindi (US2)**

- **FR-007**: `backend/src/tactistream/narrative/catalog/{en,hi}.json` MUST have identical key sets and identical placeholder
  names per key, a `_meta` object (`language`, `catalog_version`, `review: {status: "internal_review" | "native_review" |
  "expert_review", reviewer, date}`), and Western Arabic digits only.
- **FR-008**: For every template and slot set, rendered numbers and player IDs MUST be identical as multisets across `en`
  and `hi` (same mode), and Fan numbers/player IDs MUST be a sub-multiset of Analyst ones (same language) with identical
  formatting for shared values; this is verified by a Hypothesis property test over all catalog templates.
- **FR-009**: `docs/glossary-hi.md` MUST define canonical Hindi terms (at least: Blue, Amber, off-ball run, passing
  channel, pressure, space, interpretation, synthetic, insufficient tracking, partial tracking, verified fact, evidence,
  forward pass, defender, metre, recap, Fan, Analyst, pin) with rationale and review status; a test MUST verify catalog
  usage of each canonical term.
- **FR-010**: `frontend/src/i18n/hi.ts` MUST contain every key of `en.ts` (type-checked) with reviewed Hindi chrome
  strings and no Devanagari digits; `useT` MUST switch instantly; `<html lang>` and narrative `lang` attributes MUST follow
  the language.
- **FR-011**: The UI MUST self-host Noto Sans Devanagari (OFL 1.1, via `@fontsource/noto-sans-devanagari`) in the font
  stack and list it in `docs/permitted-assets.md`.
- **FR-012**: Hindi interpretation templates MUST keep hedged causality equivalent to English ("helped create" →
  "बनाने में मदद की"), never asserting intent.

**Player pinning (US3)**

- **FR-013**: `frontend/src/components/PlayerFocus.tsx` MUST list the roster from match metadata grouped by team (shirt
  number + localized display name), allow pin/unpin by keyboard and pointer, and update `prefs.pinnedPlayerId`.
- **FR-014**: The server MUST store prefs per WebSocket connection (`ConnectionPrefs`), validate `pinned_player_id` against
  the roster, and send a connection-scoped `ranking` message (new WS type, see `contracts/ws-ranking.md`) after each
  `prefs` message, after each snapshot sent to a connection that has prefs, and after each new or updated `moment`.
- **FR-015**: `moments/ranking.py` MUST compute `pinned_involvement(moment, player_id, lookup) -> "direct" | "off_ball" |
  "none"` (direct: actor or recipient of an event in the moment window; off_ball: otherwise a subject of an `ok`
  `off_ball_run` or `defender_follow` metric in `moment.metric_ids`) and apply the pinned bonus inside
  `rank(moments, pinned_player_id=None, *, lookup=None)` with sort key `(involvement == "none", −rank_score,
  moment_id)`; `rank_for_viewer(moments, prefs, lookup) -> list[RankedMoment]` exposes involvement for WS and recap.
- **FR-016**: `ranking` messages MUST NOT be appended to the shared message log, MUST carry `seq` equal to the head seq at
  send time, and MUST NOT affect other connections.
- **FR-017**: `Timeline.tsx` MUST show a ranked "Key moments" list (top 5, viewer ranking, involvement badges "Direct" /
  "Off-ball") and emphasise the top-ranked marker; Enter on a list item opens Why.

**Recap (US4)**

- **FR-018**: `recap/builder.py::build_recap(moments, bundles, prefs, metadata, state_version) -> Recap` MUST select up to 8
  items from `moments` (viewer-ranked `RankedMoment`s) whose bundle is released, non-revoked and has `claim_status` in
  {`verified_fact`, `interpretation_supported`, `fallback_template`}, apply the off-ball reservation, and fill item
  `title`, `evidence_ids`, `replay_window` (packet `render.replay_window`, else 005 `replay_window`) and
  `pinned_player_involvement` (when pinned) from the variant for `(prefs.mode, prefs.language)`.
- **FR-019**: The recap `summary` MUST be rendered from catalog templates `recap.summary.general`,
  `recap.summary.pinned`, `recap.summary.pinned_off_ball` (only when an included item has involvement `off_ball`, pattern
  `space_creation` and `claim_status = interpretation_supported`) and `recap.summary.pinned_none`; numbers are item counts
  computed by the builder.
- **FR-020**: `recap/timing.py::layout_overlay_track` MUST place segments back-to-back (segment *i* length = 1500 ms
  lead-in + replay window length) and one cue per item with `start_ms = segment_start + 1500`, `end_ms = min(start_ms +
  (show_until_ms − show_from_ms) clamped to [2000, 6000], segment_end)`, `text` = variant body if ≤ 200 chars else title,
  `annotations` = variant `render.annotations`; cues MUST NOT overlap.
- **FR-021**: `POST /api/matches/{match_id}/recap` MUST return the recap (200), 404 `match_not_found`, 409 `no_moments_yet`
  (no eligible insight) or 422 `invalid_prefs`; responses are cached by `(content_state_version, mode, language,
  pinned_player_id)` where `content_state_version` = max `state_version` over the moments and bundles considered; the
  same key returns a byte-identical document; no model call occurs.
- **FR-022**: `recap_id` MUST be `recap-{match_id}-{pinned_player_id or "all"}-{mode}-{language}`.
- **FR-023**: `frontend/src/components/RecapPanel.tsx` MUST generate a recap for the current prefs, list items (rank, title,
  involvement badge), play them sequentially through `ReplayView` (controlled time, 1×) with lead-in slates and timed
  overlays driven by `frontend/src/replay/RecapSequencer.ts`, and offer **Download overlay JSON**.

### Key Entities

- **ViewerPrefs**: `{mode, language, pinned_player_id | null}` — per client (localStorage) and per connection (server).
- **Involvement**: `direct` | `off_ball` | `none` for a pinned player in a moment.
- **RankedMoment**: candidate moment + viewer rank + involvement.
- **Ranking (WS payload)**: `{pinned_player_id, entries: [{moment_id, rank, rank_score, pinned_involvement}]}`.
- **Recap / RecapItem / OverlayCue**: per `recap.schema.json`; segment layout derived from item windows.
- **Narrative catalog**: keyed templates per language with fan/analyst variants and `_meta.review`.
- **Glossary**: canonical English → Hindi term table with rationale and review status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Switching Fan↔Analyst and EN↔HI preserves numbers and player identities in 100% of rendered variants: the
  property test (≥ 200 generated slot sets per template, all templates) and the bundle check over every bundle produced
  for the three seed-42 scenarios report 0 violations.
- **SC-002**: In `demo_match` seed 42, pinning Blue 9 changes the top-ranked timeline moment and the
  generated recap includes the space-creation moment with `pinned_player_involvement = "off_ball"` (integration test and
  Playwright).
- **SC-003**: Recap JSON validates against `recap.schema.json` for 24/24 combinations (2 modes × 2 languages × {no pin,
  `blue-09`} × 3 scenarios).
- **SC-004**: Mode or language switch renders the new variant within 100 ms (p95 over 20 toggles in Playwright) with zero
  HTTP requests and zero model calls (scripted-client call count unchanged).
- **SC-005**: For 100% of bundles in the three scenarios, Fan body numbers ≤ Analyst body numbers, and Analyst view exposes
  ≥ 1 time window and ≥ 1 metric definition while Fan exposes no agent trace (component + e2e tests).
- **SC-006**: Hindi catalog: 100% key/placeholder parity, 0 Devanagari digits, 0 glossary-consistency violations, review
  status recorded ("internal review" unless a named reviewer exists).
- **SC-007**: 100% of generated overlay tracks have non-overlapping cues, each starting exactly 1500 ms after its segment
  start and ending within its segment.
- **SC-008**: A repeated recap request with unchanged content returns a byte-identical document from cache in ≤ 50 ms
  server time; a newly released insight produces a new document.

## Assumptions

- 004 releases all four variants per bundle and exposes the released, non-revoked bundles of a session (assumed
  `MatchSession.released_bundles()`; if 004 names it differently, only `api/routes_recap.py` and `api/ws.py` adapt).
- 003's `CandidateMoment.rank_score` is the base ranking score; `rank()` already orders moments without a pin.
- The hero seed contains at least one moment that outranks the space-creation moment without a pin and does not involve
  Blue 9 (e.g., an Amber press or a Blue 8 pass), so pinning visibly reorders the timeline; 002 owns this property.
- Player display names in metadata are "{Team} {shirt}" in English and "{टीम} {shirt}" in Hindi (ब्लू 9, एम्बर 4).
- No native-speaker or football-expert reviewer is currently named; reviews are recorded as "internal review".
- Prefs are not persisted server-side beyond the connection (no profiles, no Cosmos DB — constitution VII).
- The Producer's authority over recap content is exercised through its per-insight ModePlans; recap assembly itself is
  deterministic (constitution III).
