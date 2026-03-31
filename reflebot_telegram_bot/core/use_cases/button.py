from __future__ import annotations

from reflebot_telegram_bot.core.models import PlatformUpdate, UseCaseResult
from reflebot_telegram_bot.core.planner import ResponsePlanner
from reflebot_telegram_bot.core.ports import BackendWorkflowPort


class ButtonUseCase:
    def __init__(
        self,
        backend_workflow: BackendWorkflowPort,
        planner: ResponsePlanner,
    ) -> None:
        self._backend_workflow = backend_workflow
        self._planner = planner

    async def execute(self, update: PlatformUpdate) -> UseCaseResult:
        if update.action is None:
            raise ValueError("Button update requires action.")
        response = await self._backend_workflow.send_button(update.identity, update.action)
        batch = self._planner.from_backend_response(
            response,
            edit_target_message_id=update.source_message_id,
        )
        return UseCaseResult(identity=update.identity, batch=batch)
