from __future__ import annotations

from reflebot_telegram_bot.core.models import PlatformUpdate, UseCaseResult
from reflebot_telegram_bot.core.planner import ResponsePlanner
from reflebot_telegram_bot.core.ports import BackendWorkflowPort


class StartUseCase:
    def __init__(
        self,
        backend_workflow: BackendWorkflowPort,
        planner: ResponsePlanner,
    ) -> None:
        self._backend_workflow = backend_workflow
        self._planner = planner

    async def execute(self, update: PlatformUpdate) -> UseCaseResult:
        response = await self._backend_workflow.login(
            update.identity,
            invite_token=update.start_payload,
        )
        batch = self._planner.from_backend_response(response)
        return UseCaseResult(identity=update.identity, batch=batch)
