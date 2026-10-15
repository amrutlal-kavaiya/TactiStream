import pytest

from tactistream.settings import Settings
from tactistream.smoke.eventhubs import run_eventhubs_smoke

pytestmark = pytest.mark.live


async def test_eventhubs_publish_and_read_back_via_live_state() -> None:
    settings = Settings()
    namespace = settings.eventhubs_fully_qualified_namespace
    if not namespace:
        pytest.skip("set EVENTHUBS_FULLY_QUALIFIED_NAMESPACE (and EVENTHUBS_NAME) and run `az login`")

    result = await run_eventhubs_smoke(namespace, settings.eventhubs_name)

    assert result.consumer_group == "live-state"
    assert result.record_id.startswith("evt-")
    assert 0 < result.round_trip_ms < 30_000
