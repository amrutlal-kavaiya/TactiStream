from functools import cache

import pytest

from tactistream.contracts import FeedEnvelope, MatchEvent, MatchMetadata
from tactistream.transport.fixtures import load_fixture, skeleton_fixture_path


@cache
def _skeleton() -> tuple[FeedEnvelope, ...]:
    return tuple(load_fixture(skeleton_fixture_path()))


@pytest.fixture
def skeleton() -> list[FeedEnvelope]:
    return list(_skeleton())


@pytest.fixture
def metadata(skeleton: list[FeedEnvelope]) -> MatchMetadata:
    payload = skeleton[0].payload
    assert isinstance(payload, MatchMetadata)
    return payload


@pytest.fixture
def events(skeleton: list[FeedEnvelope]) -> dict[str, MatchEvent]:
    return {env.record_id: env.payload for env in skeleton if isinstance(env.payload, MatchEvent)}


@pytest.fixture
def pass_event(events: dict[str, MatchEvent]) -> MatchEvent:
    return events["evt-0042"]
