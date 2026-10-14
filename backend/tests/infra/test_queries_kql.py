"""Static checks for `infra/appinsights/queries.kql` (FR-021); runs without the az CLI."""

import re
from pathlib import Path

QUERIES = Path(__file__).parents[3] / "infra" / "appinsights" / "queries.kql"

FR_021 = {
    "FastOverlayP95",
    "NarrativeP95",
    "FallbackByReason",
    "TokensByAgent",
    "TraceById",
    "RequestsAndFailures",
    "HistoryQueryHealth",
}
ALLOWED_TABLES = {"traces", "requests", "dependencies", "customMetrics", "exceptions"}
KNOWN_TABLES = ALLOWED_TABLES | {
    "pageViews",
    "customEvents",
    "availabilityResults",
    "performanceCounters",
    "browserTimings",
    "AppTraces",
    "AppRequests",
    "AppDependencies",
    "AppMetrics",
    "AppExceptions",
}
NAME = re.compile(r"^// name: (\w+)\s*$", re.MULTILINE)
IDENTIFIER = re.compile(r"[A-Za-z_]\w*")


def blocks() -> dict[str, str]:
    text = QUERIES.read_text(encoding="utf-8")
    parts = NAME.split(text)
    names, bodies = parts[1::2], parts[2::2]
    assert len(names) == len(set(names)), "duplicate query names"
    return dict(zip(names, bodies, strict=True))


def code_lines(body: str) -> list[str]:
    return [line.strip() for line in body.splitlines() if line.strip() and not line.strip().startswith("//")]


def tables(body: str) -> set[str]:
    found: set[str] = set()
    for line in code_lines(body):
        if line.startswith(("|", "let ", ")")):
            continue
        first = IDENTIFIER.match(line)
        if first and first.group(0) != "union":
            found.add(first.group(0))
    for union in re.finditer(r"\bunion\b([^|]*)", body):
        found.update(t for t in IDENTIFIER.findall(union.group(1)) if t in KNOWN_TABLES)
    found.update(t for t in IDENTIFIER.findall(body) if t in KNOWN_TABLES)
    return found


def test_every_fr_021_query_is_present() -> None:
    assert set(blocks()) == FR_021


def test_every_block_is_non_empty() -> None:
    for name, body in blocks().items():
        assert code_lines(body), name


def test_blocks_reference_only_application_insights_tables() -> None:
    for name, body in blocks().items():
        referenced = tables(body)
        assert referenced, name
        assert referenced <= ALLOWED_TABLES, (name, referenced - ALLOWED_TABLES)


def test_latency_queries_use_per_sample_logs_with_percentiles() -> None:
    for name in ("FastOverlayP95", "NarrativeP95"):
        body = blocks()[name]
        assert 'message == "tactistream.latency"' in body, name
        assert "percentiles(todouble(customDimensions.value_ms), 50, 95)" in body, name
        assert "count()" in body, name


def test_trace_by_id_has_a_substitutable_trace_id() -> None:
    body = blocks()["TraceById"]
    assert 'let trace_id = "<id>";' in body
    assert "operation_Id" in body
