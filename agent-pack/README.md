# Zeus Agent Pack

Minimal context pack for agents that generate Zeus plugins quickly and reliably.

## Use this order
1. `prompts/scaffold.md`
2. `prompts/fix-loop.md`
3. `prompts/publish-pr.md`
4. `checklist.md`

## Constraints for agents
- Do not invent fields not present in `schemas/*.json`.
- Keep plugin ids lowercase snake_case.
- Always run `zeus plugin check <plugin-path> --json` before proposing PR.
