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

Install can also collect optional Google OAuth client credentials for `gws`:

- `google_client_id`
- `google_client_secret`

Zeus stores both values in Secret Vault and injects them into the auth step only when you provide them.

If `gws` is already configured on this Mac, leave those fields blank and Zeus will reuse the existing local `gws` client config during Install.

If `gws auth login` reports that no client configuration exists, create a Desktop app OAuth client once in Google Cloud Console, then paste the Client ID + Client Secret into the Install form. Zeus stores them in Secret Vault and reuses them on future installs.

Auth is executed through plugin install auth actions:

```bash
gws auth login
```

Zeus now treats this as an interactive install handoff:

- the main Zeus agent runs `gws auth login` in the notch
- CLI output is streamed to the user
- if provided, the Google OAuth client credentials come from Zeus Secret Vault via `secret_env`
- otherwise, `gws` uses its existing local client config on this Mac
- if `gws` opens a browser or prints a consent URL, Zeus surfaces it and waits
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
  - Fix: if this Mac does not already have a working `gws` client config, add the Desktop OAuth Client ID + Client Secret to the Install form, then rerun Install so Zeus can launch `gws auth login`.
- Google API disabled (`accessNotConfigured`)
  - Fix: open the `enable_url` returned by `gws`, enable the API, wait ~10 seconds, and retry.
