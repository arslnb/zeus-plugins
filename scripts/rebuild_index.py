#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"
INDEX = ROOT / "index.json"

entries = []
for plugin_dir in sorted(p for p in PLUGINS.iterdir() if p.is_dir()):
    metadata_path = plugin_dir / "metadata.json"
    manifest_path = plugin_dir / "zeus.plugin.json"
    if not metadata_path.exists() or not manifest_path.exists():
        continue
    with metadata_path.open("r", encoding="utf-8") as f:
        metadata = json.load(f)
    entries.append(
        {
            "id": metadata["id"],
            "name": metadata["name"],
            "version": metadata["version"],
            "summary": metadata["summary"],
            "owner": metadata["owner"],
            "runtime": metadata["runtime"],
            "categories": metadata["categories"],
            "min_zeus_version": metadata["min_zeus_version"],
            "source_repo": metadata["source_repo"],
            "license": metadata["license"],
            "metadata_path": f"plugins/{plugin_dir.name}/metadata.json",
            "manifest_path": f"plugins/{plugin_dir.name}/zeus.plugin.json",
        }
    )

with INDEX.open("w", encoding="utf-8") as f:
    json.dump(entries, f, indent=2)
    f.write("\n")

print(f"Wrote {INDEX} with {len(entries)} entries.")
