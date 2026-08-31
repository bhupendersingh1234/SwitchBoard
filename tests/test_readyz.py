async def test_readyz_reports_starting_without_lifespan(client) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["status"] == "starting"