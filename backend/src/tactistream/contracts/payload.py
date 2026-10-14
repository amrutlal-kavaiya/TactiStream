"""Parse an untyped JSON payload into the contract model selected by a sibling discriminator field."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel


def parse_payload(
    models: Mapping[str, type[BaseModel]], tag: object, value: object
) -> BaseModel | dict[str, Any]:
    """Return `value` as the model registered for `tag`; tags without a model keep a plain object."""
    if not isinstance(tag, str):
        raise ValueError("payload cannot be typed without a valid discriminator")
    model = models.get(tag)
    if model is None:
        if isinstance(value, dict):
            return value
        raise ValueError(f"payload for {tag!r} must be an object")
    if isinstance(value, model):
        return value
    if isinstance(value, BaseModel):
        raise ValueError(f"payload for {tag!r} must be {model.__name__}, got {type(value).__name__}")
    return model.model_validate(value)
