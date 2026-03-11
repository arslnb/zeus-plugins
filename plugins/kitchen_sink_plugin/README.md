# Kitchen Sink Plugin

Reference Zeus-native plugin used to verify the full plugin surface area.

## Purpose

This plugin exists to prove that one plugin package can declare and load:

- client tools, commands, services, CLI, providers, gateway, and HTTP handlers
- prompt/tool hooks
- bundled skills
- behaviors and scheduled tasks
- proactive screen-watch rules
- a custom server channel and webhook
- server OAuth providers

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

## Notes

- The channel is intentionally named `telegram_kitchen_sink`, not `telegram`, so it does not collide with the built-in Telegram adapter.
- The server OAuth providers are example providers used for local/runtime testing.
- The plugin uses `python3` as its declared prerequisite so it is installable as a real registry package.
