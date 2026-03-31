from __future__ import annotations


class BackendTransportError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        detail: str,
        error_code: str | None,
        endpoint: str,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        self.endpoint = endpoint
        super().__init__(f"{status_code} {error_code or 'UNKNOWN'}: {detail}")


def resolve_user_message(
    error: BackendTransportError,
    *,
    default_message: str,
) -> str:
    if error.error_code in {"MISSING_API_KEY", "INVALID_API_KEY"}:
        return default_message
    if error.error_code == "MODEL_FIELD_NOT_FOUND":
        return (
            "Мы не нашли вас в системе. "
            "Проверьте, что ваш Telegram username зарегистрирован."
        )
    if error.error_code == "PERMISSION_DENIED":
        return "У вас нет доступа к этому действию."
    if error.error_code == "VALIDATION_ERROR":
        return error.detail or "Данные не подошли для текущего шага."
    return default_message
