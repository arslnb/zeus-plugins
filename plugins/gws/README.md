# Google Workspace

Hybrid Zeus plugin that uses the [Google Workspace CLI (`gws`)](https://github.com/googleworkspace/cli) under the hood.

## Implemented capability

- `gws_gmail_unread`: end-to-end unread inbox triage.
  - Calls `gws gmail users messages list`.
  - Fetches each message with `gws gmail users messages get`.
  - Returns structured message summaries (`from`, `subject`, `date`, `snippet`).

## Additional tool

- `gws_execute`: generic wrapper for any `gws` operation (Gmail, Drive, Calendar, etc.).
  - Example operation: `"drive files list"`
  - Optional fields: `params`, `body`, `extra_args`, `timeout_seconds`

## Prerequisites

```bash
npm install -g @googleworkspace/cli
gws auth setup
```

## Install API call

```bash
curl -sS -X POST "${ZEUS_BASE_URL:-http://localhost:3000}/api/plugins/install" \
  -H "Content-Type: application/json" \
  --data @plugins/gws/examples/install.json
```

## Config API call

```bash
curl -sS -X POST "${ZEUS_BASE_URL:-http://localhost:3000}/api/plugins/config" \
  -H "Content-Type: application/json" \
  --data @plugins/gws/examples/config.json
```

## Local verification

```bash
. .venv/bin/activate
zeus plugin check plugins/gws --json
zeus plugin check . --registry --json
```

## Capability smoke test

```bash
python - <<'PY'
import importlib.util
import json
from pathlib import Path

path = Path("plugins/gws/client/plugin.py")
spec = importlib.util.spec_from_file_location("gws_plugin", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

result = module.gws_gmail_unread({"max_results": 3})
print(json.dumps(result, indent=2))
PY
```

## Troubleshooting

- `gws executable not found in PATH`
  - Fix: `npm install -g @googleworkspace/cli` and make sure `gws` is on your PATH.
- Auth errors (`invalid_grant`, `401`, or no credentials)
  - Fix: run `gws auth login` (or `gws auth setup` for first-time setup).
- Google API disabled (`accessNotConfigured`)
  - Fix: open the `enable_url` returned by `gws`, enable the API, wait ~10 seconds, and retry.
