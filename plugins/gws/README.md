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

The plugin manifest now declares and auto-installs prerequisites (when possible):

- `gws` via `npm install -g @googleworkspace/cli`
- `gcloud` via platform-specific install commands

Auth/setup is executed through plugin setup actions:

```bash
gws auth setup
```

Zeus now treats this as an interactive setup handoff:

- the main Zeus agent runs `gws auth setup` in the notch
- CLI output is streamed to the user
- if `gws` prints a browser or Google Cloud Console URL, Zeus surfaces it and waits
- Zeus verifies completion with `gws auth status`

## Install API call

```bash
curl -sS -X POST "${ZEUS_BASE_URL:-http://localhost:3000}/api/plugins/install" \
  -H "Content-Type: application/json" \
  --data @plugins/gws/examples/install.json
```

## Configure API call

```bash
curl -sS -X POST "${ZEUS_BASE_URL:-http://localhost:3000}/api/plugins/configure" \
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
  - Fix: rerun plugin setup (which opens the Zeus interactive setup flow). If `gws` says manual Google Cloud Console setup is required, complete it there, then let Zeus resume and verify with `gws auth status`.
- Google API disabled (`accessNotConfigured`)
  - Fix: open the `enable_url` returned by `gws`, enable the API, wait ~10 seconds, and retry.
