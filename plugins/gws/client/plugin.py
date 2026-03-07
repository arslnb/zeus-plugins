from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

DEFAULT_GWS_BINARY = "gws"
DEFAULT_USER_ID = "me"
DEFAULT_QUERY = "in:inbox is:unread"
DEFAULT_MAX_RESULTS = 5
DEFAULT_TIMEOUT_SECONDS = 45
MAX_RESULTS_LIMIT = 25


def register_tools() -> dict[str, Any]:
    return {
        "gws_execute": {
            "runtime_name": "gws_execute",
            "description": (
                "Run an explicit Google Workspace CLI operation through gws. "
                "Use this for Gmail, Drive, or Calendar actions when you know the exact operation."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "Space-delimited gws operation, for example 'drive files list'.",
                    },
                    "params": {
                        "type": "object",
                        "description": "Optional JSON object passed via --params.",
                    },
                    "body": {
                        "type": "object",
                        "description": "Optional JSON object passed via --json.",
                    },
                    "extra_args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional extra CLI arguments appended to the gws command.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Optional timeout override in seconds.",
                    },
                },
                "required": ["operation"],
                "additionalProperties": False,
            },
            "handler": gws_execute,
            "risk_level": 1,
            "side_effect_tier": "B",
            "idempotent": False,
            "max_payload_hint": 64000,
        },
        "gws_gmail_unread": {
            "runtime_name": "gws_gmail_unread",
            "description": (
                "List unread Gmail inbox messages and return structured summaries "
                "with sender, subject, date, and snippet."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optional Gmail search query. Defaults to unread inbox mail.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum unread messages to fetch, between 1 and 25.",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Optional Gmail user id. Defaults to 'me'.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Optional timeout override in seconds.",
                    },
                },
                "additionalProperties": False,
            },
            "handler": gws_gmail_unread,
            "risk_level": 1,
            "side_effect_tier": "A",
            "idempotent": True,
            "max_payload_hint": 32000,
        },
    }


