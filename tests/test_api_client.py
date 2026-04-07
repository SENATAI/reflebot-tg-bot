from __future__ import annotations

import httpx
import pytest

from reflebot_telegram_bot.api.client import BackendApiClient


@pytest.mark.asyncio()
async def test_parse_response_returns_empty_dict_for_success_without_body(settings) -> None:
    http_client = httpx.AsyncClient(base_url=settings.backend_api_url)
    client = BackendApiClient(http_client, settings)
    response = httpx.Response(
        status_code=204,
        content=b"",
        request=httpx.Request("POST", "http://127.0.0.1:8080/api/reflections/actions/message-delivered"),
    )

    try:
        parsed = await client._parse_response(response, "/actions/message-delivered")
    finally:
        await http_client.aclose()

    assert parsed == {}
