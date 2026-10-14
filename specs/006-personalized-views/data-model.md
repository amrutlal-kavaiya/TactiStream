# Data Model: 006 Personalized Views

Canonical shapes: `recap.schema.json` (unchanged), `ws_message.schema.json` (+ `ranking`, see
[contracts/ws-ranking.md](contracts/ws-ranking.md)), `insight_packet.schema.json`, `claim.schema.json`.

## Backend types

```python
# contracts/prefs.py  (mirrors ws PrefsMsg minus "type")
class ViewerPrefs(BaseModel):            # frozen, extra="forbid"
    mode: ViewerMode = "fan"
    language: Language = "en"
    pinned_player_id: PlayerId | None = None

# contracts/ws.py (addition)
class RankingEntry(BaseModel): moment_id: MomentId; rank: int; rank_score: float; pinned_involvement: Involvement
class RankingPayload(BaseModel): pinned_player_id: PlayerId | None; entries: list[RankingEntry]

# moments/ranking.py (additions; rank() keeps its 003 name and positional params)
Involvement = Literal["direct", "off_ball", "none"]
class EvidenceLookup(Protocol):
    def events_between(self, start_ms: int, end_ms: int) -> Sequence[MatchEvent]: ...
    def metric(self, metric_id: str) -> MetricResult | None: ...
@dataclass(frozen=True)
class RankedMoment:
    moment: CandidateMoment
    rank: int                            # 1-based viewer rank
    pinned_involvement: Involvement
def pinned_involvement(moment: CandidateMoment, player_id: PlayerId, lookup: EvidenceLookup) -> Involvement: ...
def rank(moments: Sequence[CandidateMoment], pinned_player_id: PlayerId | None = None, *,
         lookup: EvidenceLookup | None = None) -> list[CandidateMoment]: ...      # lookup required when pinned
def rank_for_viewer(moments: Sequence[CandidateMoment], prefs: ViewerPrefs,
                    lookup: EvidenceLookup) -> list[RankedMoment]: ...

# api/ws_hub.py (addition)
@dataclass
class ConnectionPrefs:
    prefs: ViewerPrefs | None = None     # None until the first prefs message

# narrative/consistency.py
NUMBER_RE = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
def extract_numbers(text: str, player_names: Iterable[str]) -> list[str]: ...           # digits inside player names excluded
def extract_player_ids(text: str, metadata: MatchMetadata, language: Language) -> list[PlayerId]: ...
def unify_mode_plans(output: ProducerOutput) -> ProducerOutput: ...
def check_bundle_consistency(bundle: InsightBundle, metadata: MatchMetadata) -> list[CheckFailure]: ...
    # codes: variant_missing, claims_differ, evidence_differ, status_differ, labels_differ, timing_differ,
    #        annotations_not_subset, numbers_differ_language, players_differ_language,
    #        numbers_not_subset_mode, players_not_subset_mode, devanagari_digit

# recap/timing.py
LEAD_IN_MS: Final = 1500; MIN_CUE_MS: Final = 2000; MAX_CUE_MS: Final = 6000; MAX_CUE_TEXT: Final = 200
@dataclass(frozen=True)
class Segment: start_ms: int; lead_in_end_ms: int; end_ms: int
def layout_segments(windows: Sequence[Window]) -> list[Segment]: ...
def layout_overlay_track(items: Sequence[RecapItem], packets: Sequence[InsightPacket]) -> list[OverlayCue]: ...

# recap/summary.py
def render_recap_summary(items: Sequence[RecapItem], prefs: ViewerPrefs, patterns: Mapping[str, MomentPattern],
                         statuses: Mapping[str, ClaimStatus], metadata: MatchMetadata) -> RenderedText: ...

# recap/builder.py
MAX_ITEMS: Final = 8
ELIGIBLE_STATUSES: Final = frozenset({"verified_fact", "interpretation_supported", "fallback_template"})
def build_recap(moments: Sequence[RankedMoment], bundles: Mapping[str, InsightBundle], prefs: ViewerPrefs,
                metadata: MatchMetadata, state_version: int) -> Recap: ...      # bundles keyed by moment_id
class NoMomentsYet(Exception): ...

# recap/cache.py
class RecapCache:
    def __init__(self, max_entries: int = 64) -> None: ...
    def get_or_build(self, key: tuple[int, ViewerMode, Language, PlayerId | None],
                     build: Callable[[], Recap]) -> bytes: ...
    def clear(self) -> None: ...
```

## Narrative catalog structure (`narrative/catalog/{en,hi}.json`)

```json
{
  "_meta": { "language": "hi", "catalog_version": "1.1",
             "review": { "status": "internal_review", "reviewer": "AB", "date": "2026-10-21" } },
  "interp.space_opened_by_run": {
    "fan": "{runner} की बिना गेंद की दौड़ ने पास के लिए जगह बनाने में मदद की।",
    "analyst": "डिफ़ेंडर {defender} {runner} की ओर खिसका, जबकि बीच का पासिंग चैनल {channel_gain.before} मीटर से {channel_gain.at_pass} मीटर तक चौड़ा हुआ। अगले आगे की ओर पास ने उसी जगह का इस्तेमाल किया।"
  },
  "recap.summary.pinned": { "fan": "{player} {count} अहम पलों में शामिल रहे।", "analyst": "…" }
}
```

Rules: identical key sets and placeholder names per key across languages; every key has `fan` and `analyst` (a key
may use the same string for both); placeholders reference slot names using the placeholder syntax of 001/004
`render.py` (the dotted component form above is illustrative; precision is defined per slot in `render.py`); Western
Arabic digits only (no literal numbers in templates other than inside placeholders).

## Frontend types / store additions

```ts
// store/matchStore.ts (prefs already {mode, language} from 001)
prefs: { mode: ViewerMode; language: Language; pinnedPlayerId: string | null };
ranking: RankingPayload | null;
recap: { status: "idle" | "loading" | "ready" | "empty" | "error"; recap?: Recap; forPrefs?: Prefs };
setMode(m): void; setLanguage(l): void; pin(playerId: string | null): void;
rankedMoments(): Array<{ moment: CandidateMoment; rank: number; involvement: Involvement }>;

// store/prefsStorage.ts
export function loadPrefs(): Prefs; export function savePrefs(p: Prefs): void;   // key "tactistream.prefs.v1"

// replay/RecapSequencer.ts
export interface RecapPosition { index: number; phase: "lead_in" | "replay" | "done"; replayTimeMs: number | null; cue: OverlayCue | null }
export class RecapSequencer {
  constructor(recap: Recap, opts?: { leadInMs?: number });
  get durationMs(): number; segments(): Array<{ start: number; leadInEnd: number; end: number }>;
  play(): void; pause(): void; seek(tMs: number): void; tick(dtMs: number): void;
  position(tMs?: number): RecapPosition; subscribe(l: (p: RecapPosition) => void): () => void;
}
```

## State transitions

```text
Prefs change (client):  setMode/setLanguage/pin → store → savePrefs → socket.sendPrefs → (server) ranking message
Connection prefs:       none --prefs--> set --prefs--> set' ; on close: discarded
Recap panel:            idle --Generate--> loading --200--> ready --Play--> playing (sequencer) --end--> ready
                                         loading --409--> empty
                        ready --prefs change--> ready (stale badge, "Regenerate")
Bundle release (004+006): producer output --unify_mode_plans--> render 4 variants --check_packet ×4--> check_bundle_consistency
                          ok → insight broadcast ; fail → narrative_status fallback (output_check_failed)
```
