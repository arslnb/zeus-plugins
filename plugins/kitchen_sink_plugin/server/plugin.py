from __future__ import annotations

import asyncio
import hmac
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_telegram_envelopes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    envelopes: list[dict[str, Any]] = []
    update_id = payload.get("update_id")
    update_type_keys = (
        "message",
        "edited_message",
        "channel_post",
        "edited_channel_post",
        "business_message",
        "edited_business_message",
    )

    for update_type in update_type_keys:
        message = payload.get(update_type)
        if not isinstance(message, dict):
            continue

        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        chat_id = str(chat.get("id") or "").strip()
        from_user = message.get("from") if isinstance(message.get("from"), dict) else {}

        sender_id = str(from_user.get("id") or "").strip() or chat_id
        sender_display = str(from_user.get("username") or "").strip()
        if not sender_display:
            sender_name = " ".join(
                value.strip()
                for value in (
                    str(from_user.get("first_name") or ""),
                    str(from_user.get("last_name") or ""),
                )
                if value.strip()
            )
            sender_display = sender_name or str(chat.get("title") or "").strip()

        text = str(message.get("text") or message.get("caption") or "")
        attachments: list[dict[str, Any]] = []
        if isinstance(message.get("photo"), list) and message.get("photo"):
            attachments.append({"type": "photo", "count": len(message["photo"])})

        for key in ("video", "audio", "voice", "document", "sticker", "animation", "contact", "location"):
            value = message.get(key)
            if value is None:
                continue
            attachment: dict[str, Any] = {"type": key}
            if isinstance(value, dict):
                attachment["file_id"] = str(value.get("file_id") or "")
                attachment["mime_type"] = str(value.get("mime_type") or "")
            attachments.append(attachment)

        ts = message.get("date")
        received_at = datetime.now(timezone.utc)
        if isinstance(ts, int):
            received_at = datetime.fromtimestamp(ts, tz=timezone.utc)
        elif isinstance(ts, str) and ts.isdigit():
            received_at = datetime.fromtimestamp(int(ts), tz=timezone.utc)

        message_id_raw = str(message.get("message_id") or "").strip()
        update_id_raw = str(update_id).strip() if update_id is not None else ""
        dedupe_id = message_id_raw or update_id_raw or secrets.token_hex(8)
        message_id = f"tgk-{chat_id or 'unknown'}-{dedupe_id}"

        envelopes.append(
            {
                "message_id": message_id,
                "sender_id": sender_id,
                "sender_display": sender_display,
                "text": text,
                "attachments": attachments,
                "received_at": received_at.isoformat(),
                "thread_hint": chat_id or sender_id,
                "metadata": {
                    "plugin_id": "kitchen_sink_plugin",
                    "provider": "telegram_bot_api",
                    "source": "telegram_kitchen_sink",
                    "update_id": update_id_raw,
                    "update_type": update_type,
                    "reply_context": {
                        "chat_id": chat_id,
                    },
                    "chat": {
                        "id": chat.get("id"),
                        "type": chat.get("type"),
                        "title": chat.get("title"),
                        "username": chat.get("username"),
                    },
                    "raw": message,
                },
            }
        )

    return envelopes


def _telegram_send_message(
    bot_token: str,
    chat_id: str,
    text: str,
    reply_to_message_id: str | None = None,
) -> tuple[bool, str, str]:
    endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id

    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=encoded,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        error_body = b""
        try:
            error_body = exc.read()
        except Exception:
            error_body = b""
        detail = error_body.decode("utf-8", errors="replace").strip() or f"http_{exc.code}"
        return False, "", detail
    except Exception as exc:
        return False, "", str(exc)

    try:
        parsed = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return False, "", "invalid_telegram_response"

    if not isinstance(parsed, dict):
        return False, "", "telegram_response_not_object"

    if not bool(parsed.get("ok")):
        description = str(parsed.get("description") or "telegram_send_failed")
        return False, "", description

    result = parsed.get("result")
    if isinstance(result, dict):
        provider_message_id = str(result.get("message_id") or "").strip()
        return True, provider_message_id, ""

    return True, "", ""


def _telegram_set_webhook(
    *,
    bot_token: str,
    webhook_url: str,
    secret_token: str,
) -> tuple[bool, str]:
    endpoint = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    payload: dict[str, Any] = {"url": webhook_url}
    if secret_token:
        payload["secret_token"] = secret_token
    encoded = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=encoded,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        error_body = b""
        try:
            error_body = exc.read()
        except Exception:
            error_body = b""
        detail = error_body.decode("utf-8", errors="replace").strip() or f"http_{exc.code}"
        return False, detail
    except Exception as exc:
        return False, str(exc)

    try:
        parsed = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return False, "invalid_telegram_webhook_response"
    if not isinstance(parsed, dict):
        return False, "telegram_webhook_response_not_object"
    if not bool(parsed.get("ok")):
        return False, str(parsed.get("description") or "telegram_webhook_registration_failed")
    return True, ""


