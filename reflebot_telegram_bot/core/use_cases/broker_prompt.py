from __future__ import annotations

from reflebot_telegram_bot.broker.schemas import ReflectionPromptCommand
from reflebot_telegram_bot.core.models import PlatformIdentity, UseCaseResult
from reflebot_telegram_bot.core.planner import ResponsePlanner


class BrokerPromptUseCase:
    def __init__(self, planner: ResponsePlanner, *, platform_name: str) -> None:
        self._planner = planner
        self._platform_name = platform_name

    async def execute(self, command: ReflectionPromptCommand) -> UseCaseResult:
        identity = PlatformIdentity(
            platform=self._platform_name,
            user_id=str(command.telegram_id),
            chat_id=str(command.telegram_id),
        )
        batch = self._planner.from_reflection_prompt(command)
        return UseCaseResult(identity=identity, batch=batch)
