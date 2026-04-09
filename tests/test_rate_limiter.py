from __future__ import annotations

from time import monotonic

import pytest

from reflebot_telegram_bot.platforms.telegram.rate_limiter import SlidingWindowRateLimiter


@pytest.mark.asyncio()
async def test_sliding_window_rate_limiter_waits_when_window_is_full() -> None:
    limiter = SlidingWindowRateLimiter(max_calls=2, period_seconds=0.05)

    await limiter.acquire()
    await limiter.acquire()

    started_at = monotonic()
    await limiter.acquire()
    elapsed = monotonic() - started_at

    assert elapsed >= 0.04
