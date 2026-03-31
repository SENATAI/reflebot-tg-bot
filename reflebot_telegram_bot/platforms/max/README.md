# Max Adapter Skeleton

Этот каталог зарезервирован под будущий adapter для платформы Max.

Чтобы подключить Max без дублирования Bot Core, нужно реализовать:

- mapper входящих событий Max в `PlatformUpdate`
- sender для `PlatformMessageBatch`
- capability strategy для edit/buttons/media
- bootstrap wiring через `platform_registry`
- compatibility strategy, если backend contract останется Telegram-centric
