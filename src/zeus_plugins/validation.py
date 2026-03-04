from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


@dataclass
class Issue:
    code: str
    message: str
    path: str


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_schema(repo_root: Path, name: str) -> dict[str, Any]:
    return _load_json(repo_root / "schemas" / name)


def _version_tuple(version: str) -> tuple[int, int, int] | None:
    parts = version.split(".")
    if len(parts) != 3:
        return None
    try:
        return tuple(int(p) for p in parts)  # type: ignore[return-value]
    except ValueError:
        return None


def _collect_schema_errors(validator: Draft202012Validator, payload: Any, base_path: str) -> list[Issue]:
    issues: list[Issue] = []
    for err in sorted(validator.iter_errors(payload), key=lambda e: e.path):
        rel = "/".join(str(p) for p in err.path)
        path = f"{base_path}:{rel}" if rel else base_path
        issues.append(Issue(code="SCHEMA", message=err.message, path=path))
    return issues


def validate_plugin_folder(repo_root: Path, plugin_dir: Path) -> list[Issue]:
    issues: list[Issue] = []
    manifest_path = plugin_dir / "zeus.plugin.json"
    metadata_path = plugin_dir / "metadata.json"

    if not manifest_path.exists():
        issues.append(Issue(code="FILES", message="Missing zeus.plugin.json", path=str(plugin_dir)))
        return issues
    if not metadata_path.exists():
        issues.append(Issue(code="FILES", message="Missing metadata.json", path=str(plugin_dir)))
        return issues

    try:
        manifest = _load_json(manifest_path)
    except Exception as exc:  # pragma: no cover
        issues.append(Issue(code="JSON", message=f"Invalid manifest JSON: {exc}", path=str(manifest_path)))
        return issues

    try:
        metadata = _load_json(metadata_path)
    except Exception as exc:  # pragma: no cover
        issues.append(Issue(code="JSON", message=f"Invalid metadata JSON: {exc}", path=str(metadata_path)))
        return issues

    manifest_schema = _load_schema(repo_root, "zeus.plugin.schema.json")
    metadata_schema = _load_schema(repo_root, "registry.metadata.schema.json")

    issues.extend(_collect_schema_errors(Draft202012Validator(manifest_schema), manifest, str(manifest_path)))
    issues.extend(_collect_schema_errors(Draft202012Validator(metadata_schema), metadata, str(metadata_path)))

    folder_id = plugin_dir.name
    if manifest.get("id") != folder_id:
        issues.append(Issue(code="ID", message=f"manifest.id must equal folder name '{folder_id}'", path=str(manifest_path)))
    if metadata.get("id") != folder_id:
        issues.append(Issue(code="ID", message=f"metadata.id must equal folder name '{folder_id}'", path=str(metadata_path)))

    manifest_version = manifest.get("version")
    metadata_version = metadata.get("version")
    if manifest_version and metadata_version and manifest_version != metadata_version:
        issues.append(Issue(code="VERSION", message="manifest.version must equal metadata.version", path=str(plugin_dir)))

    components = manifest.get("components", {})
    for component_name, component_def in components.items():
        entry = component_def.get("entry")
        if entry:
            entry_path = plugin_dir / entry
            if not entry_path.exists():
                issues.append(
                    Issue(
                        code="ENTRY",
                        message=f"components.{component_name}.entry '{entry}' does not exist",
                        path=str(manifest_path),
                    )
                )

    min_ver = metadata.get("min_zeus_version")
    if isinstance(min_ver, str) and _version_tuple(min_ver) is None:
        issues.append(Issue(code="VERSION", message="min_zeus_version must be semver x.y.z", path=str(metadata_path)))

    return issues


def validate_registry(repo_root: Path) -> list[Issue]:
    issues: list[Issue] = []
    plugins_dir = repo_root / "plugins"
    if not plugins_dir.exists():
        return [Issue(code="FILES", message="Missing plugins/ directory", path=str(plugins_dir))]

    plugin_dirs = sorted([p for p in plugins_dir.iterdir() if p.is_dir()])
    discovered_ids = [p.name for p in plugin_dirs]

    for plugin_dir in plugin_dirs:
        issues.extend(validate_plugin_folder(repo_root, plugin_dir))

    index_path = repo_root / "index.json"
    if not index_path.exists():
        issues.append(Issue(code="FILES", message="Missing index.json", path=str(index_path)))
        return issues

    try:
        index_data = _load_json(index_path)
    except Exception as exc:  # pragma: no cover
        issues.append(Issue(code="JSON", message=f"Invalid index.json: {exc}", path=str(index_path)))
        return issues

    if not isinstance(index_data, list):
        issues.append(Issue(code="SCHEMA", message="index.json must be an array", path=str(index_path)))
        return issues

    indexed_ids: list[str] = []
    for i, entry in enumerate(index_data):
        if not isinstance(entry, dict):
            issues.append(Issue(code="SCHEMA", message="index entry must be an object", path=f"{index_path}:{i}"))
            continue
        plugin_id = entry.get("id")
        metadata_path = entry.get("metadata_path")
        manifest_path = entry.get("manifest_path")
        if not isinstance(plugin_id, str):
            issues.append(Issue(code="SCHEMA", message="index entry id must be string", path=f"{index_path}:{i}"))
            continue
        indexed_ids.append(plugin_id)
        expected_meta = f"plugins/{plugin_id}/metadata.json"
        expected_manifest = f"plugins/{plugin_id}/zeus.plugin.json"
        if metadata_path != expected_meta:
            issues.append(
                Issue(
                    code="INDEX",
                    message=f"metadata_path should be '{expected_meta}'",
                    path=f"{index_path}:{i}",
                )
            )
        if manifest_path != expected_manifest:
            issues.append(
                Issue(
                    code="INDEX",
                    message=f"manifest_path should be '{expected_manifest}'",
                    path=f"{index_path}:{i}",
                )
            )

    missing_from_index = sorted(set(discovered_ids) - set(indexed_ids))
    if missing_from_index:
        issues.append(
            Issue(
                code="INDEX",
                message=f"Plugins missing from index.json: {', '.join(missing_from_index)}",
                path=str(index_path),
            )
        )

    extra_in_index = sorted(set(indexed_ids) - set(discovered_ids))
    if extra_in_index:
        issues.append(
            Issue(
                code="INDEX",
                message=f"index.json has unknown plugin ids: {', '.join(extra_in_index)}",
                path=str(index_path),
            )
        )

    return issues
