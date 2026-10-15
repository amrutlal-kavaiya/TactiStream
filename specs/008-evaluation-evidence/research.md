# Research & Decisions: 008 Evaluation Evidence

## R1. Held-out design

- **Decision**: 30 held-out scenarios = 18 positives (3 families × variants D/E/F × 2 eval seeds) + 9 negatives (3 negatives ×
  D/E/F) + 3 missing-data (`tracking_gap` × D/E/F). Variants D–F change scenario **structure** (002), not only seeds, per the
  build plan ("merely changing random numbers in the identical scripted play is a weak generalization test"). Dev set (seeds 1–9999,
  variants A–C, ≥ 12 scenarios) is the only set used for prompt/template iteration and for deriving the fixed token budget.
- **Run hygiene**: held-out runs are executed after prompts are frozen for the day; every held-out run id is listed in the report;
  the report uses the latest complete run per config and discloses the count.
- **Alternatives rejected**: 100+ scenarios (review capacity is the bottleneck, not generation); random split of one pool (lets
  dev-tuned structures leak into held-out).

## R2. Freezing and label isolation

- **Decision**: Configs receive only `FrozenMoment` objects. Labels go to `eval/labels/`. Match ids are rewritten to
  `eval-{scenario_id}` because registry ids `sim-{scenario}-{seed}` would reveal the family. A label-leak test scans frozen files for
  family names, negative names, `tracking_gap`, `variant`, `expect`, and manifest keys. The runner test makes `eval/labels/`
  unreadable (`chmod 000` in a temp copy) and still completes.
- **Determinism**: canonical JSON (`sort_keys=True`, `separators=(",", ":")`, floats as produced by the simulator's fixed rounding);
  no timestamps inside frozen inputs; manifest holds SHA-256s.

## R3. Score definitions

| Score | Population | Numerator | Notes |
|---|---|---|---|
| Useful coverage | positive scenarios | scenarios with ≥ 1 released interpretation claim whose template is in the family's list | reviewed variant additionally requires label supported |
| False-explanation rate | negative scenarios | scenarios with a released interpretation claim from the paired positive family's template list | lower is better |
| Abstention correctness | missing-data scenarios | no released spatial interpretation **and** released event-level card | pure abstention on everything fails coverage |
| Check pass | released packets | packets passing `check_packet` re-run against the frozen snapshot | gate requires 100% |
| Support | reviewed atomic claims | supported | denominator includes unclear (conservative) |
| Recovery | injected records | released supported/verified card or fallback template within deadline, with no released bad value | |

Coverage is always shown beside support so universal abstention cannot look like success (constitution VI).

## R4. Statistics

- **Decision**: Wilson score 95% intervals for every rate; Cohen's κ for two reviewers over 3 categories; latency percentiles by
  nearest-rank on the full sample (no interpolation, no trimming). "Gain" between configs means non-overlapping Wilson intervals on
  support or useful coverage; otherwise the report says "no measurable difference at this sample size".
- **Alternatives rejected**: bootstrap CIs (more code, little benefit at n ≈ 30–150); significance testing language (overclaims at this size).

## R5. Blind review

- **Decision**: Local FastAPI mini-app inside `tactistream.eval.review` bound to 127.0.0.1; items carry opaque ids; config mapping in
  `key.json` never served; per-reviewer seeded shuffle; stratified sample by config (equal quota, remainder by random fill); replay
  shown as a 2D top-down SVG/canvas animation from frozen frames (no scenario names, no 3D app link — the app URL would expose seed
  and scenario).
- **Claim text**: English analyst variant (most explicit); mode/language consistency is 006's concern and not re-reviewed here.
- **Expert labelling**: report label is `internal_review` unless a reviewer self-identifies as a football analyst/coach and is named
  in the report (with consent).

## R6. Live latency measurement

- **Decision**: Use the server-side measurement already defined (001 R10, 007 `LatencySample`): fast overlay = display ack received −
  envelope server receipt; narrative = insight display ack received − trigger event server receipt, including fallback cards. Load
  clients ack on receipt (no rendering), so their numbers are network + server time; one real browser viewer runs simultaneously and is
  reported separately as "browser display". All values are upper bounds (include ack return trip).
- **Load client location**: run from the builder's machine (named, region recorded) — closest to the judging experience; optionally
  repeat from a GitHub Actions runner and report both.
- **Alternatives rejected**: client-side clocks (skew); Locust/k6 (extra tooling for 10 connections).

## R7. Failure fixtures — expected outcomes (assertions in `test_failure_fixtures.py`)

| Fixture | Setup | Expected (asserted) |
|---|---|---|
| `missing_positions` | 002 `tracking_gap` scenario, seed 42 variant A | event card released; spatial moment → `narrative_status` `abstained` or `fallback` with `insufficient_tracking`; packet `claim_status = insufficient_data`, body equals catalog `status.insufficient_tracking` (en), labels include `partial_tracking`; related metric `status = unavailable`; no annotation for an invisible player |
| `late_events` | hero match; hold back the event that changes a released fact, deliver it 2 s late | `insight_revoked {reason: late_event_revision}` for the old version; then a new bundle with `insight_version + 1` or none; final pass counts equal the in-order run |
| `duplicated_events` | every envelope published twice, adjacent swaps | final `state_hash` equals clean run; exactly one bundle per moment; event list unique |
| `model_timeout` | `POST /fixtures {"inject":"model_timeout"}` | `narrative_status {fallback, timeout}` at ≤ deadline + 250 ms (FakeClock); `fallback_template` card released; ≥ 1 `event` message delivered while the model call is pending |
| `bad_claim` | `POST /fixtures {"inject":"bad_claim"}` | trace contains the bad claim with verdict `reject` or `revise` (reason `value_mismatch`) or check failure `unsupported_number`; no released packet contains the injected value; card is the repaired claim or fallback template |
| `reconnect` | close WS after seq K, reconnect with `resume {last_seq: K}` | fresh `snapshot`; later messages have `seq > snapshot.seq`; no duplicated event ids client-side; active insight id unchanged |
| `history_unavailable` | history store sleeping 3 s | tool returns `unavailable(timeout)`; moment released or fallback within deadline; no history-derived numbers in text |

## R8. Frame-rate capture

- **Decision**: Playwright (Chromium, headed, `--disable-gpu-vsync` **not** set) on the named demo machine; inject an rAF loop that records
  frame deltas during three replays of the hero window; report median fps, 5th-percentile fps (1000 / p95 delta) and frames > 50 ms.
  Machine details from `TACTISTREAM_DEMO_MACHINE`; browser version from `browser.version()`; viewport 1920×1080, DPR recorded.
- **Alternatives rejected**: CI headless capture (software rendering, unrepresentative); Chrome tracing (heavier, harder to explain).

## R9. Economics

- **Decision**: Measured: model calls and tokens per agent (usage returned by the model client), runner compute seconds, Event Hubs
  envelopes/bytes per match (counted by the publisher), Blob bytes (artifact store counters), container vCPU-seconds for the match
  duration (1 replica × vCPU × seconds), Fabric CU (manual reading from the Capacity Metrics app). Prices are inputs from
  `pricing.yaml` with source and date; costs are labelled "list-price estimate". No per-month extrapolation is presented as a forecast.

## R10. Fixed-total-token comparison

- **Decision**: `three_agent_fixed_tokens` uses the median total tokens per moment of `single_agent` on the dev set as a hard
  budget; the workflow must fall back when the next call would exceed it (004 `token_budget`). This answers "is it the extra
  tokens or the structure?" If 004 cannot honour a budget by 22 Oct, the config is reported as `not run` with the reason.
