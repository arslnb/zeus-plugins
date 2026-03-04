from __future__ import annotations


def register_tools():
    return {
        "email_digest_plan": email_digest_plan,
    }


def email_digest_plan(context: dict | None = None) -> dict:
    tz = (context or {}).get("timezone", "UTC")
    return {
        "ok": True,
        "workflow": [
            "fetch unread emails",
            "cluster by sender/topic",
            "summarize action items"
        ],
        "timezone": tz,
    }
