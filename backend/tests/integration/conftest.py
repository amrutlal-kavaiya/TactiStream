from collections.abc import AsyncIterator

import pytest
from support.app_env import Env, make_env


@pytest.fixture
async def env() -> AsyncIterator[Env]:
    async for value in make_env():
        yield value
