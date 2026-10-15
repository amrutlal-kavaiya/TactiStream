# CLI Contract — `tactistream-sim` (002)

Console script `tactistream-sim = tactistream.simulator.cli:app` (typer). Output on stdout; errors on stderr as
`error: <message>`, never a traceback for expected failures.

## `tactistream-sim generate`

```text
tactistream-sim generate --scenario SCENARIO --seed INT [--variant A] [--split dev] --out DIR [--force]
```

Writes `DIR/feed.jsonl` (one canonical `FeedEnvelope` per line: metadata, then events/frames by `session_clock_ms`, events
first at equal time) and `DIR/manifest.json` (canonical `GenerationManifest`). Prints:

```text
match_id=demo-blue-amber-001 events=9 frames=142 duration_ms=14100
feed_sha256=<64 hex>
wrote data/generated/hero/feed.jsonl data/generated/hero/manifest.json
```

The hero always has 9 events (kickoff, carry, 2 build-up passes, forward pass, carry, shot, out_of_play, period_end);
`frames = duration_ms / 100 + 1`. Duration shown is the nominal 14100 ms; seed jitter moves it by a few hundred ms, and the
exact value is frozen by the golden test.

| Exit | Meaning |
|---|---|
| 0 | written, validation passed |
| 2 | usage / `ConfigError` (unknown scenario, seed or variant outside its split, non-empty `--out` without `--force`) |
| 3 | `KinematicsError`, `IllegalTransition` or `validate_output` issues (printed `code record_id detail`, one per line); nothing written |

## `tactistream-sim list`

```text
scenario           dev variants  eval variants  seeds (dev | eval)
space_creation     A B C         D E F          1-9999 | >=10000
press_turnover     A B C         D E F          1-9999 | >=10000
switch_escape      A B C         D E F          1-9999 | >=10000
run_no_channel     A B C         D E F          1-9999 | >=10000
press_no_turnover  A B C         D E F          1-9999 | >=10000
switch_closed      A B C         D E F          1-9999 | >=10000
tracking_gap       A B C         D E F          1-9999 | >=10000
demo_match         A B C         -              1-9999 | -
```

`demo_match` is a development/demo program only (no eval variants).

## File compatibility

- `feed.jsonl` loads with 001's `transport/fixtures.load_fixture(path)` and validates line-by-line against
  `feed_envelope.schema.json`.
- `manifest.json` is for 008 evaluation and reviewers only. It is never published on a bus, never served by the API, never
  read by live-path modules (constitution II).
