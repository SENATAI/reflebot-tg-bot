from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from time import monotonic


class SlidingWindowRateLimiter:
    def __init__(
        self,
        max_calls: int,
        *,
        period_seconds: float = 1.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be at least 1.")
        if period_seconds <= 0:
            raise ValueError("period_seconds must be greater than 0.")

        self._max_calls = max_calls
        self._period_seconds = period_seconds
        self._clock = clock
        self._calls: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            sleep_for = 0.0
            async with self._lock:
                now = self._clock()
                self._evict_expired(now)

                if len(self._calls) < self._max_calls:
                    self._calls.append(now)
                    return

                sleep_for = self._period_seconds - (now - self._calls[0])

            await asyncio.sleep(max(sleep_for, 0))

    def _evict_expired(self, now: float) -> None:
        while self._calls and now - self._calls[0] >= self._period_seconds:
            self._calls.popleft()
