# Research & Decisions: 003 Live State & Metrics

## R1. Reorder window on a monotonic clock

- **Decision**: Hold out-of-order events up to 500 ms measured on the injected monotonic `Clock` (FakeClock in tests), then
  release in order and flag the gap; frames are never held (applied when newer, stored when late).
- **Rationale**: Events drive moments and must be ordered; frames arrive at 10 Hz and holding them adds latency for no gain.
  Monotonic time keeps the window correct at 2× playback and immune to wall-clock jumps.
- **Alternatives rejected**: Holding by session time (wrong under pause/speed changes); infinite wait for missing sequences
  (one lost event would stall the match).

## R2. Late data → revision, final state is order-independent

- **Decision**: Late events and late frames are applied (never dropped); `state_version` counts accepted records; moments are
  a pure function of the snapshot and are re-detected on revisions; diffs ignore `state_version`. `metric_state_hash` excludes
  `state_version` so it measures content.
- **Rationale**: This makes replay consistency a provable property: same multiset of unique records ⇒ same final snapshot ⇒
  same moments and metrics. Revocation keeps the UI honest in between.
- **Alternatives rejected**: Dropping late records (state then depends on delivery timing); incremental metric patching
  (hard to prove equal to full recompute).

## R3. Pressure proxy

- **Decision**: `P = (100/3)·Σ exp(−d_i/2.5)` over the 3 nearest *visible* opponents; unavailable if the carrier is invisible
  or fewer than 10 of 11 opponents are visible.
- **Rationale**: Build plan formula; the 10/11 rule prevents an invisible nearby defender from producing a falsely low
  score ("return unavailable rather than a reassuring low score"). Reference values: (1, 2, 3 m) → 47.4; (5, 7.5, 10 m) → 6.8;
  (0, ∞, ∞) → 33.3; max 100.
- **Press threshold 35.0**: three defenders at ≈ 1.5/2.5/3.5 m score 38.8; one defender at 1 m alone scores 22.3, so a single
  closer cannot trigger a "press". 002 press scenarios target ≥ 40 for margin.

## R4. Attack-direction normalization by 180° rotation

- **Decision**: For a team attacking −x, `(x, y) → (105 − x, 68 − y)`.
- **Rationale**: Rotation preserves handedness (a run to the attacker's left stays left), unlike mirroring x only. Distances
  are invariant, which hypothesis tests assert.

## R5. Channel and separation use rounded components

- **Decision**: Round `clearance_before_m` / `clearance_at_pass_m` to 0.1 m first and set `value` to their difference.
- **Rationale**: The Analyst drawer and output checks (001 R9) compare displayed numbers; `5.3 − 1.9` must equal the shown `3.4`.

## R6. Shot-anchored space creation

- **Decision**: A shot whose 8–12 s look-back window contains a qualifying space pass becomes the `space_creation` moment
  (trigger = shot, metrics anchored on the pass), matching `contracts/examples/candidate_moment.json` (trigger `evt-0045`,
  metrics `-0042`). A qualifying pass without a shot within 12 s becomes its own moment after settling.
- **Rationale**: The demo card is "Space opened before the shot"; anchoring on the shot avoids emitting a pass moment and then
  superseding it seconds later (card churn).

## R7. Tracking coverage definition

- **Decision**: Coverage = share of expected window frames in which every involved player is visible and each team has
  ≥ 10 visible players.
- **Rationale**: With "involved players only", `tracking_gap` would score 1.0 when the hidden runner was never identified as
  involved. Requiring near-complete team visibility makes hidden defenders count. 004 (abstain < 0.8) and 005 (409 < 0.6)
  thresholds work unchanged.

## R8. Full checkpoints + raw archive

- **Decision**: Each checkpoint is the full state (≈ 3–4 MB for `demo_match`), written in the background every 100 records /
  10 s, latest 3 kept; every received envelope (incl. duplicates and invalid) is appended to the archive; restore = latest
  checkpoint + archive tail through the Ingestor (dedupe makes overlap harmless). Keys follow 007's Blob routing
  (`checkpoints/…`, `feed-archive/…`).
- **Rationale**: Simplest correct recovery for one match on one replica; incremental snapshots are unnecessary at this size.
- **Alternatives rejected**: Event Hubs checkpoint store (001 R7 starts consumers at `@latest`); Cosmos DB (constitution VII).

## R9. Hub sequence after restore

- **Decision**: The restored `WsHub` starts at `ws_head_seq + 10000`.
- **Rationale**: Messages sent between the last checkpoint and the crash (≤ 100 records, a few messages each) had seq values
  above the stored head; jumping 10,000 keeps seq strictly increasing for reconnecting clients, who replace state on snapshot.

## R10. Contribution metric IDs

- **Decision**: Per-player IDs `metric-contribution-{seq:04d}-{player_id}`; needs a backwards-compatible `MetricId` pattern
  extension (minor schema bump). Until accepted, contribution is computed (tests, 006 integration) but not indexed or broadcast.
- **Alternatives rejected**: One table-shaped result with player-keyed components (narrative slots reference a metric ID,
  not a component); numeric encoding of the player into the sequence (unreadable).

## R11. Measurements (record here, task T074)

- Cold full recompute on final `demo_match` snapshot: `____` ms (target < 1000). Ingest throughput: `____` records/s
  (target ≥ 2000). Restore `demo_match`: `____` ms (target < 2000). Hardware: `____`.
