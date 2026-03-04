from __future__ import annotations


def register_tools():
    return {
        "hello_notch_ping": hello_notch_ping,
    }


def hello_notch_ping(context: dict | None = None) -> dict:
    return {
        "ok": True,
        "message": "hello from hello_notch",
    }
