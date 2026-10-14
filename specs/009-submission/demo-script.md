# Demo Script — TactiStream, 115 seconds

Recording date: **25 Oct 2026 (IST)**. Source: the deployed app at `<APP_URL>/demo?seed=42` (never a local build or mock-up).
Target length **1:55**; hard maximum **1:59** (official rule: under two minutes). Narration in English, ~140 words per minute.

## Timeline (verbatim from the build plan)

| Time | Screen action | Narration intent |
|---|---|---|
| 0:00–0:08 | Show the shot, then the Why card | "The shot is obvious. The run that opened the space is easier to miss." |
| 0:08–0:30 | Rewind in 3D; highlight runner, defender and channel | Explain the invisible contribution using visible evidence |
| 0:30–0:43 | Expand the evidence drawer | Show factual measurements and the interpretation distinction |
| 0:43–0:58 | Change Fan to Analyst; switch to Hindi; pin the runner | Same facts, different useful experiences |
| 0:58–1:13 | Load an unseen seed or alternate sequence | Show the running system handles a second example |
| 1:13–1:28 | Trigger a labeled missing-data or timeout fixture | Show a blocked claim and a useful fallback |
| 1:28–1:45 | Generate recap and inspect timed overlay output | Connect the experience to a studio workflow |
| 1:45–1:55 | Show measured results and the live project link | State the product value and actual deployed stack |

## Shot list

| # | Time | Screen | Actions (exact) | On-screen must show | Prep |
|---|---|---|---|---|---|
| 1 | 0:00–0:08 | Match view, hero seed 42 | Recording starts ~1 s before the shot event; card "Space opened before the shot" slides in | Synthetic badge, match clock, card with "Interpretation" label | Load `/demo?seed=42` once before recording to warm the model; restart demo, start recording at session clock ≈ shot − 3 s |
| 2 | 0:08–0:30 | Why Mode 3D replay | Click **Why?**; replay 10 s window; pause once when the channel is widest | Runner highlight (`highlight_blue_09`), defender path, channel overlay (`show_channel_…`) | Camera preset "broadcast high" |
| 3 | 0:30–0:43 | Evidence drawer | Click **Evidence**; hover the metric row; point to "Fact" vs "Interpretation" tags | Event IDs, timestamps, coordinates, channel width value + unit, "Interpretation" label | Drawer opens on the metric tab |
| 4 | 0:43–0:58 | Same card, settings in top bar | Fan → Analyst (card gains metrics); EN → HI (same numbers); pin Blue 9 (timeline re-ranks) | Identical numbers in EN and HI; pinned badge; timeline order change | Hindi font loaded (check before recording) |
| 5 | 0:58–1:13 | Judge tools → Load another sequence | Click; new session `press_turnover` seed 10500 variant D; first card appears | New card text, Synthetic badge, different moment on timeline | Pre-warm this seed once on 25 Oct morning |
| 6 | 1:13–1:28 | Judge tools → Inject bad claim, then trace view | Click Inject bad claim before the next moment; when card appears open **Trace** | Rejected claim row with reason (e.g. `value_mismatch`), released card labelled fact/fallback, "Fixture active" label | Know the moment timing for this seed |
| 7 | 1:28–1:45 | Recap panel | Click **Generate recap** (pinned Blue 9); open **Overlay JSON** tab; scroll 2 entries | Ranked playlist with Blue 9 off-ball item, timed overlay entries with `start_ms`/`end_ms`, evidence IDs | Recap for this match generated once beforehand to verify output |
| 8 | 1:45–1:55 | Evidence page, then URL bar | Top bar **Evidence**; hover the gates table; final frame shows live URL and repo URL as text overlay | Gates table with statuses and sample sizes; "Internal review" label; `APP_URL` and GitHub URL | Use the published report (`report_id` noted) |

## Narration (≈ 250 words)

1. **0:00–0:08** — "The shot is obvious. The run that opened the space is easier to miss."
2. **0:08–0:30** — "TactiStream rewinds the last ten seconds on a 3D pitch. Blue 9 runs diagonally, the Amber defender goes with him, and
   the central channel widens. Every highlight comes from the synthetic tracking data — the model never invents a position."
3. **0:30–0:43** — "Open the evidence: event IDs, timestamps, coordinates and the measured channel width. Facts are checked against the
   match snapshot; the tactical reading is labelled as interpretation."
4. **0:43–0:58** — "Analyst mode adds the metrics. Hindi keeps the same numbers and names. Pin Blue 9, and the timeline and recap now rank
   his off-ball work."
5. **0:58–1:13** — "Here is a sequence the prompts were never tuned on: a pressing trap and a turnover. Same pipeline, new evidence, a new
   card — streamed live through Azure Event Hubs."
6. **1:13–1:28** — "Now we break it on purpose. The Analyst is fed a bad claim with an inflated number. The Verifier rejects it against the
   metric, and the viewer gets a factual card instead. Model timeouts fall back the same way, inside eight seconds."
7. **1:28–1:45** — "For a producer, one click builds a recap: a ranked replay playlist, short text and a timed overlay track in JSON, ready
   for a graphics system, with every line linked to evidence."
8. **1:45–1:55** — "Measured latency, support rate and failures are on the Evidence page, including where we fall short. TactiStream — see
   the move behind the moment."

Rules: narration states no measured number unless it is read from the published report on screen; the 8-second deadline is a design
constant and may be said. If 008 narrowed the multi-agent claim, line 6 stays (it shows Verifier behaviour) but no superiority claim is
added anywhere. If Event Hubs is not deployed at recording time (stop rule), drop "streamed live through Azure Event Hubs".

## Recording checklist

- [ ] Deployed app healthy (`tactistream-smoke deployed` passed within the last hour); uptime workflow green
- [ ] Browser: fresh profile, no extensions visible, bookmarks bar hidden, zoom 100%, window exactly 1920×1080 content area
- [ ] Notifications off (OS, chat, mail); clock/taskbar hidden or neutral
- [ ] Cursor visible and enlarged/highlighted; clicks deliberate, no hunting
- [ ] No secrets on screen: no terminal, no `.env`, no Azure portal keys/connection strings, no inbox, no personal tabs
- [ ] Model pre-warmed: run `/demo?seed=42` and `seed=10500` once, then Restart demo
- [ ] Hindi font renders (no tofu boxes) on the card
- [ ] Recording: 1920×1080, 30 or 60 fps, H.264 MP4, audio 48 kHz, mic level checked
- [ ] Each beat within ±3 s of the timeline; total 1:50–1:59 (`ffprobe -show_entries format=duration`)
- [ ] English captions (`demo.srt`) created from the narration and synced; burned in or uploaded with the video
- [ ] Final frame shows live URL and repository URL as readable text for ≥ 3 s
- [ ] Watched once end-to-end at 1×; one other person (or the builder after a 2-hour break) can name the three agents and the evidence check
- [ ] Uploaded per organizer instructions; plays logged out; link recorded in `submission-checklist.md`

## Backup recording

- Record a second complete take on 25 Oct after the final one, from the same deployed app.
- Title and first frame read: **"Backup recording — TactiStream deployed app, recorded 25 Oct 2026"**.
- Used only if the live app is unavailable during a presentation or judging; any cached replay shown live is labelled "Cached replay".
- Stored in the same hosting location as the main video, linked from README under "If the live demo is busy".

## Rehearsal (25 Oct, fresh session)

1. New browser profile, open README from GitHub (logged out) → follow only README links to `/demo?seed=42`.
2. Walk the judge guide path with a timer (SC-002 target ≤ 3 min).
3. Record any friction as an issue; fix only blockers (feature freeze), each with a test.
