import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from azure.eventhub.exceptions import AuthenticationError
from support.fake_eventhubs import FakeHub

from tactistream.smoke.eventhubs import EventHubsSmokeResult, run_eventhubs_smoke
from tactistream.smoke.foundry import SmokeError

NAMESPACE = "tactistream.servicebus.windows.net"
HUB = "tactistream-feed"


def clock(*seconds: float) -> Callable[[], float]:
    values = iter(seconds)
    return lambda: next(values)


async def run(hub: FakeHub, **kw: Any) -> EventHubsSmokeResult:
    kw.setdefault("clock", clock(5.0, 5.0873))
    return await run_eventhubs_smoke(NAMESPACE, HUB, credential="cred", client_factory=hub, **kw)


async def test_publishes_one_envelope_and_reads_it_back_via_live_state() -> None:
    hub = FakeHub()
    before = datetime.now(UTC)
    result = await run(hub)

    ((body, partition_key),) = hub.sent
    sent = json.loads(body)
    assert result.record_id == sent["record_id"]
    assert result.record_id.startswith("evt-")
    assert partition_key == sent["match_id"]
    assert (result.namespace, result.hub, result.consumer_group) == (NAMESPACE, HUB, "live-state")
    assert result.round_trip_ms == 87
    assert hub.producers[0][:3] == (NAMESPACE, HUB, "cred")
    assert hub.consumer_args == [(NAMESPACE, HUB, "live-state", "cred")]
    (consumer,) = hub.consumers["live-state"]
    assert isinstance(consumer.starting_position, datetime)
    assert consumer.starting_position <= before
    assert consumer.closed
    assert hub.producers[0][3].closed


async def test_record_ids_are_random() -> None:
    first = await run(FakeHub())
    second = await run(FakeHub())
    assert first.record_id != second.record_id


async def test_other_envelopes_on_the_hub_are_ignored() -> None:
    hub = FakeHub()
    foreign = {
        "schema_version": "1.0",
        "kind": "latency",
        "match_id": "other-match",
        "record_id": "lat-1",
        "published_ms": 1,
        "payload": {},
    }
    hub.log.append((datetime.now(UTC), json.dumps(foreign)))
    result = await run(hub)
    assert result.record_id == json.loads(hub.sent[0][0])["record_id"]


async def test_not_read_back_within_timeout_is_a_smoke_error() -> None:
    hub = FakeHub(transform=lambda body: None)
    with pytest.raises(SmokeError, match=r"not read back via live-state within 0\.05 s"):
        await run(hub, timeout_s=0.05, clock=clock(1.0))
    assert hub.producers[0][3].closed


async def test_consumer_failure_is_raised_with_its_cause_not_a_timeout() -> None:
    hub = FakeHub(consumer_error=AuthenticationError("unauthorized: no Data Receiver role"))
    with pytest.raises(AuthenticationError, match="no Data Receiver role"):
        await run(hub, timeout_s=5, clock=clock(1.0))
    assert hub.consumers["live-state"][0].closed


async def test_read_back_that_differs_from_the_sent_envelope_is_a_smoke_error() -> None:
    def tamper(body: str) -> str:
        envelope = json.loads(body)
        envelope["published_ms"] += 1
        return json.dumps(envelope)

    with pytest.raises(SmokeError, match="differs"):
        await run(FakeHub(transform=tamper), clock=clock(1.0, 1.1))
