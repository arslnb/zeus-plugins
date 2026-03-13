from __future__ import annotations

import asyncio

from services import messaging_server_client


class KitchenSinkClientPlugin:
    def __init__(self, ctx):
        self.ctx = dict(ctx or {})
        self.config = dict(self.ctx.get("config") or {})

    def tools(self):
        return {
            "kitchen_lookup": {
                "description": "Return a stable fixture payload from the kitchen sink plugin.",
                "handler": self.kitchen_lookup,
            },
            "github_me": {
                "description": "Return the connected GitHub profile using the plugin's server-side OAuth session.",
                "handler": self.github_me,
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            "github_notifications": {
                "description": "Return unread GitHub notifications using the plugin's server-side OAuth session.",
                "handler": self.github_notifications,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 20,
                            "description": "Maximum number of notifications to return.",
                        }
                    },
                },
            }
        }

    def commands(self):
        return {"sync_now": {"description": "Execute the kitchen sink command."}}

    def services(self):
        return {"calendar_sync": {"description": "Execute the kitchen sink service."}}

    def cli(self):
        return {"status_cli": {"description": "Execute the kitchen sink CLI."}}

    def providers(self):
        return {"weather_provider": {"description": "Execute the kitchen sink provider."}}

    def gateway(self):
        return {"gateway_route": {"description": "Execute the kitchen sink gateway operation."}}

    def http(self):
        return {"http_route": {"description": "Execute the kitchen sink HTTP operation."}}

    async def kitchen_lookup(self, payload, context):
        return {
            "status": "ok",
            "kind": "tool",
            "payload_value": payload.get("value"),
            "hooked_by_plugin": bool(payload.get("hooked_by_plugin", False)),
            "runtime_name": context.get("runtime_name"),
            "plugin_configured": bool(self.config),
        }

    async def github_me(self, payload, context):
        del payload
        result = await asyncio.to_thread(
            messaging_server_client.invoke_plugin_action,
            plugin_id=str(context.get("plugin_id") or "kitchen_sink_plugin"),
            action="github_me",
            payload={},
        )
        out = dict(result or {})
        out.setdefault("status", "ok")
        out.setdefault("kind", "tool")
        return out

    async def github_notifications(self, payload, context):
        limit_value = payload.get("limit") if isinstance(payload, dict) else None
        try:
            limit = int(limit_value)
        except Exception:
            limit = 5
        limit = max(1, min(limit, 20))
        result = await asyncio.to_thread(
            messaging_server_client.invoke_plugin_action,
            plugin_id=str(context.get("plugin_id") or "kitchen_sink_plugin"),
            action="github_notifications",
            payload={"limit": limit},
        )
        out = dict(result or {})
        out.setdefault("status", "ok")
        out.setdefault("kind", "tool")
        return out

    async def call_command(self, name, payload, context):
        return {
            "status": "ok",
            "kind": "command",
            "name": name,
            "payload_value": payload.get("value"),
            "runtime_name": context.get("runtime_name"),
        }

    async def call_service(self, name, payload, context):
        return {
            "status": "ok",
            "kind": "service",
            "name": name,
            "payload_value": payload.get("value"),
            "runtime_name": context.get("runtime_name"),
        }

    async def call_cli(self, name, payload, context):
        return {
            "status": "ok",
            "kind": "cli",
            "name": name,
            "payload_value": payload.get("value"),
            "runtime_name": context.get("runtime_name"),
        }

    async def call_provider(self, name, payload, context):
        return {
            "status": "ok",
            "kind": "provider",
            "name": name,
            "payload_value": payload.get("value"),
            "runtime_name": context.get("runtime_name"),
        }

    async def call_gateway(self, name, payload, context):
        return {
            "status": "ok",
            "kind": "gateway",
            "name": name,
            "payload_value": payload.get("value"),
            "runtime_name": context.get("runtime_name"),
        }

    async def call_http(self, name, payload, context):
        return {
            "status": "ok",
            "kind": "http",
            "name": name,
            "payload_value": payload.get("value"),
            "runtime_name": context.get("runtime_name"),
        }

    def before_model_resolve(self, payload, context):
        next_payload = dict(payload or {})
        next_payload["plugin_before_model_resolve"] = True
        return {"payload": next_payload}

    def before_prompt_build(self, payload, context):
        next_payload = dict(payload or {})
        system_prompt = str(next_payload.get("system_prompt") or "")
        next_payload["system_prompt"] = system_prompt + "\n# kitchen-sink-before-prompt-build"
        return {"payload": next_payload}

    def before_tool_call(self, payload, context):
        next_payload = dict(payload or {})
        tool_input = dict(next_payload.get("tool_input") or {})
        tool_input["hooked_by_plugin"] = True
        next_payload["tool_input"] = tool_input
        return {"payload": next_payload}

    def after_tool_call(self, payload, context):
        next_payload = dict(payload or {})
        result_json = dict(next_payload.get("result_json") or {})
        result_json["after_hook_applied"] = True
        next_payload["result_json"] = result_json
        return {"payload": next_payload}


def check_environment(context=None, ctx=None):
    del context, ctx
    return True, "Environment ready."


def register(context):
    return KitchenSinkClientPlugin(context)
