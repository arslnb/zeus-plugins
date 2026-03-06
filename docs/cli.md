# Zeus CLI in this Repo

## Install

```bash
python -m pip install .
```

## Create scaffold

```bash
zeus plugin init my_plugin --runtime daemon --owner arslnb
```

## Validate one plugin

```bash
zeus plugin check plugins/my_plugin --json
```

## Validate full registry

```bash
zeus plugin check . --registry --json
```

## Registry validation behavior
- `zeus plugin check . --registry` validates only plugins that appear in `index.json`.
- Folders under `plugins/` that are not allowlisted are ignored by registry validation and by the Zeus app catalog.

## Prerequisite authoring workflow
1. Add prerequisite metadata to `zeus.plugin.json`.
2. Give each required prerequisite:
   - `id`
   - `name`
   - `why`
   - `binary` and/or `check_command`
   - at least one `install_options[]` entry or docs URL
3. Prefer `install_options[]` over legacy `auto_install_commands`.

Example:

```json
{
  "prerequisites": {
    "agent_guidance": "Install prerequisites first, then return to plugin configuration.",
    "cli": [
      {
        "id": "github_cli",
        "name": "GitHub CLI",
        "binary": "gh",
        "required": true,
        "why": "Needed for repository operations.",
        "check_command": "gh --version",
        "install_options": [
          {
            "type": "shell",
            "label": "Install with Homebrew",
            "command": "brew install gh",
            "auto_run": true,
            "requires_admin": false,
            "platforms": ["darwin"]
          },
          {
            "type": "open_url",
            "label": "Open install docs",
            "url": "https://cli.github.com/"
          }
        ]
      }
    ]
  }
}
```

## Validation rules worth knowing
- Every prerequisite needs a usable detection path.
- Every required prerequisite needs an install path or docs URL.
- `auto_run: true` is rejected for admin-only/manual URL actions.
- Auto-run shell commands must be a single explicit command, not a chained script.
