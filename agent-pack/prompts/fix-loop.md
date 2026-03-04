Given validation output JSON from `zeus plugin check --json`, apply only the minimal edits needed to fix all issues.

Rules:
- Keep public behavior stable.
- Do not rename plugin id unless schema forces it.
- Return changed files and rerun command.
