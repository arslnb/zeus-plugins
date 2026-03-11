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

## Build a signed static registry

Generate an Ed25519 keypair once:

```bash
zeus plugin keygen --out-dir .registry-keys
```

Publish the approved registry to a static directory:

```bash
zeus plugin publish . \
  --output-dir dist/registry \
  --base-url https://plugins.example.com \
  --private-key .registry-keys/ed25519-private.pem \
  --clean
```

That produces:

- `dist/registry/index.json` for the app catalog
- `dist/registry/plugins/<plugin_id>/<version>.json` for server installs
- `dist/registry/artifacts/<plugin_id>/<version>/<plugin_id>-<version>.tgz`
- `dist/registry/registry-public-key.b64` for `ZEUS_PLUGIN_REGISTRY_PUBLIC_KEY`

Host `dist/registry/` on any static host (GitHub Pages, Cloudflare Pages, S3, R2, Vercel static output, etc.).
Then set on the Zeus message server:

- `ZEUS_PLUGIN_REGISTRY_BASE_URL=https://plugins.example.com`
- `ZEUS_PLUGIN_REGISTRY_PUBLIC_KEY=$(cat dist/registry/registry-public-key.b64)`

## GitHub Pages publish pipeline

This repo now includes a GitHub Actions workflow at `.github/workflows/publish-registry.yml`.
On every push to `main`, it can publish the signed static registry to GitHub Pages.

Set these once in the GitHub repo settings:

- Secret: `ZEUS_REGISTRY_SIGNING_PRIVATE_KEY`
  - Use the contents of `.registry-keys/ed25519-private.pem` or `.registry-keys/ed25519-private.b64`
- Optional repository variable: `ZEUS_PLUGIN_REGISTRY_BASE_URL`
  - Set this only if you use a custom domain
  - Default is `https://<owner>.github.io/<repo>`

After the workflow runs, the server should use:

- `ZEUS_PLUGIN_REGISTRY_BASE_URL=https://<owner>.github.io/<repo>`
- `ZEUS_PLUGIN_REGISTRY_PUBLIC_KEY=<contents of dist/registry/registry-public-key.b64>`

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
- Zeus installs the plugin first, then opens a notch install thread when required prerequisites are missing. The main Zeus agent creates one todo per missing prerequisite and can auto-run only manifest-declared safe shell commands.
- Keep auth in `oauth`; keep environment install in `prerequisites`.
- For CLI auth that may open a browser or require manual work, set:
  - `oauth.interactive: true`
  - `oauth.success_check_command`
  - `oauth.agent_prompt`
- Use `oauth.secret_env` for Secret Vault-backed credentials and `oauth.env` for non-secret config fields that auth commands need at runtime. Zeus injects these bindings only when the referenced optional fields are set; required config fields still block Install until provided.
- Zeus will then hand auth to the main Zeus agent in a notch thread, stream the CLI output, wait for the user when needed, and recheck `success_check_command` before marking the plugin ready.
- Legacy fields (`auto_install_commands`, `install_hint`, `install_url`, `docs_url`) still validate and normalize, but new plugins should author `install_options[]`.

## Reference implementation
- `plugins/gws/zeus.plugin.json` is the reference manifest for:
  - catalog allowlisting
  - prerequisite install options
  - Zeus prerequisite handoff
  - interactive CLI OAuth handoff
  - shipped skills
