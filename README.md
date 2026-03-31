# Reflebot Telegram Bot

Асинхронный Bot-сервис для Reflebot на стеке `uv`, `aiogram`, `httpx`, `aio-pika` и `pydantic_settings`.

## Архитектура

Проект разделён на несколько слоёв:

- `reflebot_telegram_bot/core/` — platform-agnostic модели, порты, planner и use cases.
- `reflebot_telegram_bot/backend/` — HTTP gateway и compatibility layer для текущего backend contract.
- `reflebot_telegram_bot/platforms/telegram/` — Telegram adapter: update mapper, sender и router wiring.
- `reflebot_telegram_bot/broker/` — RabbitMQ consumer и publisher для reflection prompt delivery.
- `reflebot_telegram_bot/bootstrap/` — выбор активного platform adapter.

Текущая версия запускает `telegram` как активный adapter. Каркас для `max` добавлен как skeleton, но не реализован.

## Ограничение

Backend contract остаётся Telegram-centric:

- login использует `telegram_username`
- action endpoint'ы используют `X-Telegram-Id`
- media workflow использует `telegram_file_id`

Это изолировано в `backend/compatibility.py`, но для полноценного multi-platform backend позже потребуется отдельная эволюция backend contract.

## Запуск

1. Создать `.env` на основе `.env.example`.
2. Установить зависимости:

```bash
uv sync --dev
```

3. Запустить бота:

```bash
uv run telegram-bot
```

## Основные настройки

- `PLATFORM_ADAPTER=telegram`
- `TELEGRAM_BOT_TOKEN`
- `REFLEBOT_BACKEND_BASE_URL`
- `REFLEBOT_API_PREFIX`
- `REFLEBOT_TELEGRAM_SECRET_TOKEN`
- `RABBITMQ_URL`
- `RABBITMQ_NOTIFICATIONS_EXCHANGE`
- `RABBITMQ_REFLECTION_PROMPT_QUEUE`
- `RABBITMQ_REFLECTION_PROMPT_ROUTING_KEY`
- `RABBITMQ_NOTIFICATION_RESULTS_EXCHANGE`
- `RABBITMQ_DELIVERY_RESULT_ROUTING_KEY`

## Тесты

```bash
uv run pytest
```
