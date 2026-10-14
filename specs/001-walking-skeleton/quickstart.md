# Quickstart: 001 Walking Skeleton

## Prerequisites

- uv ≥ 0.5, Node 22, Azure CLI (`az login` done) for the smoke tests only.

## Local, no Azure

```bash
cp .env.example .env            # defaults: TACTISTREAM_BUS=memory, TACTISTREAM_AGENTS=off
make install                    # uv sync (backend) + npm ci (frontend) + playwright install --with-deps chromium
make dev                        # API on :8000, Vite on :5173 (proxy /api and /ws to :8000)
```

`playwright install --with-deps` installs Chromium's system libraries through the OS package manager, so on Linux it
asks for `sudo` (passwordless in Codespaces). uv downloads Python 3.12 itself if it is not installed.

Optional settings (`.env` or the shell):

- `TACTISTREAM_DATA_DIR` — directory holding `fixtures/skeleton.jsonl`; default `<repo>/data`. If the fixture is missing,
  `POST /api/sessions` returns 422 `invalid_scenario`.
- `TACTISTREAM_STATIC_DIR` — built frontend the API serves at `/`; default `<repo>/frontend/dist`, mounted only if the
  directory exists. `make dev` does not need it (Vite serves the UI on :5173); `make e2e` points it at a fresh build.

Open http://localhost:5173 → **Start demo match**. Expected within ~3 s:

- Synthetic badge in the top bar, session clock running.
- Event rows: kickoff, carry, pass, carry.
- Card: "Blue 8 played a forward pass to Blue 11 (13.1 m forward)." with evidence chips `evt-0042`, `metric-forward_progress-0042`.
- Clicking `evt-0042` opens the drawer with the raw event.

## Tests

```bash
make test        # backend pytest (non-live) + frontend vitest
make e2e         # Playwright smoke against `make dev`-equivalent server
make contracts   # validate examples, regenerate TS types, fail on drift
```

## Azure smoke (day one)

```bash
export FOUNDRY_PROJECT_ENDPOINT=…  FOUNDRY_MODEL_DEPLOYMENT=…
export EVENTHUBS_FULLY_QUALIFIED_NAMESPACE=….servicebus.windows.net EVENTHUBS_NAME=tactistream-feed
cd backend
uv run tactistream-smoke foundry     # prints deployment, region, latency_ms, tokens, validated JSON
uv run tactistream-smoke eventhubs   # prints record_id match and round_trip_ms
```

Record the printed values in `specs/001-walking-skeleton/research.md` (R5, R7).

## Run against Event Hubs locally

```bash
TACTISTREAM_BUS=eventhubs make dev
```