def _github_request_json(*, access_token: str, path: str) -> Any:
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "ZeusKitchenSinkPlugin/1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def _format_github_me(profile: dict[str, Any]) -> str:
    login = str(profile.get("login") or "").strip() or "(unknown)"
    name = str(profile.get("name") or "").strip()
    company = str(profile.get("company") or "").strip()
    location = str(profile.get("location") or "").strip()
    bio = str(profile.get("bio") or "").strip()
    public_repos = int(profile.get("public_repos") or 0)
    followers = int(profile.get("followers") or 0)
    following = int(profile.get("following") or 0)
    parts = [f"GitHub: {login}"]
    if name:
        parts.append(f"Name: {name}")
    if company:
        parts.append(f"Company: {company}")
    if location:
        parts.append(f"Location: {location}")
    parts.append(f"Repos: {public_repos} | Followers: {followers} | Following: {following}")
    if bio:
        parts.append(f"Bio: {bio}")
    return "\n".join(parts)


def _format_github_notifications(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return "GitHub: no unread notifications."
    lines = ["GitHub notifications:"]
    for item in rows[:5]:
        if not isinstance(item, dict):
            continue
        repo = item.get("repository") if isinstance(item.get("repository"), dict) else {}
        subject = item.get("subject") if isinstance(item.get("subject"), dict) else {}
        repo_name = str(repo.get("full_name") or repo.get("name") or "unknown/repo").strip()
        subject_type = str(subject.get("type") or "item").strip()
        title = str(subject.get("title") or "(untitled)").strip()
        reason = str(item.get("reason") or "").strip()
        line = f"- {repo_name}: {subject_type} - {title}"
        if reason:
            line += f" [{reason}]"
        lines.append(line)
    return "\n".join(lines)


class TelegramKitchenSinkAdapter:
    def __init__(
        self,
        *,
        webhook_secret: str = "",
        bot_token: str = "",
        github_access_token: str = "",
        send_message_fn=None,
        set_webhook_fn=None,
        github_request_fn=None,
    ) -> None:
        self._webhook_secret = str(webhook_secret or "").strip()
        self._bot_token = str(bot_token or "").strip()
        self._github_access_token = str(github_access_token or "").strip()
        self._send_message = send_message_fn or _telegram_send_message
        self._set_webhook = set_webhook_fn or _telegram_set_webhook
        self._github_request_json = github_request_fn or _github_request_json

    async def ensure_webhook(self, *, public_base_url: str) -> None:
        base = str(public_base_url or "").strip().rstrip("/")
        if not base or not self._bot_token:
            return
        webhook_url = f"{base}/v1/channels/telegram_kitchen_sink/webhook"
        ok, detail = await asyncio.to_thread(
            self._set_webhook,
            bot_token=self._bot_token,
            webhook_url=webhook_url,
            secret_token=self._webhook_secret,
        )
        if not ok:
            raise RuntimeError(f"telegram_webhook_registration_failed:{detail}")

    async def verify_webhook(self, request):
        challenge = str(request.query_params.get("challenge") or "").strip()
        if challenge:
            return challenge
        return None

    def _command_response(self, command_text: str) -> str | None:
        command = str(command_text or "").strip().lower()
        if command in {"/help", "/start", "/github_help"}:
            return "Kitchen Sink Plugin commands:\n/github_me\n/github_notifications"
        if command == "/github_me":
            if not self._github_access_token:
                return "GitHub is not connected. Connect the server_github OAuth provider first."
            profile = self._github_request_json(access_token=self._github_access_token, path="/user")
            if not isinstance(profile, dict):
                return "GitHub profile lookup returned an invalid response."
            return _format_github_me(profile)
        if command == "/github_notifications":
            if not self._github_access_token:
                return "GitHub is not connected. Connect the server_github OAuth provider first."
            rows = self._github_request_json(
                access_token=self._github_access_token,
                path="/notifications?all=false&participating=false&per_page=5",
            )
            return _format_github_notifications(rows)
        return None

    async def _maybe_handle_commands(self, envelopes: list[dict[str, Any]]) -> None:
        if not self._bot_token:
            return
        for envelope in envelopes:
            metadata = envelope.get("metadata") if isinstance(envelope.get("metadata"), dict) else {}
            raw_message = metadata.get("raw") if isinstance(metadata.get("raw"), dict) else {}
            chat = metadata.get("chat") if isinstance(metadata.get("chat"), dict) else {}
            chat_id = str(chat.get("id") or envelope.get("thread_hint") or "").strip()
            if not chat_id:
                continue
            text = str(envelope.get("text") or "").strip()
            if not text.startswith("/"):
                continue
            try:
                reply_text = await asyncio.to_thread(self._command_response, text)
            except urllib.error.HTTPError as exc:
                detail = ""
                try:
                    detail = exc.read().decode("utf-8", errors="replace").strip()
                except Exception:
                    detail = ""
                reply_text = f"GitHub API error: {detail or f'http_{exc.code}'}"
            except Exception as exc:
                reply_text = f"Command failed: {exc}"
            if not reply_text:
                continue
            reply_to_message_id = str(raw_message.get("message_id") or "").strip() or None
            await asyncio.to_thread(
                self._send_message,
                self._bot_token,
                chat_id,
                reply_text,
                reply_to_message_id,
            )

    async def ingest_webhook(self, request=None, body=b""):
        if self._webhook_secret:
            supplied = ""
            if request is not None and hasattr(request, "headers"):
                supplied = str(request.headers.get("X-Telegram-Bot-Api-Secret-Token") or "").strip()
            if not supplied or not hmac.compare_digest(supplied, self._webhook_secret):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_telegram_secret")

        try:
            payload = json.loads((body or b"{}").decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_json") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payload_must_be_object")

        envelopes = _extract_telegram_envelopes(payload)
        await self._maybe_handle_commands(envelopes)
        return envelopes

    async def send(self, payload):
        chat_id = str(payload.get("chat_id") or "").strip()
        text = str(payload.get("text") or "").strip()
        reply_to_message_id = str(payload.get("reply_to_message_id") or "").strip() or None
        if not chat_id or not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="missing_required_fields: chat_id,text",
            )
        if not self._bot_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="telegram_bot_not_configured",
            )

        ok, provider_message_id, error_detail = await asyncio.to_thread(
            self._send_message,
            self._bot_token,
            chat_id,
            text,
            reply_to_message_id,
        )
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"telegram_send_failed:{error_detail}",
            )
        return {
            "ok": True,
            "provider_message_id": provider_message_id,
        }


