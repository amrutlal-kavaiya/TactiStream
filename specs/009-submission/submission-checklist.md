# Submission Checklist — Microsoft + Premier League: Inside the Game

Organizer rules: [OFFICIAL RULES](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md). Innovation
Studio instructions and later organizer updates override everything below. All times IST unless marked PT.

## Key dates

| Date | Deadline / work | Status |
|---|---|---|
| **≤ 19 Oct** | Registration completed (closes **21 Oct 00:30 IST**; internal target "before 20 Oct") — confirmation saved | [ ] ref: `____` |
| 24 Oct | Feature freeze, UI polish, docs complete, fresh-clone run | [ ] |
| 25 Oct | Record 115-s demo + backup; fresh-session rehearsal | [ ] |
| 26 Oct | **Submit** and verify links (internal target) | [ ] submitted at `____` |
| 27 Oct | Buffer; final availability checks; no new features | [ ] |
| 28 Oct 12:29 IST | Official submission close | — |
| 26 Oct → 10 Nov PT | Judging access window (10 Nov 23:59 PT ≈ 11 Nov 13:29 IST); daily availability log below | [ ] |
| ≥ 12 Nov | Teardown allowed (`docs/operations.md`) | — |

## Official requirements (from the rules summary in the build plan)

- [ ] Data is synthetic and football-realistic; no real players, clubs or Premier League marks (Synthetic badge everywhere)
- [ ] New project created for this hackathon (repo history starts 13–14 Oct 2026)
- [ ] Public GitHub repository, OSI license file present
- [ ] Working judging experience: live URL + `/demo?seed=42`, available through 10 Nov PT
- [ ] Demo video under 2 minutes (target 1:55)
- [ ] Team of at most 4 members, all registered
- [ ] All materials in English (Hindi appears only as a product feature, explained in English)
- [ ] Category: **Best Multi-Agent System**
- [ ] Only permitted assets; `docs/permitted-assets.md` complete

## Submission fields

| Field | Value | Verified logged-out |
|---|---|---|
| Project name | TactiStream | — |
| Tagline | See the move behind the moment. | — |
| Category | Best Multi-Agent System | — |
| Repository URL | `https://github.com/<owner>/TactiStream` | [ ] |
| Live app URL | `<APP_URL>/demo?seed=42` | [ ] |
| Demo video URL | `____` | [ ] |
| Backup recording URL (if a field exists or in README) | `____` | [ ] |
| Team members (≤ 4) | `____` | — |
| Description | draft below (final numbers from `docs/results.md`, `report_id ____`) | — |

## Five equal-weight criteria → evidence

| Criterion | Evidence in repo | Evidence in demo / app |
|---|---|---|
| Technological Implementation | `docs/architecture.md` (deployed services only, model + region), `infra/` Bicep + `deploy.yml` OIDC, `contracts/schemas/`, simulator + golden tests, `docs/results.md` latency | Live app on Container Apps via Event Hubs; video 0:58–1:13; `/evidence` latency rows |
| Agentic Design & Innovation | `docs/agents.md` authority table, prompts, bounded workflow, output checks; 008 three-way + fixed-token comparison | Video 1:13–1:28 (rejected claim in trace view); Judge tools → Inject bad claim |
| Real-World Impact & Applicability | `docs/business.md` (first buyer, pilot design, value model); recap JSON contract `contracts/schemas/recap.schema.json` | Video 1:28–1:45 recap + timed overlay JSON |
| User Experience & Presentation | `docs/judge-guide.md`; Fan/Analyst, EN/HI, pinning; accessibility notes; fps result in `docs/results.md` | Video 0:00–0:58; `/demo?seed=42` zero-click start |
| Adherence to Hackathon Category | Three agents with distinct authority, shared state (snapshot, claim ledger, verdicts), recovery; `AgentTrace` in Eventhouse `AgentTraces` | Trace view; `/evidence` agent comparison (claim narrowed if 008 found no gain) |

## Submission description draft (≤ 250 words; fill `{…}` only from `docs/results.md`)

> **TactiStream turns a football event stream into a tactical story you can inspect, replay, and personalize.**
>
> A deterministic simulator produces a synthetic, football-realistic match (fictional Blue and Amber teams) as separate event and
> 10 Hz tracking streams. The feed flows through Azure Event Hubs into a FastAPI match service on Azure Container Apps that keeps live
> state and computes explainable metrics with event and frame references.
>
> Three agents built with Microsoft Agent Framework on a Microsoft Foundry model have distinct authority: the **Analyst** proposes at most
> two evidence-referenced claims using read-only, as-of tools; the **Verifier** approves, revises once, or rejects each claim against the
> evidence; the **Producer** adapts only approved claims for Fan or Analyst mode in English or Hindi. Deterministic output checks then
> reject any new number, name, unit or annotation. On timeout or failure, viewers get a factual template within the 8-second deadline.
>
> Why Mode replays the moment on a simplified 3D pitch with the runner, defender and opening channel highlighted, and every claim opens to
> its evidence. Recaps export a ranked playlist and a timed overlay JSON a studio graphics system could consume. {Fabric sentence only if
> deployed: "Fabric Eventstream and Eventhouse keep the durable record and evaluation queries."}
>
> Measured on {n} held-out synthetic scenarios: fast overlay p95 {x} s, narrative p95 {y} s (timeouts {t}), {s}% supported claims in an
> internal review of {k} claims, and a three-way comparison against a deterministic summary and a single agent{, with the multi-agent claim
> narrowed where it showed no gain}. Results describe this controlled synthetic environment, not professional-match accuracy. There is no
> official Premier League integration.

Review before submitting:

- [ ] Every `{…}` replaced with values from `docs/results.md` (same `report_id` as `/evidence`)
- [ ] No claim of official Premier League integration, production accuracy, customer validation, forecasting or xG
- [ ] Services named are exactly those in `docs/deployment-inventory.json`

## Link verification (26 Oct, after submitting)

| Check | Device / network | Result | Time |
|---|---|---|---|
| Repo opens logged out, README renders, links work | phone on mobile data | [ ] | |
| `/demo?seed=42` reaches hero card with zero clicks | second laptop, different network | [ ] | |
| Video plays logged out, captions available | phone | [ ] | |
| `/evidence` shows the published `report_id` | second laptop | [ ] | |
| Submission confirmation saved (screenshot/email, reference `____`) | — | [ ] | |

## Availability log (26 Oct → 10 Nov PT)

Daily uptime workflow (007) plus a manual `/demo?seed=42` check every 3 days and on 10 Nov.

| Date (IST) | Uptime workflow | Manual `/demo` | Notes / incident |
|---|---|---|---|
| 26 Oct | [ ] | [ ] | |
| 27 Oct | [ ] | [ ] | |
| 28 Oct | [ ] | | |
| … one row per day through 11 Nov | | | |

## Optional export (US5) decision

- [ ] `tactistream-eval gates-check` result on 24 Oct: `____` → US5 **started / skipped (gate: ____)**
