from __future__ import annotations

import json
from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TelegramKitchenSinkAdapter:
    def __init__(self, *, webhook_secret: str = "", send_token: str = "") -> None:
        self._webhook_secret = str(webhook_secret or "").strip()
        self._send_token = str(send_token or "").strip()

    async def verify_webhook(self, request):
        challenge = str(request.query_params.get("challenge") or "").strip()
        if challenge:
            return challenge
        return None

    async def ingest_webhook(self, request=None, body=b""):
        if self._webhook_secret:
            supplied = ""
            if request is not None and hasattr(request, "headers"):
                supplied = str(request.headers.get("X-Telegram-Bot-Api-Secret-Token") or "").strip()
            if supplied != self._webhook_secret:
                raise RuntimeError("invalid_telegram_secret")

        try:
            payload = json.loads((body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}

        message = payload.get("message") if isinstance(payload.get("message"), dict) else {}
        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        from_user = message.get("from") if isinstance(message.get("from"), dict) else {}

        update_id = str(payload.get("update_id") or "")
        chat_id = str(chat.get("id") or "")
        sender_id = str(from_user.get("id") or "").strip() or chat_id
        sender_display = str(from_user.get("username") or "").strip()
        if not sender_display:
            parts = [str(from_user.get("first_name") or "").strip(), str(from_user.get("last_name") or "").strip()]
            sender_display = " ".join(part for part in parts if part).strip()
        if not sender_display:
            sender_display = str(chat.get("title") or "").strip() or "telegram fixture"

        text = str(message.get("text") or "").strip()
        message_id_raw = str(message.get("message_id") or "").strip()
        dedupe_id = message_id_raw or update_id or "fixture"
        if not sender_id:
            return []

        return [
            {
                "message_id": f"fixture-tg-{chat_id or 'unknown'}-{dedupe_id}",
                "sender_id": sender_id,
                "sender_display": sender_display,
                "text": text,
                "attachments": [],
                "received_at": _now_iso(),
                "thread_hint": chat_id,
                "metadata": {
                    "plugin_id": "kitchen_sink_plugin",
                    "source": "telegram_kitchen_sink",
                    "update_id": update_id,
                },
            }
        ]

    async def send(self, payload):
        chat_id = str(payload.get("chat_id") or "").strip()
        text = str(payload.get("text") or "").strip()
        if not chat_id or not text:
            return {"ok": False, "error": "missing_required_fields: chat_id,text"}
        if not self._send_token:
            return {"ok": False, "error": "missing_send_token"}
        reply_to_message_id = str(payload.get("reply_to_message_id") or "").strip()
        return {
            "ok": True,
            "provider_message_id": f"fixture-send-{chat_id}-{reply_to_message_id or 'root'}",
        }


class KitchenSinkServerPlugin:
    def __init__(self, ctx):
        config = dict(ctx.config or {})
        secret_refs = dict(ctx.secret_refs or {})
        self._adapter = TelegramKitchenSinkAdapter(
            webhook_secret=str(secret_refs.get("telegram_webhook_secret") or ""),
            send_token=str(secret_refs.get("send_token") or ""),
        )
        self._custom_route = "kitchen-sink-events"
        self._enabled = False

    async def on_enable(self):
        self._enabled = True

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
