from support.app_env import MATCH, app_env

from tactistream.contracts import validate

EVIDENCE = f"/api/matches/{MATCH}/evidence"


async def test_event_evidence_resolves_to_the_raw_record() -> None:
    async with app_env() as env:
        await env.start_session()
        await env.control("play")
        await env.clock.advance(3000)

        response = await env.client.get(f"{EVIDENCE}/evt-0042")
        assert response.status_code == 200
        body = response.json()
        assert (body["evidence_id"], body["kind"]) == ("evt-0042", "event")
        assert body["record"]["event_type"] == "pass"
        assert body["record"]["player_id"] == "blue-08"
        assert body["record"]["source"]["kind"] == "synthetic"
        validate("event.schema.json", body["record"])


async def test_metric_evidence_resolves() -> None:
    async with app_env() as env:
        await env.start_session()
        await env.control("play")
        await env.clock.advance(3000)

        response = await env.client.get(f"{EVIDENCE}/metric-forward_progress-0042", params={"language": "hi"})
        assert response.status_code == 200
        body = response.json()
        assert body["kind"] == "metric"
        assert body["record"]["value"] == 13.1
        validate("metric_result.schema.json", body["record"])


async def test_unknown_evidence_is_404() -> None:
    async with app_env() as env:
        await env.start_session()
        response = await env.client.get(f"{EVIDENCE}/evt-9999")
        assert response.status_code == 404
        assert response.json()["error"] == "evidence_not_found"


async def test_evidence_is_not_resolvable_before_its_session_time() -> None:
    async with app_env() as env:
        await env.start_session()
        await env.control("play")
        await env.clock.advance(3500)
        early = await env.client.get(f"{EVIDENCE}/evt-0043")
        assert (early.status_code, early.json()["error"]) == (404, "evidence_not_found")

        await env.clock.advance(400)
        assert (await env.client.get(f"{EVIDENCE}/evt-0043")).status_code == 200


async def test_evidence_for_unknown_match_is_404() -> None:
    async with app_env() as env:
        response = await env.client.get("/api/matches/demo-nope-001/evidence/evt-0042")
        assert (response.status_code, response.json()["error"]) == (404, "match_not_found")
