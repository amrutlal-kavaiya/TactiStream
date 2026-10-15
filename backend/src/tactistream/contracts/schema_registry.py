"""Load the canonical JSON Schemas in `/contracts/schemas` and validate objects against them."""

from __future__ import annotations

import json
import os
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable

BASE_URI = "https://tactistream.dev/contracts/"
ENV_DIR = "TACTISTREAM_CONTRACTS_DIR"


class ContractError(ValueError):
    """An object does not conform to its contract schema."""

    def __init__(self, schema: str, path: str, message: str) -> None:
        super().__init__(f"{schema}: {path}: {message}")
        self.schema = schema
        self.path = path
        self.message = message


def contracts_dir() -> Path:
    override = os.environ.get(ENV_DIR)
    if override:
        return Path(override)
    return Path(__file__).parents[4] / "contracts" / "schemas"


class SchemaRegistry:
    """Schemas keyed by both `$id` and file name so relative `$ref`s resolve either way."""

    def __init__(self, directory: Path) -> None:
        resources: list[tuple[str, Resource[Any]]] = []
        for path in sorted(directory.glob("*.json")):
            contents = json.loads(path.read_text(encoding="utf-8"))
            resource: Resource[Any] = Resource.from_contents(contents)
            resources.append((path.name, resource))
            resources.append((urljoin(BASE_URI, path.name), resource))
            schema_id = contents.get("$id")
            if isinstance(schema_id, str):
                resources.append((schema_id, resource))
        self.directory = directory
        self.registry: Registry[Any] = Registry().with_resources(resources)
        self._validators: dict[str, Draft202012Validator] = {}

    def _validator(self, schema: str) -> Draft202012Validator:
        uri = urljoin(BASE_URI, schema)
        validator = self._validators.get(uri)
        if validator is None:
            resource_uri = uri.split("#", 1)[0]
            try:
                self.registry.get_or_retrieve(resource_uri)
            except Exception as exc:
                raise ContractError(schema, "$", f"unknown schema {resource_uri}") from exc
            validator = Draft202012Validator({"$ref": uri}, registry=self.registry)
            self._validators[uri] = validator
        return validator

    def validate(self, schema: str, obj: object) -> None:
        """Raise `ContractError` (with the JSON path of the most relevant failure) if `obj` is invalid."""
        validator = self._validator(schema)
        try:
            error = best_match(validator.iter_errors(obj))
        except Unresolvable as exc:
            raise ContractError(schema, "$", f"unresolvable reference: {exc}") from exc
        if error is not None:
            raise ContractError(schema, error.json_path, error.message)


@cache
def _registry_for(directory: Path) -> SchemaRegistry:
    return SchemaRegistry(directory)


def default_registry() -> SchemaRegistry:
    return _registry_for(contracts_dir())


def validate(schema: str, obj: object) -> None:
    """Validate `obj` against `schema` (file name, `$id`, optionally with a `#/$defs/...` fragment)."""
    default_registry().validate(schema, obj)
