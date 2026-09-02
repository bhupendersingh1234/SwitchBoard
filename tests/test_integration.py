import httpx
import respx


@respx.mock
async def test_full_app_proxies_chat_completions_through_real_lifespan(live_client) -> None:
    respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"id": "chatcmpl-real", "choices": []})
    )
    response = await live_client.post(
        "/v1/chat/completions", json={"model": "gpt-4", "messages": []}
    )
    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-real"