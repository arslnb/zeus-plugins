# Zeus Plugins

Community plugin registry and tooling for Zeus.

## What is in this repo
- `plugins/`: submitted plugins (manifest, metadata, examples, code)
- `index.json`: canonical directory used by Zeus to discover plugins
- `schemas/`: strict JSON schemas for manifest + registry metadata
- `agent-pack/`: copy/paste prompts and checklists for coding agents
- `zeus` CLI (from this repo):
  - `zeus plugin init` to scaffold a plugin
  - `zeus plugin check --json` to validate plugin/registry

## Quickstart

```bash
git clone git@github.com:arslnb/zeus-plugins.git
cd zeus-plugins
python -m pip install .

# Scaffold a new plugin
zeus plugin init weather_digest --runtime daemon --owner yourname

# Validate just that plugin
zeus plugin check plugins/weather_digest --json

# Validate whole registry
zeus plugin check . --registry --json
```

## Submit a plugin
1. Fork this repo.
2. Add your plugin under `plugins/<plugin_id>/`.
3. Update `index.json` (or run `scripts/rebuild_index.py`).
4. Open a PR and include validation output.
