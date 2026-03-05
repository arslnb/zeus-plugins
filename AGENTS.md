# AGENTS.md

Purpose: navigation and source-of-truth rules for the Zeus plugin registry repo.

## What This Repo Owns

- Plugin authoring scaffolds and validation tooling.
- Registry metadata consumed by Zeus.
- Approved plugin inventory.

## Canonical Sources

- Build/submission workflow:
  - `README.md`
  - `docs/cli.md`
- Plugin schemas:
  - `schemas/`
- Definitive approved plugin list:
  - `index.json`
- Plugin packages:
  - `plugins/<plugin_id>/`

## Update Rules

- Any material plugin behavior or packaging contract change must update:
  1. code or schema in this repo
  2. `index.json` if inventory/version/metadata changed
  3. developer-facing docs in `/Users/arslnb/codebase/zeus-ws/blog/zeus/docs/` in the same overall change.

- Keep `index.json` and `plugins/*` metadata/manifests consistent.