def gws_execute(context: dict | None = None) -> dict[str, Any]:
    """Run a raw gws operation.

    Required context fields:
      - operation: string, e.g. "drive files list" or "calendar events insert"

    Optional context fields:
      - params: object, mapped to --params
      - body: object, mapped to --json
      - extra_args: array[string], appended to the command
      - timeout_seconds: int
      - gws_binary: string
    """
    request = context or {}
    client_cfg = _client_config(request)

    operation = request.get("operation")
    if not isinstance(operation, str) or not operation.strip():
        return {
            "ok": False,
            "error": "Missing 'operation'. Example: 'gmail users messages list'",
        }

    operation_parts = [part for part in operation.strip().split(" ") if part]
    if len(operation_parts) < 3:
        return {
            "ok": False,
            "error": "Operation must include service resource method, e.g. 'drive files list'",
        }

    params = request.get("params")
    if params is not None and not isinstance(params, dict):
        return {"ok": False, "error": "'params' must be an object when provided"}

    body = request.get("body")
    if body is not None and not isinstance(body, dict):
        return {"ok": False, "error": "'body' must be an object when provided"}

    extra_args = request.get("extra_args")
    if extra_args is None:
        extra_args = []
    if not isinstance(extra_args, list) or not all(isinstance(item, str) for item in extra_args):
        return {
            "ok": False,
            "error": "'extra_args' must be an array of strings when provided",
        }

    gws_binary = _setting(request, client_cfg, "gws_binary", DEFAULT_GWS_BINARY)
    timeout_seconds = _bounded_int(
        _setting(request, client_cfg, "timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
        default=DEFAULT_TIMEOUT_SECONDS,
        minimum=5,
        maximum=300,
    )

    return _run_gws(
        gws_binary=gws_binary,
        operation=operation_parts,
        params=params,
        body=body,
        extra_args=extra_args,
        timeout_seconds=timeout_seconds,
    )


def gws_gmail_unread(context: dict | None = None) -> dict[str, Any]:
    """List unread inbox messages and enrich with message metadata.

    Optional context fields:
      - query: Gmail search query (default: in:inbox is:unread)
      - max_results: 1..25 (default: 5)
      - user_id: Gmail user id (default: me)
      - timeout_seconds: int
      - gws_binary: string
    """
    request = context or {}
    client_cfg = _client_config(request)

    gws_binary = _setting(request, client_cfg, "gws_binary", DEFAULT_GWS_BINARY)
    timeout_seconds = _bounded_int(
        _setting(request, client_cfg, "timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
        default=DEFAULT_TIMEOUT_SECONDS,
        minimum=5,
        maximum=300,
    )
    user_id = str(_setting(request, client_cfg, "user_id", _setting(request, client_cfg, "default_user_id", DEFAULT_USER_ID)))
    query = str(_setting(request, client_cfg, "query", _setting(request, client_cfg, "default_query", DEFAULT_QUERY)))
    max_results = _bounded_int(
        _setting(request, client_cfg, "max_results", _setting(request, client_cfg, "default_max_results", DEFAULT_MAX_RESULTS)),
        default=DEFAULT_MAX_RESULTS,
        minimum=1,
        maximum=MAX_RESULTS_LIMIT,
    )

    listed = _run_gws(
        gws_binary=gws_binary,
        operation=["gmail", "users", "messages", "list"],
        params={"userId": user_id, "q": query, "maxResults": max_results},
        timeout_seconds=timeout_seconds,
    )
    if not listed.get("ok"):
        return listed

    raw_list = listed.get("output")
    if not isinstance(raw_list, dict):
        return {
            "ok": False,
            "error": "Unexpected gws response type from gmail users messages list",
            "output": raw_list,
        }

    messages = raw_list.get("messages")
    if not isinstance(messages, list):
        messages = []

    summaries: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for item in messages:
        if not isinstance(item, dict):
            continue
        message_id = item.get("id")
        thread_id = item.get("threadId")
        if not isinstance(message_id, str) or not message_id:
            continue

        fetched = _run_gws(
            gws_binary=gws_binary,
            operation=["gmail", "users", "messages", "get"],
            params={
                "userId": user_id,
                "id": message_id,
                "format": "metadata",
                "metadataHeaders": ["From", "Subject", "Date"],
            },
            timeout_seconds=timeout_seconds,
        )
        if not fetched.get("ok"):
            errors.append(
                {
                    "id": message_id,
                    "thread_id": thread_id,
                    "error": fetched.get("error", "Failed to fetch message"),
                    "details": fetched.get("stderr", ""),
                }
            )
            continue

        detail = fetched.get("output")
        if not isinstance(detail, dict):
            errors.append(
                {
                    "id": message_id,
                    "thread_id": thread_id,
                    "error": "Unexpected gws response type from gmail users messages get",
                }
            )
            continue

        headers = detail.get("payload", {}).get("headers", [])
        summaries.append(
            {
                "id": message_id,
                "thread_id": thread_id,
                "from": _header(headers, "From"),
                "subject": _header(headers, "Subject"),
                "date": _header(headers, "Date"),
                "snippet": detail.get("snippet", ""),
            }
        )

    return {
        "ok": True,
        "user_id": user_id,
        "query": query,
        "requested_max_results": max_results,
        "message_count": len(summaries),
        "messages": summaries,
        "errors": errors,
    }


def _run_gws(
    gws_binary: str,
    operation: list[str],
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    extra_args: list[str] | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    binary = str(gws_binary).strip() or DEFAULT_GWS_BINARY
    if shutil.which(binary) is None:
        return {
            "ok": False,
            "error": f"gws executable not found in PATH: '{binary}'",
            "hint": "Install with `npm install -g @googleworkspace/cli`, then rerun the Zeus plugin Install flow so Zeus can handle auth.",
        }

    command = [binary, *operation]
    if params is not None:
        command.extend(["--params", json.dumps(params, separators=(",", ":"))])
    if body is not None:
        command.extend(["--json", json.dumps(body, separators=(",", ":"))])
    if extra_args:
        command.extend(extra_args)

    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"gws command timed out after {timeout_seconds}s",
            "command": command,
        }

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    parsed_output: Any
    if stdout:
        try:
            parsed_output = json.loads(stdout)
        except json.JSONDecodeError:
            parsed_output = stdout
    else:
        parsed_output = {}

    if proc.returncode != 0:
        return {
            "ok": False,
            "error": "gws command failed",
            "returncode": proc.returncode,
            "command": command,
            "stderr": stderr,
            "output": parsed_output,
        }

    return {
        "ok": True,
        "command": command,
        "stderr": stderr,
        "output": parsed_output,
    }


def _client_config(context: dict[str, Any]) -> dict[str, Any]:
    config = context.get("config")
    if not isinstance(config, dict):
        return {}
    client_cfg = config.get("client")
    if not isinstance(client_cfg, dict):
        return {}
    return client_cfg


def _setting(
    request: dict[str, Any],
    client_cfg: dict[str, Any],
    key: str,
    default: Any,
) -> Any:
    if key in request:
        return request[key]
    if key in client_cfg:
        return client_cfg[key]
    return default


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _header(headers: Any, name: str) -> str:
    if not isinstance(headers, list):
        return ""
    for header in headers:
        if not isinstance(header, dict):
            continue
        if str(header.get("name", "")).lower() != name.lower():
            continue
        value = header.get("value")
        return str(value) if value is not None else ""
    return ""
