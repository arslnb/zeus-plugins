---
summary: Kitchen sink helper skill for the real Telegram + GitHub OAuth reference plugin.
---
# Kitchen Sink Skill

Use this bundled skill when the Kitchen Sink Plugin is installed.

- Channel name: `telegram`
- Telegram inbound webhook path: `/v1/channels/telegram/webhook`
- Telegram outbound send path: `/v1/client/channels/telegram/send`
- Telegram config keys: `server.telegram_bot_token`, `server.telegram_webhook_secret`
- Telegram replies are agent-mediated; the plugin does not define direct slash commands.
- GitHub OAuth provider id: `server_github`
- GitHub config keys: `server.github_client_id`, `server.github_client_secret`
- GitHub access is performed on the server side using the stored `server_github` OAuth token.
- GitHub daemon tools: `github_me`, `github_notifications`
- Those daemon tools proxy through signed server plugin actions instead of using a separate PAT.

This skill exists both to verify bundled skill installation and to document the live integration surfaces exposed by the plugin.
