import os

import pytest

from tactistream.settings import Settings
from tactistream.smoke.foundry import run_foundry_smoke

pytestmark = pytest.mark.live


async def test_foundry_chat_round_trip() -> None:
    settings = Settings()
    endpoint, deployment = settings.foundry_project_endpoint, settings.foundry_model_deployment
    if not (endpoint and deployment):
        pytest.skip("set FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL_DEPLOYMENT and run `az login`")

    result = await run_foundry_smoke(endpoint, deployment, region=os.environ.get("AZURE_LOCATION"))

    assert result.reply["ok"] is True
    assert result.deployment == deployment
    assert result.latency_ms > 0
