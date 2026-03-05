---
summary: Use gws tools for common Gmail, Drive, and Calendar actions.
---
# GWS Assistant

Use this skill when handling Google Workspace operations through the `gws` plugin tools.

## Guidance

- Prefer `gws_gmail_unread` for inbox triage.
- Use `gws_execute` for explicit Gmail/Drive/Calendar commands.
- Keep commands narrow and deterministic (limit result sets, include explicit ids when possible).
