# Kitchen Sink Plugin

Reference Zeus-native plugin used to verify the full plugin surface area while exercising a real Telegram channel and a real non-Google OAuth provider.

## Purpose

This plugin exists to prove that one plugin package can declare and load:

- client tools, commands, services, CLI, providers, gateway, and HTTP handlers
- prompt/tool hooks
- bundled skills
- behaviors and scheduled tasks
- proactive screen-watch rules
- a real Telegram-backed custom server channel and webhook
- a real GitHub OAuth provider on the server side
- real GitHub API usage over that server-side OAuth session
- agent-driven replies routed back through the plugin channel send path

It is primarily a testing and regression fixture, not an end-user productivity plugin.

## Install API call

```bash
curl -sS -X POST "${ZEUS_BASE_URL:-http://localhost:3000}/api/plugins/install" \
  -H "Content-Type: application/json" \
  --data @plugins/kitchen_sink_plugin/examples/install.json
```

## Configure API call

```bash
curl -sS -X POST "${ZEUS_BASE_URL:-http://localhost:3000}/api/plugins/configure" \
  -H "Content-Type: application/json" \
  --data @plugins/kitchen_sink_plugin/examples/config.json
```

## Local validation

```bash
. .venv/bin/activate
zeus plugin check plugins/kitchen_sink_plugin --json
zeus plugin check . --registry --json
```

## Real integration setup

### Telegram

Set these server secrets during install/configure:

- `telegram_bot_token`: Telegram bot token from BotFather
- `telegram_webhook_secret`: shared secret sent by Telegram as `X-Telegram-Bot-Api-Secret-Token`

Set `ZEUS_PUBLIC_BASE_URL` on the messaging server. On plugin enable/reload, the plugin auto-registers:

- webhook URL: `${ZEUS_PUBLIC_BASE_URL}/v1/channels/telegram_kitchen_sink/webhook`
- secret token: `${TELEGRAM_WEBHOOK_SECRET}`

Outbound sends use:

```bash
curl -sS -X POST "${ZEUS_SERVER_BASE_URL}/v1/client/channels/telegram_kitchen_sink/send" \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"<chat id>","text":"hello from zeus"}'
```

Normal inbound Telegram messages can also flow through the Mac app's agent loop and reply back through this same send path, because the plugin includes a `metadata.reply_context` payload on inbound envelopes.

### GitHub OAuth

Create a GitHub OAuth App and set:

- `github_client_id`
- `github_client_secret`

Use this callback URL in the GitHub app:

```text
https://<your-zeus-server>/v1/plugins/oauth/callback
```

Start the server-managed OAuth flow with provider id `server_github`.

Requested scopes:

- `read:user`
- `user:email`
- `notifications`

### Optional Telegram Commands

Once `server_github` is connected, the plugin also exposes a few direct server-side bot commands for smoke-testing:

Send these commands to the bot:

- `/help`
- `/github_me`
- `/github_notifications`

## Notes

- The channel is intentionally named `telegram_kitchen_sink`, not `telegram`, so it does not collide with the built-in Telegram adapter.
- The server OAuth provider is a real GitHub OAuth app configuration, not an example URL.
- The plugin no longer needs a separate GitHub PAT or `api_base` to exercise GitHub. It uses the stored `server_github` OAuth access token.
- The plugin uses `python3` as its declared prerequisite so it is installable as a real registry package.