class KitchenSinkServerPlugin:
    def __init__(self, ctx):
        secret_refs = dict(ctx.secret_refs or {})
        oauth_connections = dict(ctx.oauth_connections or {})
        github_oauth = oauth_connections.get("server_github") if isinstance(oauth_connections.get("server_github"), dict) else {}
        self._public_base_url = str(getattr(ctx.settings, "public_base_url", "") or "").strip()
        self._adapter = TelegramKitchenSinkAdapter(
            webhook_secret=str(secret_refs.get("telegram_webhook_secret") or ""),
            bot_token=str(secret_refs.get("telegram_bot_token") or ""),
            github_access_token=str(github_oauth.get("access_token") or ""),
        )
        self._custom_route = "kitchen-sink-events"
        self._enabled = False

    async def on_enable(self):
        self._enabled = True
        await self._adapter.ensure_webhook(public_base_url=self._public_base_url)

    def channels(self):
        return {"telegram_kitchen_sink": self._adapter}

    def webhooks(self):
        return {
            self._custom_route: {
                "methods": ["POST"],
                "handler": self.handle_custom_event,
            }
        }

    async def handle_custom_event(self, request=None, body=b"", **kwargs):
        del request, kwargs
        try:
            payload = json.loads((body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}
        event_type = str(payload.get("type") or "unknown")
        return {
            "status_code": 202,
            "body": {"ok": True, "event_type": event_type},
            "envelopes": [
                {
                    "message_id": f"kitchen-webhook-{event_type}",
                    "channel": "webhook:kitchen-sink-events",
                    "sender_id": "kitchen_sink_plugin",
                    "sender_display": "Kitchen Sink Webhook",
                    "text": f"custom webhook:{event_type}",
                    "attachments": [],
                    "received_at": _now_iso(),
                    "thread_hint": "kitchen-sink-events",
                    "metadata": {
                        "plugin_id": "kitchen_sink_plugin",
                        "source": "kitchen_sink_webhook",
                        "enabled": self._enabled,
                    },
                }
            ],
        }


def check_server_environment(context=None, ctx=None):
    del context, ctx
    return True, "Environment ready."


def register(ctx):
    return KitchenSinkServerPlugin(ctx)
