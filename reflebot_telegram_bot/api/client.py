from __future__ import annotations

import logging
from typing import Any

import httpx

from reflebot_telegram_bot.api.errors import BackendTransportError
from reflebot_telegram_bot.api.schemas import BackendError
from reflebot_telegram_bot.settings import Settings

logger = logging.getLogger(__name__)


class BackendApiClient:
    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http_client = http_client
        self._settings = settings

    def _build_headers(self, telegram_id: int | None = None) -> dict[str, str]:
        headers = {"X-Service-API-Key": self._settings.service_api_key}
        if telegram_id is not None:
            headers["X-Telegram-Id"] = str(telegram_id)
        return headers

    async def post_json(
        self,
        endpoint: str,
        *,
        payload: dict[str, Any] | None = None,
        telegram_id: int | None = None,
    ) -> dict[str, Any]:
        response = await self._http_client.post(
            endpoint,
            json=payload,
            headers=self._build_headers(telegram_id),
        )
        return await self._parse_response(response, endpoint)

    async def post_multipart(
        self,
        endpoint: str,
        *,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        telegram_id: int,
    ) -> dict[str, Any]:
        response = await self._http_client.post(
            endpoint,
            data=data,
            files=files,
            headers=self._build_headers(telegram_id),
        )
        return await self._parse_response(response, endpoint)

    async def _parse_response(
        self,
        response: httpx.Response,
        endpoint: str,
    ) -> dict[str, Any]:
        if response.is_success:
            return response.json()

        detail = response.text
        error_code: str | None = None
        try:
            parsed = BackendError.model_validate(response.json())
            detail = parsed.detail
            error_code = parsed.error_code
        except Exception:
            logger.exception("Failed to decode backend error payload")

        raise BackendTransportError(
            status_code=response.status_code,
            detail=detail,
            error_code=error_code,
            endpoint=endpoint,
        )
