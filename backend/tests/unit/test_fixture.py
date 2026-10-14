import json
import runpy
from pathlib import Path
from typing import Any

import pytest

from tactistream.contracts import validate
from tactistream.transport.fixtures import fixtures_dir, skeleton_fixture_path

REPO = Path(__file__).parents[3]
FIXTURE = REPO / "data" / "fixtures" / "skeleton.jsonl"
SCRIPT = REPO / "backend" / "scripts" / "make_skeleton_fixture.py"


@pytest.fixture(scope="module")
def lines() -> list[dict[str, Any]]:
    return [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines()]


def by_kind(lines: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [line for line in lines if line["kind"] == kind]


def test_every_line_is_a_valid_feed_envelope(lines: list[dict[str, Any]]) -> None:
    for line in lines:
        validate("feed_envelope.schema.json", line)
        assert "server_receipt_ms" not in line


def test_metadata_comes_first_and_matches_contract_example(lines: list[dict[str, Any]]) -> None:
    example = json.loads((REPO / "contracts/examples/match_metadata.json").read_text(encoding="utf-8"))
    assert lines[0]["kind"] == "metadata"
    assert lines[0]["payload"] == example
    assert len(by_kind(lines, "metadata")) == 1


def test_frame_indices_are_contiguous_with_all_players_visible(lines: list[dict[str, Any]]) -> None:
    frames = [line["payload"] for line in by_kind(lines, "frame")]
    assert [f["frame_index"] for f in frames] == list(range(60))
    assert [f["session_clock_ms"] for f in frames] == [i * 100 for i in range(60)]
    for frame in frames:
        assert len(frame["players"]) == 22
        assert all(p["visible"] for p in frame["players"])
        assert frame["ball"]["visible"]


def test_event_sequences_are_contiguous(lines: list[dict[str, Any]]) -> None:
    events = [line["payload"] for line in by_kind(lines, "event")]
    assert [e["sequence"] for e in events] == [40, 41, 42, 43]
    assert [(e["event_id"], e["event_type"], e["session_clock_ms"]) for e in events] == [
        ("evt-0040", "kickoff", 0),
        ("evt-0041", "carry", 1500),
        ("evt-0042", "pass", 3000),
        ("evt-0043", "carry", 3900),
    ]


def test_pass_event_matches_data_model(lines: list[dict[str, Any]]) -> None:
    pass_event = next(line["payload"] for line in by_kind(lines, "event") if line["record_id"] == "evt-0042")
    assert pass_event["player_id"] == "blue-08"
    assert pass_event["recipient_id"] == "blue-11"
    assert pass_event["start_m"] == [58.1, 32.4]
    assert pass_event["end_m"] == [71.2, 28.0]
    assert pass_event["duration_ms"] == 900
    assert pass_event["outcome"] == "complete"


def test_ball_and_carriers_agree_with_events(lines: list[dict[str, Any]]) -> None:
    frames = {line["payload"]["session_clock_ms"]: line["payload"] for line in by_kind(lines, "frame")}

    def player(t: int, player_id: str) -> list[float]:
        return next(p["pos_m"] for p in frames[t]["players"] if p["player_id"] == player_id)

    assert player(1500, "blue-08") == [52.0, 33.0]
    assert player(3000, "blue-08") == [58.1, 32.4]
    assert frames[3000]["ball"]["pos_m"] == [58.1, 32.4]
    assert frames[3900]["ball"]["pos_m"] == [71.2, 28.0]
    assert player(3900, "blue-11") == [71.2, 28.0]
    assert frames[3500]["ball"]["pos_m"] == pytest.approx([58.1 + 13.1 * 5 / 9, 32.4 - 4.4 * 5 / 9], abs=0.01)


def test_events_sort_before_frames_at_equal_time(lines: list[dict[str, Any]]) -> None:
    timed = [(line["payload"]["session_clock_ms"], line["kind"]) for line in lines[1:]]
    order = {"event": 0, "frame": 1}
    assert timed == sorted(timed, key=lambda item: (item[0], order[item[1]]))


def test_generator_script_reproduces_committed_fixture() -> None:
    build_lines = runpy.run_path(str(SCRIPT))["build_lines"]
    assert build_lines() == FIXTURE.read_text(encoding="utf-8").splitlines()


def test_fixtures_dir_defaults_to_repo_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TACTISTREAM_DATA_DIR", raising=False)
    assert fixtures_dir() == REPO / "data" / "fixtures"


def test_fixtures_dir_honours_data_dir_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TACTISTREAM_DATA_DIR", str(tmp_path))
    assert fixtures_dir() == tmp_path / "fixtures"
    assert skeleton_fixture_path() == tmp_path / "fixtures" / "skeleton.jsonl"
