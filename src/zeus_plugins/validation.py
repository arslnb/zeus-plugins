from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:  # pragma: no cover - dependency presence varies by environment
    Draft202012Validator = None  # type: ignore[assignment]


@dataclass
class Issue:
    code: str
    message: str
    path: str


_AUTO_RUN_BLOCKLIST = ("&&", "||", ";", "|", "\n", "\r")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_schema(repo_root: Path, name: str) -> dict[str, Any]:
    return _load_json(repo_root / "schemas" / name)


def _require_jsonschema() -> Any:
    if Draft202012Validator is None:
        raise RuntimeError("jsonschema is required for schema validation; install zeus-plugins dependencies first")
    return Draft202012Validator


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


def _looks_like_shell_command(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    if not candidate or re.match(r"^https?://", candidate):
        return False
    return "\n" not in candidate and "\r" not in candidate


def _normalize_install_options(prerequisite: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    raw_install_options = prerequisite.get("install_options")
    if isinstance(raw_install_options, list):
        for option in raw_install_options:
            if isinstance(option, dict):
                normalized.append(dict(option))

    auto_install_commands = prerequisite.get("auto_install_commands")
    if isinstance(auto_install_commands, dict):
        for platform_name, command in auto_install_commands.items():
            if not _looks_like_shell_command(command):
                continue
            normalized.append(
                {
                    "type": "shell",
                    "label": f"Install {prerequisite.get('name') or prerequisite.get('id') or 'prerequisite'}",
                    "description": prerequisite.get("description") or prerequisite.get("why") or "",
                    "command": str(command).strip(),
                    "auto_run": True,
                    "requires_admin": False,
                    "platforms": [platform_name],
                }
            )

    install_hint = prerequisite.get("install_hint")
    if _looks_like_shell_command(install_hint) and not any(
        option.get("type") == "shell" and str(option.get("command") or "").strip() == str(install_hint).strip()
        for option in normalized
        if isinstance(option, dict)
    ):
        normalized.append(
            {
                "type": "shell",
                "label": f"Install {prerequisite.get('name') or prerequisite.get('id') or 'prerequisite'}",
                "description": prerequisite.get("description") or prerequisite.get("why") or "",
                "command": str(install_hint).strip(),
                "auto_run": False,
                "requires_admin": False,
            }
        )

    for url_key, label in (("install_url", "Open install guide"), ("docs_url", "Open docs")):
        url_value = prerequisite.get(url_key)
        if not isinstance(url_value, str) or not url_value.strip():
            continue
        if any(
            option.get("type") == "open_url" and str(option.get("url") or "").strip() == url_value.strip()
            for option in normalized
            if isinstance(option, dict)
        ):
            continue
        normalized.append(
            {
                "type": "open_url",
                "label": label,
                "description": prerequisite.get("description") or prerequisite.get("why") or "",
                "url": url_value.strip(),
            }
        )

    return normalized


def _validate_prerequisites(manifest: dict[str, Any], manifest_path: Path) -> list[Issue]:
    issues: list[Issue] = []
    prerequisites = manifest.get("prerequisites")
    if not isinstance(prerequisites, dict):
        return issues
    cli_prerequisites = prerequisites.get("cli")
    if not isinstance(cli_prerequisites, list):
        return issues

    seen_ids: set[str] = set()
    for index, raw_entry in enumerate(cli_prerequisites):
        if isinstance(raw_entry, str):
            continue
        if not isinstance(raw_entry, dict):
            continue
        entry_path = f"{manifest_path}:prerequisites/cli/{index}"
        prereq_id = str(raw_entry.get("id") or "").strip()
        if prereq_id:
            if prereq_id in seen_ids:
                issues.append(Issue(code="PREREQ", message=f"duplicate prerequisite id '{prereq_id}'", path=entry_path))
            else:
                seen_ids.add(prereq_id)

        binary = str(raw_entry.get("binary") or "").strip()
        check_command = str(raw_entry.get("check_command") or raw_entry.get("command") or "").strip()
        if not binary and not check_command:
            issues.append(
                Issue(
                    code="PREREQ",
                    message="prerequisite must define binary and/or check_command",
                    path=entry_path,
                )
            )

        normalized_options = _normalize_install_options(raw_entry)
        required = bool(raw_entry.get("required"))
        if required and not normalized_options:
            issues.append(
                Issue(
                    code="PREREQ",
                    message="required prerequisite must declare install_options or an install/docs URL",
                    path=entry_path,
                )
            )

        for option_index, option in enumerate(normalized_options):
            option_path = f"{entry_path}/install_options/{option_index}"
            option_type = str(option.get("type") or "").strip()
            if option_type == "shell":
                command = str(option.get("command") or "").strip()
                auto_run = bool(option.get("auto_run"))
                requires_admin = bool(option.get("requires_admin"))
                if not command:
                    issues.append(Issue(code="PREREQ", message="shell install option requires command", path=option_path))
                    continue
                if auto_run and requires_admin:
                    issues.append(
                        Issue(
                            code="PREREQ",
                            message="auto_run shell install options cannot require admin access",
                            path=option_path,
                        )
                    )
                if auto_run and command.lstrip().startswith("sudo "):
                    issues.append(
                        Issue(
                            code="PREREQ",
                            message="auto_run shell install options cannot begin with sudo",
                            path=option_path,
                        )
                    )
                if auto_run and any(token in command for token in _AUTO_RUN_BLOCKLIST):
                    issues.append(
                        Issue(
                            code="PREREQ",
                            message="auto_run shell install options must be a single explicit command",
                            path=option_path,
                        )
                    )
            elif option_type == "open_url" and bool(option.get("auto_run")):
                issues.append(
                    Issue(
                        code="PREREQ",
                        message="open_url install options cannot be marked auto_run",
                        path=option_path,
                    )
                )

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

    validator_cls = _require_jsonschema()
    issues.extend(_collect_schema_errors(validator_cls(manifest_schema), manifest, str(manifest_path)))
    issues.extend(_collect_schema_errors(validator_cls(metadata_schema), metadata, str(metadata_path)))
    issues.extend(_validate_prerequisites(manifest, manifest_path))

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

    seen_ids: set[str] = set()
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
        if plugin_id in seen_ids:
            issues.append(Issue(code="INDEX", message=f"duplicate plugin id '{plugin_id}'", path=f"{index_path}:{i}"))
            continue
        seen_ids.add(plugin_id)
        if not isinstance(metadata_path, str) or not metadata_path:
            issues.append(Issue(code="INDEX", message="metadata_path is required", path=f"{index_path}:{i}"))
            continue
        if not isinstance(manifest_path, str) or not manifest_path:
            issues.append(Issue(code="INDEX", message="manifest_path is required", path=f"{index_path}:{i}"))
            continue

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
        manifest_file = repo_root / manifest_path
        metadata_file = repo_root / metadata_path
        if not manifest_file.exists():
            issues.append(
                Issue(
                    code="FILES",
                    message=f"manifest_path does not exist: {manifest_path}",
                    path=f"{index_path}:{i}",
                )
            )
            continue
        if not metadata_file.exists():
            issues.append(
                Issue(
                    code="FILES",
                    message=f"metadata_path does not exist: {metadata_path}",
                    path=f"{index_path}:{i}",
                )
            )
            continue
        issues.extend(validate_plugin_folder(repo_root, manifest_file.parent))

    return issues
