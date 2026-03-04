#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zeus_plugins.validation import validate_registry


def main() -> int:
    issues = validate_registry(ROOT)
    payload = {
        "ok": len(issues) == 0,
        "issue_count": len(issues),
        "issues": [issue.__dict__ for issue in issues],
    }
    print(json.dumps(payload, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
