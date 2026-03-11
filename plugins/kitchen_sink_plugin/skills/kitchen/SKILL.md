---
summary: Kitchen sink helper skill for the real Telegram + GitHub OAuth reference plugin.
---
# Kitchen Sink Skill

Use this bundled skill when the Kitchen Sink Plugin is installed.

- Channel name: `telegram_kitchen_sink`
- Telegram inbound webhook path: `/v1/channels/telegram_kitchen_sink/webhook`
- Telegram outbound send path: `/v1/client/channels/telegram_kitchen_sink/send`
- Telegram config keys: `server.telegram_bot_token`, `server.telegram_webhook_secret`
- Telegram commands: `/help`, `/github_me`, `/github_notifications`
- GitHub OAuth provider id: `server_github`
- GitHub config keys: `server.github_client_id`, `server.github_client_secret`
- GitHub access is performed on the server side using the stored `server_github` OAuth token.

This skill exists both to verify bundled skill installation and to document the live integration surfaces exposed by the plugin.
