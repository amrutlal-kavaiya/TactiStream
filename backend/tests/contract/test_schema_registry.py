import json
from pathlib import Path
from typing import Any

import pytest

from tactistream.contracts.schema_registry import ContractError, SchemaRegistry, contracts_dir, validate

EXAMPLES = Path(__file__).parents[3] / "contracts" / "examples"


def event() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((EXAMPLES / "event.json").read_text(encoding="utf-8"))
    return data


def test_default_dir_is_repo_contracts_schemas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TACTISTREAM_CONTRACTS_DIR", raising=False)
    assert contracts_dir() == Path(__file__).parents[3] / "contracts" / "schemas"


def test_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TACTISTREAM_CONTRACTS_DIR", str(tmp_path))
    assert contracts_dir() == tmp_path


def test_schema_resolvable_by_id_and_file_name() -> None:
    validate("event.schema.json", event())
    validate("https://tactistream.dev/contracts/event.schema.json", event())


def test_error_reports_json_path() -> None:
    bad = event()
    bad["start_m"] = [58.1, 999.0]
    with pytest.raises(ContractError) as exc:
        validate("event.schema.json", bad)
    assert exc.value.path == "$.start_m[1]"
    assert "$.start_m[1]" in str(exc.value)


def test_unknown_schema_raises_contract_error() -> None:
    with pytest.raises(ContractError):
        validate("nope.schema.json", {})


def test_registry_from_custom_dir(tmp_path: Path) -> None:
    (tmp_path / "tiny.schema.json").write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "https://tactistream.dev/contracts/tiny.schema.json",
                "type": "integer",
            }
        ),
        encoding="utf-8",
    )
    registry = SchemaRegistry(tmp_path)
    registry.validate("tiny.schema.json", 3)
    with pytest.raises(ContractError):
        registry.validate("tiny.schema.json", "x")
