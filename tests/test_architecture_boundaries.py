from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "reflebot_telegram_bot"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_core_backend_and_broker_do_not_import_aiogram() -> None:
    checked_files = [
        "core/models.py",
        "core/planner.py",
        "core/ports.py",
        "core/use_cases/start.py",
        "core/use_cases/button.py",
        "core/use_cases/text.py",
        "core/use_cases/file.py",
        "core/use_cases/broker_prompt.py",
        "backend/client.py",
        "backend/compatibility.py",
        "backend/errors.py",
        "backend/gateway.py",
        "backend/schemas.py",
        "broker/consumer.py",
        "broker/publisher.py",
        "broker/schemas.py",
    ]

    for relative_path in checked_files:
        contents = _read(relative_path)
        assert "from aiogram" not in contents
        assert "import aiogram" not in contents


def test_legacy_telegram_specific_modules_are_removed() -> None:
    absent_paths = [
        ROOT / "handlers" / "start.py",
        ROOT / "handlers" / "callbacks.py",
        ROOT / "handlers" / "messages.py",
        ROOT / "services" / "backend_gateway.py",
        ROOT / "services" / "file_adapter.py",
        ROOT / "services" / "prompt_delivery.py",
        ROOT / "services" / "renderer.py",
        ROOT / "telegram" / "keyboards.py",
        ROOT / "telegram" / "media.py",
    ]

    for path in absent_paths:
        assert not path.exists()
