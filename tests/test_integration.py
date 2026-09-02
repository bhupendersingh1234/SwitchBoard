import httpx
import respx

from switchboard.api.deps import get_current_tenant
from switchboard.db.models import Tenant
from switchboard.main import app


@respx.mock
async def test_full_app_proxies_chat_completions_through_real_lifespan(live_client) -> None:
    app.dependency_overrides[get_current_tenant] = lambda: Tenant(name="test-tenant")
    try:
        respx.post("https://api.openai.com/v1/chat/completions").mock(
            return_value=httpx.Response(200, json={"id": "chatcmpl-real", "choices": []})
        )
        response = await live_client.post(
            "/v1/chat/completions", json={"model": "gpt-4", "messages": []}
        )
        assert response.status_code == 200
        assert response.json()["id"] == "chatcmpl-real"
    finally:
        app.dependency_overrides.clear()


async def test_chat_completions_requires_authentication(live_client) -> None:
    response = await live_client.post(
        "/v1/chat/completions", json={"model": "gpt-4", "messages": []}
    )
    assert response.status_code == 401