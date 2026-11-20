import httpx


async def test_health_shape(client: httpx.AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["api"] == "ok"
    assert body["database"] in {"ok", "down"}


async def test_report_requires_description(client: httpx.AsyncClient) -> None:
    r = await client.post("/reports", json={"channel": "web"})
    assert r.status_code == 422
