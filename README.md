# Zeus Plugins

Community plugin registry and tooling for Zeus.

## What is in this repo
- `plugins/`: submitted plugins (manifest, metadata, examples, code)
- `index.json`: authoritative allowlist used by Zeus to discover approved plugins
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

## Authoring prerequisites for a smooth setup UX
- Treat `index.json` as the only approved catalog list. Zeus ignores plugin folders that are not allowlisted there.
- Declare prerequisites in `zeus.plugin.json` under `prerequisites.cli[]`.
- Prefer the new declarative install model:
  - `id`
  - `why`
  - `check_command`
  - `install_options[]`
  - optional `agent_guidance`
- `install_options[]` supports:
  - `type: "shell"` with `command`, `label`, `description`, `auto_run`, `requires_admin`, optional `platforms`
  - `type: "open_url"` with `url`, `label`, `description`, optional `platforms`
- Zeus installs the plugin first, then opens a notch setup thread when required prerequisites are missing. The main Zeus agent creates one todo per missing prerequisite and can auto-run only manifest-declared safe shell commands.
- Keep auth/setup in `oauth`; keep environment install in `prerequisites`.
- Legacy fields (`auto_install_commands`, `install_hint`, `install_url`, `docs_url`) still validate and normalize, but new plugins should author `install_options[]`.

## Reference implementation
- `plugins/gws/zeus.plugin.json` is the reference manifest for:
  - catalog allowlisting
  - prerequisite install options
  - Zeus prerequisite handoff
  - CLI OAuth sequence
  - shipped skills
