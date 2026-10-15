import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from tactistream.simulator import io
from tactistream.simulator.config import SimulationConfig
from tactistream.simulator.engine import simulate
from tactistream.simulator.io import BASE_PUBLISHED_EPOCH_MS, canonical_line, to_envelopes, write_output
from tactistream.simulator.manifest import GenerationManifest
from tactistream.transport.fixtures import load_fixture
from unit.simulator.factories import make_simulation_output


def test_canonical_line() -> None:
    assert canonical_line({"b": 1, "a": [1.0, 2]}) == b'{"a":[1.0,2],"b":1}\n'
    assert canonical_line({"name": "ब्लू"}) == '{"name":"ब्लू"}\n'.encode()


def test_envelope_order_and_published_ms() -> None:
    envelopes = to_envelopes(make_simulation_output())
    assert envelopes[0].kind == "metadata"
    assert envelopes[0].published_ms == BASE_PUBLISHED_EPOCH_MS
    keys = [(getattr(e.payload, "session_clock_ms", 0), 0 if e.kind == "event" else 1) for e in envelopes[1:]]
    assert keys == sorted(keys)
    assert [e.record_id for e in envelopes[1:4]] == ["evt-0001", "frm-000000", "frm-000001"]
    at_600 = [e.record_id for e in envelopes if getattr(e.payload, "session_clock_ms", -1) == 600]
    assert at_600 == ["evt-0002", "frm-000006"]
    for e in envelopes[1:]:
        assert e.published_ms == BASE_PUBLISHED_EPOCH_MS + e.payload.session_clock_ms  # type: ignore[union-attr]
        assert e.match_id == "demo-blue-amber-001"


def test_write_output_round_trips_through_load_fixture(tmp_path: Path) -> None:
    output = make_simulation_output()
    written = write_output(output, tmp_path / "out")
    feed = written.feed_path.read_bytes()
    assert written.feed_sha256 == hashlib.sha256(feed).hexdigest()
    assert load_fixture(written.feed_path) == to_envelopes(output)
    manifest = json.loads(written.manifest_path.read_text(encoding="utf-8"))
    assert manifest["segments"][0]["key_event_ids"] == {"forward_pass": "evt-0003"}
    assert written.manifest_path.read_text(encoding="utf-8") == output.manifest.to_canonical_json() + "\n"


def test_write_output_refuses_non_empty_dir_without_force(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "other.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_output(make_simulation_output(), out)
    assert not (out / "feed.jsonl").exists()
    written = write_output(make_simulation_output(), out, force=True)
    assert written.feed_path == out / "feed.jsonl"
    assert (out / "manifest.json").exists()
    write_output(make_simulation_output(), out, force=True)


def test_force_overwrite_never_pairs_feed_and_manifest_of_different_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "notes.txt").write_text("keep", encoding="utf-8")
    write_output(simulate(SimulationConfig(42, "space_creation")), out, force=True)
    seen: list[tuple[str, str]] = []

    def consistent() -> None:
        feed, manifest = out / "feed.jsonl", out / "manifest.json"
        if feed.exists() and manifest.exists():
            got = hashlib.sha256(feed.read_bytes()).hexdigest()
            want = json.loads(manifest.read_text(encoding="utf-8"))["feed_sha256"]
            seen.append((got, want))

    for name in ("replace", "rename"):
        real = getattr(os, name)

        def spy(src: object, dst: object, *, _real: Any = real) -> None:
            _real(src, dst)
            consistent()

        monkeypatch.setattr(os, name, spy)
    second = simulate(SimulationConfig(1, "space_creation"))
    written = write_output(second, out, force=True)
    monkeypatch.undo()
    assert seen, "write_output never renamed anything"
    assert all(got == want for got, want in seen), seen
    assert written.feed_sha256 == second.manifest.feed_sha256
    assert (out / "notes.txt").read_text(encoding="utf-8") == "keep"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out"]


def test_failed_write_leaves_no_feed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(self: GenerationManifest) -> str:
        raise RuntimeError("disk full")

    monkeypatch.setattr(GenerationManifest, "to_canonical_json", boom)
    out = tmp_path / "out"
    with pytest.raises(RuntimeError):
        write_output(make_simulation_output(), out)
    assert not (out / "feed.jsonl").exists()
    assert list(tmp_path.iterdir()) in ([], [out])


def test_feed_bytes_matches_written_file(tmp_path: Path) -> None:
    output = make_simulation_output()
    written = write_output(output, tmp_path / "out")
    assert io.feed_bytes(to_envelopes(output)) == written.feed_path.read_bytes()
