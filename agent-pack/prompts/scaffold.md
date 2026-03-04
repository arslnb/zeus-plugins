Build a Zeus plugin scaffold in this repository.

Requirements:
1) Create `zeus.plugin.json` using `schemas/zeus.plugin.schema.json`.
2) Create matching Python entry files for every declared component.
3) Add `metadata.json` using `schemas/registry.metadata.schema.json`.
4) Add `examples/install.json` and `examples/config.json`.
5) Return exact commands for `zeus plugin check --json`.
