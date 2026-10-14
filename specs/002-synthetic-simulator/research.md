# Research & Decisions: 002 Synthetic Simulator

## R1. Scripted keyframes + bounded followers (not agent-based simulation)

- **Decision**: Each scenario family is a deterministic script of beats (events with times) and keyframes for the few actors
  that make the pattern (passer, receiver, runner, follower, pressers, closer). Other players follow formation slots shifted
  with the ball through a velocity/acceleration-clamped follower with small Ornstein–Uhlenbeck jitter.
- **Rationale**: The product needs *specific*, testable tactical geometry (a lane that widens by ≥ 2.5 m) plus plausible
  background motion. Scripts make intent checkable; followers make bounds hold by construction.
- **Alternatives rejected**: Agent-based / physics simulation (days of tuning, intent not guaranteed); LLM-generated
  coordinates (non-deterministic, implausible, explicitly rejected by the build plan).

## R2. Trajectory interpolation

- **Decision**: C1 cubic Hermite splines with Catmull–Rom tangents through scripted keyframes on the 100 ms grid;
  `check_bounds` verifies max speed 9.5 m/s and max acceleration 6 m/s² on the unrounded track and raises `KinematicsError`.
- **Rationale**: Minimum-jerk segments with zero end velocity peak at 1.875·d/T speed and 5.77·d/T² acceleration — a 13.5 m run
  in 2.8 s would need 9.9 m/s² — so velocity-continuous splines are required. Failing loudly keeps scenario authors honest.
- **Alternatives rejected**: Silent clamping (positions drift from scripted event coordinates); linear segments (infinite
  acceleration at corners).

## R3. Randomness and determinism

- **Decision**: `numpy.random.Generator(PCG64(SeedSequence([seed, segment_index])))`; one sub-stream per program segment;
  NumPy pinned in `uv.lock`; positions rounded to 0.01 m at record creation; canonical JSON lines (sorted keys, compact
  separators, `ensure_ascii=False`); `published_ms` in files is `1792000000000 + session_clock_ms` (the replayer re-stamps it
  with real wall time at publish). Golden SHA-256s in `backend/tests/golden/simulator_hashes.json`; regenerating requires
  `TACTISTREAM_UPDATE_GOLDEN=1` and a `generator_version` bump if an existing config's output changes.
- **Rationale**: Per-segment sub-streams make `demo_match` segment 1 identical to standalone `space_creation` and keep
  segments independent when one is edited. Rounding absorbs last-bit libm differences.
- **Alternatives rejected**: Python `random` (separate generator, harder to sub-stream); wall-clock `published_ms` in files
  (breaks byte identity).

## R4. Validation tolerances

- **Decision**: Speed checked with 1-frame differences (+0.15 m/s), acceleration with a 200 ms second difference (+0.5 m/s²).
- **Rationale**: Rounding to 0.01 m gives ±0.005 m error; a 100 ms second difference amplifies that to ±2 m/s², which would
  make the check meaningless. 200 ms gives ±0.5 m/s². Strict bounds are enforced pre-rounding by `check_bounds`.

## R5. Event times on the 100 ms grid

- **Decision**: Simulator events occur on multiples of 100 ms so event coordinates equal the actor's frame position (up to
  rounding). This is a simulator convention, not a contract rule; 003 must tolerate off-grid events (nearest frame ± 50 ms).

## R6. Match IDs must not leak labels

- **Decision**: `sim-{sha256(canonical config)[:10]}` for all non-hero configs; hero presets `demo-blue-amber-001`
  (space_creation/42/A) and `demo-blue-amber-002` (demo_match/42/A).
- **Rationale**: The registry's `sim-{scenario}-{seed}` would expose the scenario label to agents through every record and
  tool payload (constitution II). Opaque IDs remain deterministic.
- **Cross-cutting**: Registry ID-format row needs updating (reported as a proposed cross-cutting change).

## R7. Structural evaluation variants

- **Decision**: Variants change focus team, period/attack direction, y-mirror, key-actor set, number of build-up passes,
  tempo, and (F) a decoy straight run. Dev = A–C, eval = D–F; seeds dev 1–9999, eval ≥ 10000; generator refuses mixing.
- **Rationale**: The build plan calls noise-only variation "a weak generalization test". D–F also exercise attack-direction
  normalization (period 2, Amber attacking) that dev never shows.

## R8. Seek semantics

- **Decision**: Forward seek publishes skipped records immediately as a burst; backward seek calls `on_rewind` (session clears
  state the same way `reset` does) then bursts from 0. The session suppresses per-record WS messages during a burst and sends
  one snapshot after the consumer has applied `SeekResult.last_record_id`.
- **Rationale**: Keeps the bus the only path into state (Fabric and live-state see the same records) and avoids flooding
  browsers with thousands of frames.
- **Alternatives rejected**: Applying records directly to `MatchState` (diverges from the live path); replaying at high speed
  (slow, floods WS).

## R9. Sessions are shared per config

- **Decision**: `SessionRegistry.get_or_create(scenario, seed, variant)` returns the existing session for an identical config;
  max 8 sessions, LRU eviction of viewer-less sessions, else 429.
- **Rationale**: Match IDs are deterministic per config, so two sessions with one ID would collide on `/ws/matches/{id}`.
  Shared playback matches a live broadcast and stays bounded on one replica (constitution VII).

## R10. Performance budget (record measurements here, task T058)

- Target: single family ≤ 0.5 s, `demo_match` ≤ 3 s on the Codespace (4 vCPU). Vectorize trajectories per player with NumPy.
- **Measured**: single family `____` ms (median of 5), `demo_match` `____` ms, hardware `____`.
