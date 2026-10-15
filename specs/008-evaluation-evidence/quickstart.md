# Quickstart: 008 Evaluation Evidence

All commands run from `backend/` unless noted. CI-safe commands use `--model scripted`.

## 1. Smoke the pipeline offline (no Azure)

```bash
make eval-smoke     # freeze 3 held-out scenarios → run 4 configs (scripted) → score → report into a temp dir
```

## 2. Freeze inputs (once per simulator version)

```bash
uv run tactistream-eval freeze --set dev
uv run tactistream-eval freeze --set heldout
git add ../eval/frozen ../eval/labels     # frozen inputs and scorer labels are committed
```

## 3. Dev run → fixed token budget

```bash
uv run tactistream-eval run --config ../eval/configs/single_agent.yaml --set dev --model foundry
uv run tactistream-eval budget --from-run single_agent-dev-<ts> --config ../eval/configs/three_agent_fixed_tokens.yaml
```

## 4. Held-out runs (Foundry; ~30 scenarios × 4 configs)

```bash
for c in deterministic single_agent three_agent three_agent_fixed_tokens; do
  uv run tactistream-eval run --config ../eval/configs/$c.yaml --set heldout --model foundry --inject-every 5
done
uv run tactistream-eval score --run <four run ids>
```

## 5. Blind review

```bash
uv run tactistream-eval review build --runs <four run ids> --sample 150 --seed 7
uv run tactistream-eval review serve --review <review_id> --reviewer builder      # open http://127.0.0.1:8765
# optional second reviewer on the same set:
uv run tactistream-eval review serve --review <review_id> --reviewer reviewer2 --port 8766
uv run tactistream-eval score --run <four run ids> --review <review_id>
```

## 6. Live measurements

```bash
uv run pytest tests/integration/test_failure_fixtures.py --junitxml=../eval/results/fixtures-junit.xml
uv run tactistream-eval consistency --runs 20
# open the deployed app in a real browser on /?seed=42 before starting, then:
uv run tactistream-eval load --base-url "$APP_URL" --viewers 10 --seed 42 --duration-s 120
# on the named demo machine (frontend/):
TACTISTREAM_DEMO_MACHINE="demo-laptop; Intel i7-1260P; Iris Xe; 16 GB; Windows 11" BASE_URL="$APP_URL" npm run perf:fps
```

## 7. Report and publish

```bash
uv run tactistream-eval report --publish     # writes eval/results/latest/report.json and docs/results.md
git add ../eval/results ../docs/results.md && git commit -m "008: publish evaluation report <report_id>"
# push → deploy.yml rebuilds the image, /evidence serves the new report
curl -s "$APP_URL/api/evaluation/results" | jq '.report_id, [.gates[] | {gate_id, status}]'
```
