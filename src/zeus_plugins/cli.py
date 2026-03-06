from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from zeus_plugins.validation import Issue, validate_plugin_folder, validate_registry

DEFAULT_MANIFEST = {
    "schema_version": 1,
    "id": "",
    "name": "",
    "version": "0.1.0",
    "description": "",
    "components": {},
    "config_schema": {
        "client": {},
        "server": {},
    },
    "prerequisites": {
        "cli": [],
    },
    "oauth": {
        "mode": "none",
    },
}


def _find_repo_root(*starts: Path) -> Path | None:
    marker = Path("schemas") / "zeus.plugin.schema.json"
    for start in starts:
        current = start.resolve()
        candidates = [current, *current.parents]
        for candidate in candidates:
            if (candidate / marker).exists():
                return candidate
    return None


def _write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _print_issues_json(issues: list[Issue], target: str) -> None:
    payload = {
        "ok": len(issues) == 0,
        "target": target,
        "issue_count": len(issues),
        "issues": [issue.__dict__ for issue in issues],
    }
    print(json.dumps(payload, indent=2))


def _print_issues_text(issues: list[Issue]) -> None:
    if not issues:
        print("Validation passed.")
        return
    print(f"Validation failed with {len(issues)} issue(s):")
    for issue in issues:
        print(f"- [{issue.code}] {issue.path}: {issue.message}")


def cmd_init(args: argparse.Namespace) -> int:
    plugin_id = args.plugin_id.strip()
    out_dir = Path(args.dir).expanduser().resolve() / plugin_id

    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        print(f"Refusing to overwrite non-empty directory: {out_dir}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = dict(DEFAULT_MANIFEST)
    manifest["id"] = plugin_id
    manifest["name"] = args.name or plugin_id.replace("_", " ").title()
    manifest["description"] = args.description or f"{manifest['name']} Zeus plugin"

    if args.runtime == "daemon":
        manifest["components"] = {"client": {"runtime": "python", "entry": "client/plugin.py"}}
    elif args.runtime == "channel":
        manifest["components"] = {"server": {"runtime": "python", "entry": "server/plugin.py", "channels": []}}
    else:
        manifest["components"] = {
            "client": {"runtime": "python", "entry": "client/plugin.py"},
            "server": {"runtime": "python", "entry": "server/plugin.py", "channels": []},
        }

    metadata = {
        "id": plugin_id,
        "name": manifest["name"],
        "version": manifest["version"],
        "summary": manifest["description"],
        "owner": args.owner,
        "runtime": ["client", "server"] if args.runtime == "hybrid" else ["client" if args.runtime == "daemon" else "server"],
        "categories": [c.strip() for c in args.categories.split(",") if c.strip()] if args.categories else ["productivity"],
        "min_zeus_version": "1.0.0",
        "source_repo": args.source_repo,
        "license": args.license,
    }

    _write_json(out_dir / "zeus.plugin.json", manifest)
    _write_json(out_dir / "metadata.json", metadata)
    _write_json(
        out_dir / "examples" / "install.json",
        {"source_type": "path", "source": str(out_dir), "force": True},
    )
    _write_json(
        out_dir / "examples" / "config.json",
        {
            "plugin_id": plugin_id,
            "config": {"client": {}, "server": {}},
            "secrets": {"client": {}, "server": {}},
            "run_setup": True,
        },
    )

    if args.runtime in {"daemon", "hybrid"}:
        (out_dir / "client").mkdir(parents=True, exist_ok=True)
        (out_dir / "client" / "plugin.py").write_text(
            """from __future__ import annotations


def register_tools():
    return {
        \"ping\": ping,
    }


def ping(context: dict | None = None) -> dict:
    return {\"ok\": True, \"message\": \"pong from %s\"}
""" % plugin_id,
            encoding="utf-8",
        )

    if args.runtime in {"channel", "hybrid"}:
        (out_dir / "server").mkdir(parents=True, exist_ok=True)
        (out_dir / "server" / "plugin.py").write_text(
            """from __future__ import annotations


def channels():
    return []


def webhooks():
    return {}
""",
            encoding="utf-8",
        )

    (out_dir / "README.md").write_text(
        """# {name}

Generated with `zeus plugin init`.

## Local check

```bash
zeus plugin check {path} --json
```

## Install

Use `examples/install.json` with `POST /api/plugins/install`.
""".format(name=manifest["name"], path=out_dir),
        encoding="utf-8",
    )

    print(f"Created plugin scaffold at {out_dir}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()

    if args.registry:
        repo_root = target
        issues = validate_registry(repo_root)
        if args.json:
            _print_issues_json(issues, str(repo_root))
        else:
            _print_issues_text(issues)
        return 0 if not issues else 1

    if not (target / "zeus.plugin.json").exists() and (target / "plugins").exists():
        issues = validate_registry(target)
        if args.json:
            _print_issues_json(issues, str(target))
        else:
            _print_issues_text(issues)
        return 0 if not issues else 1

    repo_root = _find_repo_root(Path.cwd(), target)
    if repo_root is None:
        print("Could not locate repo root containing schemas/zeus.plugin.schema.json", file=sys.stderr)
        return 2
    issues = validate_plugin_folder(repo_root, target)
    if args.json:
        _print_issues_json(issues, str(target))
    else:
        _print_issues_text(issues)
    return 0 if not issues else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zeus", description="Zeus plugin tooling")
    subparsers = parser.add_subparsers(dest="command")

    plugin_parser = subparsers.add_parser("plugin", help="Plugin commands")
    plugin_subparsers = plugin_parser.add_subparsers(dest="plugin_command")

    init_parser = plugin_subparsers.add_parser("init", help="Initialize a plugin scaffold")
    init_parser.add_argument("plugin_id", help="Plugin id and output directory name")
    init_parser.add_argument("--dir", default="plugins", help="Base directory for new plugin folder")
    init_parser.add_argument("--runtime", choices=["daemon", "channel", "hybrid"], default="daemon")
    init_parser.add_argument("--name", default="", help="Human-readable plugin name")
    init_parser.add_argument("--description", default="", help="Short plugin description")
    init_parser.add_argument("--owner", default="community", help="Owner/maintainer id")
    init_parser.add_argument("--source-repo", default="https://github.com/arslnb/zeus-plugins", help="Source repo URL")
    init_parser.add_argument("--license", default="MIT", help="Plugin license")
    init_parser.add_argument("--categories", default="", help="Comma-separated categories")
    init_parser.add_argument("--force", action="store_true", help="Overwrite directory if it exists")
    init_parser.set_defaults(func=cmd_init)

    check_parser = plugin_subparsers.add_parser("check", help="Validate a plugin or full registry")
    check_parser.add_argument("path", nargs="?", default=".", help="Plugin folder path or registry root")
    check_parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    check_parser.add_argument("--registry", action="store_true", help="Force registry-level validation")
    check_parser.set_defaults(func=cmd_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "plugin" or not hasattr(args, "func"):
        parser.print_help()
        return 2

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
