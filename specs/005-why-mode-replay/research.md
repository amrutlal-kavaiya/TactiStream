# Research & Decisions: 005 Why Mode Replay

Each decision records what was chosen, why, and what was rejected. Items marked **Record** are filled in by the
named task with observed values (measurements, not open design questions).

## R1. 3D stack and version pinning

- **Decision**: `three` + `@react-three/fiber` 9.x (React 19 support) + `@react-three/drei` 10.x, installed with
  `npm install --save-exact`; `@types/three` matching the `three` minor. Only drei helpers used: `Text` (troika SDF
  labels), `Line`, `OrthographicCamera` is not used (perspective presets only).
- **Rationale**: Declarative scene in React, shared store, instanced meshes are easy; the constitution names R3F.
- **Alternatives rejected**: raw three.js imperative scene (harder to test, duplicates React state wiring); Babylon.js
  (heavier, not in constitution).
- **Record** (T001): `three` `____`, `@react-three/fiber` `____`, `@react-three/drei` `____`, `@react-three/test-renderer` `____`.

## R2. Testing 3D without WebGL

- **Decision**: Keep behaviour in pure TS modules (`coords`, `frameSource`, `annotationGeometry`, `cameraPoses`,
  `ReplayController`) tested with Vitest; test the R3F scene graph with `@react-three/test-renderer` (no WebGL needed)
  for instance counts, labels and annotation meshes; mock `PitchScene` in DOM component tests (`ReplayView`,
  `MainSurface`); verify real rendering only in Playwright (chromium with SwiftShader in CI).
- **Alternatives rejected**: `jest-webgl-canvas-mock` (brittle, no scene semantics); screenshot diffing (flaky across GPUs).

## R3. Where annotation geometry is computed

- **Decision**: Server-side, deterministic, in `moments/scene.py`; the client only interpolates between supplied
  keyframes/frames.
- **Rationale**: Constitution I/III — the model supplies IDs, never coordinates; one golden test proves provenance;
  the client cannot drift from metric values.
- **Alternatives rejected**: client-side computation from frames (duplicated geometry in TS, risk of disagreeing with
  metrics); Producer-supplied geometry (forbidden).

## R4. Interpolation and gaps

- **Decision**: Linear interpolation only between consecutive frames ≤ 150 ms apart where the entity is visible in
  both. Nothing drawn across invisibility or frame gaps.
- **Rationale**: "All visible positions come from supplied or synthetic tracking"; 10 Hz linear interpolation is
  visually smooth at 1× and 0.5× and introduces no invented trajectory beyond a straight chord between two samples.
- **Alternatives rejected**: Catmull-Rom splines (overshoot invents positions); holding last position across gaps
  (displays a stale position as current).

## R5. Replay transport

- **Decision**: One REST call per moment (`GET …/replay/{moment_id}`), gzip, cached server- and client-side.
- **Rationale**: ≤ 121 frames is small (~150 KB raw, ~25 KB gzip); avoids streaming complexity on the WebSocket.
- **Alternatives rejected**: WebSocket streaming of historical frames (mixes live and historical seq semantics).

## R6. Insufficient-tracking threshold

- **Decision**: 409 when `tracking_coverage < 0.6` or a required spatial metric is `unavailable/insufficient_tracking`;
  otherwise replay with `partial_tracking` badge.
- **Rationale**: Metrics already decide whether spatial claims are computable (003); the coverage floor prevents a
  mostly empty pitch being presented as an explanation. 0.6 is a prototype parameter, documented in `docs/metrics.md`
  (008) and covered by fixture tests on both sides of the threshold.

## R7. Performance measurement

- **Decision**: Dev-only FPS overlay + `frontend/scripts/capture-fps.mjs` (Playwright, headed or headless GPU flag)
  writing JSON to `eval/results/fps/`. 005 records a development-machine figure; 008 measures on the named demo machine.
- **Record** (T061): machine `____`, GPU `____`, browser `____`, duration `____ s`, mean fps `____`, p5 fps `____`.
- **Record** (T024): replay endpoint p95 over 20 local requests: `____ ms`.
