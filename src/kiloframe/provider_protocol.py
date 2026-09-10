"""Provider wire adapters. No routing decisions or assistant persona live here."""
from __future__ import annotations

import json
from typing import Any


def consolidated_system_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Give every cloud endpoint one authoritative, ordered system instruction.

    Anthropic already requires this shape. Several nominally OpenAI-compatible model
    gateways accept multiple system messages but apply only one of them, which made
    Kilo's identity and operating rules vary by provider. Tool/user/assistant ordering
    is preserved; only system content is consolidated at the front.
    """
    system = [str(message.get("content") or "") for message in messages if message.get("role") == "system"]
    conversation = [dict(message) for message in messages if message.get("role") != "system"]
    if not system:
        return conversation
    return [{"role": "system", "content": "\n\n".join(system)}, *conversation]


def anthropic_payload(payload: dict[str, Any]) -> dict[str, Any]:
    system = []
    messages = []
    for message in consolidated_system_messages(payload["messages"]):
        role = message["role"]
        if role == "system":
            system.append(str(message.get("content") or ""))
            continue
        blocks = []
        if role == "tool":
            role = "user"
            content = message.get("content") or ""
            try:
                result = json.loads(content)
            except (ValueError, TypeError):
                result = {}
            failed = isinstance(result, dict) and (bool(result.get("error")) or result.get("isError") is True
                or result.get("ok") is False or ("exit_code" in result and result["exit_code"] != 0))
            blocks.append({"type": "tool_result", "tool_use_id": message["tool_call_id"],
                           "content": content, "is_error": failed})
        else:
            if message.get("content"):
                blocks.append({"type": "text", "text": str(message["content"])})
            for call in message.get("tool_calls") or []:
                function = call["function"]
                args = function.get("arguments") or "{}"
                blocks.append({"type": "tool_use", "id": call["id"], "name": function["name"],
                               "input": json.loads(args) if isinstance(args, str) else args})
        if blocks:
            if messages and messages[-1]["role"] == role:
                messages[-1]["content"].extend(blocks)
            else:
                messages.append({"role": role, "content": blocks})
    result = {"model": payload["model"], "max_tokens": payload["max_tokens"],
              "stream": True, "system": "\n\n".join(system), "messages": messages}
    if payload.get("tools"):
        result["tools"] = [{"name": t["function"]["name"],
                            "description": t["function"].get("description", ""),
                            "input_schema": t["function"]["parameters"]} for t in payload["tools"]]
    return result


def anthropic_event(event: dict[str, Any]) -> dict[str, Any] | None:
    kind = event.get("type")
    index = event.get("index", 0)
    if kind == "content_block_start":
        block = event.get("content_block") or {}
        if block.get("type") == "tool_use":
            return {"delta": {"tool_calls": [{"index": index, "id": block["id"],
                "function": {"name": block["name"], "arguments": ""}}]}}
        if block.get("type") == "text" and block.get("text"):
            return {"delta": {"content": block["text"]}}
    if kind == "content_block_delta":
        delta = event.get("delta") or {}
        if delta.get("type") == "text_delta":
            return {"delta": {"content": delta.get("text", "")}}
        if delta.get("type") == "input_json_delta":
            return {"delta": {"tool_calls": [{"index": index,
                "function": {"arguments": delta.get("partial_json", "")}}]}}
    if kind == "message_start":
        usage = (event.get("message") or {}).get("usage") or {}
        return {"usage": {"prompt_tokens": usage.get("input_tokens", 0),
                          "completion_tokens": usage.get("output_tokens", 0)}}
    if kind == "message_delta":
        reason = (event.get("delta") or {}).get("stop_reason")
        return {"finish_reason": "length" if reason == "max_tokens" else "tool_calls" if reason == "tool_use" else reason,
                "usage": {"completion_tokens": (event.get("usage") or {}).get("output_tokens", 0)}}
    return None


def text_tool_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Endpoints rejecting native tools also reject native tool history on follow-up."""
    converted = []
    for original in messages:
        message = dict(original)
        calls = message.pop("tool_calls", None)
        if calls:
            message["content"] = (message.get("content") or "") + "\n" + "\n".join(
                "<tool_call>" + json.dumps(c["function"]) + "</tool_call>" for c in calls)
        if message["role"] == "tool":
            message["role"] = "user"
            message["content"] = "Tool result for " + message.get("name", "tool") + ":\n" + str(message.get("content") or "")
            message.pop("name", None)
            message.pop("tool_call_id", None)
        converted.append(message)
    return converted
