# Quickstart: 004 Agent Workflow

## Offline (scripted agents, no Azure)

```bash
cp .env.example .env
# in .env:
#   TACTISTREAM_AGENTS=scripted
#   TACTISTREAM_AGENT_SCRIPTS=data/fixtures/agent_scripts/demo-blue-amber-001.json
#   TACTISTREAM_DEMO_FIXTURES=true
#   TACTISTREAM_TRACE_DIR=data/traces
make dev
```

Open http://localhost:5173 → **Start demo match**. Expected after the shot (~46 s session time):

- Stage indicator: Analysing… → Verifying… → Producing… → Checking…, then the card
  "Space opened before the shot" / "Blue 9's run helped create room for the pass." with **Interpretation** and **Synthetic** labels.
- Analyst mode shows "…the passing channel widened by 3.4 m…"; Hindi keeps 3.4 and the player identities.
- **How was this made?** opens the Agent trace tab: Analyst → Verifier checks → Verifier → Producer → Release checks.

Failure fixtures (labelled "Demo fixture"):

1. Reset, press **Inject bad claim**, Play → trace shows a **Blocked claim** (Wrong claim type, Value differs from
   measurement, Claims more than the data shows) and the revised claim; the card shows only approved text.
2. Reset, press **Inject model timeout**, Play → card "Blue 11 took a shot: on target." with **Facts only** within 8 s.
3. Start the 002 missing-tracking scenario (`POST /api/sessions` with the scenario name defined in 002) → "Insufficient
   tracking for this explanation." with the fact sentence; the trace shows only the gate step and no model calls.

## Live Foundry

```bash
export TACTISTREAM_AGENTS=foundry FOUNDRY_PROJECT_ENDPOINT=… FOUNDRY_MODEL_DEPLOYMENT=…
az login
make dev
cd backend && uv run pytest -m live tests/live/test_foundry_agents.py -s   # prints outcome, per-role latency, tokens
```

Record the 5-run results in `research.md` R7 (task T073).

## Tests

```bash
cd backend && uv run pytest tests/unit tests/integration -k "agent or workflow or narrative or trace or checks or catalog"
cd frontend && npm test && npx playwright test tests/e2e/agents.spec.ts
```

## Inspect a trace

```bash
curl -s localhost:8000/api/matches/demo-blue-amber-001/traces/<trace_id> | jq '.steps[] | {role, attempt, status, latency_ms}'
```
