import argparse
import json
import os
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


API_BASE = "https://api.sakana.ai/v1"
SERVER_NAME = "sakana-fugu-adapter"


def _json_response(handler, status, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler):
    length = int(handler.headers.get("content-length", "0"))
    if length == 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def _text_from_content(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif item.get("type") == "tool_result":
                tool_content = item.get("content", "")
                parts.append(tool_content if isinstance(tool_content, str) else json.dumps(tool_content))
        return "\n".join(part for part in parts if part)
    return str(content)


def _required_tool_fields(payload):
    required = {}
    for tool in payload.get("tools", []) or []:
        name = tool.get("name")
        fields = tool.get("input_schema", {}).get("required", [])
        if name and isinstance(fields, list):
            required[name] = set(fields)
    return required


def _missing_required_tool_input(tool_name, tool_input, required_by_tool):
    required = required_by_tool.get(tool_name, set())
    if not required:
        return False
    if not isinstance(tool_input, dict):
        return True
    return any(field not in tool_input or tool_input.get(field) in (None, "") for field in required)


def _is_missing_required_tool_error(content):
    text = _text_from_content(content)
    return "InputValidationError" in text and "required parameter" in text and "is missing" in text


def _anthropic_to_openai_messages(payload):
    messages = []
    required_by_tool = _required_tool_fields(payload)
    skipped_tool_use_ids = set()
    system = payload.get("system")
    if system:
        messages.append({"role": "system", "content": _text_from_content(system)})

    pending_tool_results = []
    for msg in payload.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            assistant_text = []
            tool_calls = []
            user_text = []
            for item in content:
                if item.get("type") == "text":
                    if role == "assistant":
                        assistant_text.append(item.get("text", ""))
                    else:
                        user_text.append(item.get("text", ""))
                elif item.get("type") == "tool_use":
                    tool_id = item.get("id")
                    tool_name = item.get("name")
                    tool_input = item.get("input", {})
                    if _missing_required_tool_input(tool_name, tool_input, required_by_tool):
                        if tool_id:
                            skipped_tool_use_ids.add(tool_id)
                        continue
                    tool_calls.append({
                        "id": tool_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(tool_input),
                        },
                    })
                elif item.get("type") == "tool_result":
                    tool_use_id = item.get("tool_use_id")
                    if tool_use_id in skipped_tool_use_ids or _is_missing_required_tool_error(item.get("content", "")):
                        continue
                    pending_tool_results.append({
                        "role": "tool",
                        "tool_call_id": tool_use_id,
                        "content": _text_from_content(item.get("content", "")),
                    })

            if role == "assistant":
                assistant_content = "\n".join(assistant_text) or None
                if assistant_content or tool_calls:
                    openai_msg = {"role": "assistant", "content": assistant_content}
                    if tool_calls:
                        openai_msg["tool_calls"] = tool_calls
                    messages.append(openai_msg)
            elif user_text:
                messages.append({"role": "user", "content": "\n".join(user_text)})

            if pending_tool_results:
                messages.extend(pending_tool_results)
                pending_tool_results = []
        else:
            messages.append({"role": role, "content": _text_from_content(content)})
    return messages


def _tools_to_openai(payload):
    tools = []
    for tool in payload.get("tools", []) or []:
        tools.append({
            "type": "function",
            "function": {
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return tools


def _call_sakana(payload):
    api_key = os.environ.get("SAKANA_API_KEY")
    if not api_key:
        raise RuntimeError("SAKANA_API_KEY is not set")

    model = payload.get("model", "fugu")
    body = {
        "model": model,
        "messages": _anthropic_to_openai_messages(payload),
        "stream": False,
    }
    if payload.get("max_tokens"):
        body["max_tokens"] = payload["max_tokens"]
    max_tokens_cap = os.environ.get("FUGU_MAX_TOKENS")
    if max_tokens_cap:
        try:
            body["max_tokens"] = min(int(body.get("max_tokens", int(max_tokens_cap))), int(max_tokens_cap))
        except ValueError:
            pass
    if payload.get("temperature") is not None:
        body["temperature"] = payload["temperature"]
    tools = _tools_to_openai(payload)
    if tools:
        body["tools"] = tools

    req = urllib.request.Request(
        f"{API_BASE}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(detail) from exc


def _openai_to_anthropic(openai_payload, model):
    choice = openai_payload.get("choices", [{}])[0]
    msg = choice.get("message", {})
    content = []
    text = msg.get("content")
    if text:
        content.append({"type": "text", "text": text})

    for call in msg.get("tool_calls", []) or []:
        function = call.get("function", {})
        raw_args = function.get("arguments") or "{}"
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            args = {"_raw": raw_args}
        content.append({
            "type": "tool_use",
            "id": call.get("id"),
            "name": function.get("name"),
            "input": args,
        })

    stop_reason = "tool_use" if msg.get("tool_calls") else "end_turn"
    usage = openai_payload.get("usage", {})
    return {
        "id": openai_payload.get("id", f"msg_{int(time.time())}"),
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content or [{"type": "text", "text": ""}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


def _estimate_tokens(payload):
    text = []
    if payload.get("system"):
        text.append(_text_from_content(payload.get("system")))
    for msg in payload.get("messages", []) or []:
        text.append(_text_from_content(msg.get("content", "")))
    for tool in payload.get("tools", []) or []:
        text.append(tool.get("name", ""))
        text.append(tool.get("description", ""))
        text.append(json.dumps(tool.get("input_schema", {})))
    chars = len("\n".join(text))
    return max(1, chars // 4)


def _sse(handler, event, data):
    handler.wfile.write(f"event: {event}\n".encode("utf-8"))
    handler.wfile.write(f"data: {json.dumps(data)}\n\n".encode("utf-8"))
    handler.wfile.flush()


def _stream_anthropic(handler, message):
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "close")
    handler.end_headers()

    shell = dict(message)
    content = shell.pop("content", [])
    _sse(handler, "message_start", {"type": "message_start", "message": {**shell, "content": []}})
    for index, block in enumerate(content):
        _sse(handler, "content_block_start", {"type": "content_block_start", "index": index, "content_block": block})
        if block.get("type") == "text":
            _sse(handler, "content_block_delta", {"type": "content_block_delta", "index": index, "delta": {"type": "text_delta", "text": block.get("text", "")}})
        _sse(handler, "content_block_stop", {"type": "content_block_stop", "index": index})
    _sse(handler, "message_delta", {"type": "message_delta", "delta": {"stop_reason": message.get("stop_reason"), "stop_sequence": None}, "usage": {"output_tokens": message.get("usage", {}).get("output_tokens", 0)}})
    _sse(handler, "message_stop", {"type": "message_stop"})
    handler.close_connection = True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/health", "/"):
            _json_response(self, 200, {"ok": True, "server": SERVER_NAME})
            return
        if path == "/v1/models":
            _json_response(self, 200, {
                "object": "list",
                "data": [
                    {"id": "fugu", "object": "model", "display_name": "Sakana Fugu"},
                    {"id": "fugu-ultra", "object": "model", "display_name": "Sakana Fugu Ultra"},
                    {"id": "fugu-ultra-20260615", "object": "model", "display_name": "Sakana Fugu Ultra 20260615"},
                ],
            })
            return
        _json_response(self, 404, {"error": {"message": "not found"}})

    def do_POST(self):
        path = urlparse(self.path).path
        if path in ("/v1/messages/count_tokens", "/messages/count_tokens"):
            try:
                payload = _read_json(self)
                _json_response(self, 200, {"input_tokens": _estimate_tokens(payload)})
            except Exception as exc:
                _json_response(self, 400, {"error": {"type": "invalid_request_error", "message": str(exc)}})
            return

        if path not in ("/v1/messages", "/messages"):
            _json_response(self, 404, {"error": {"message": "not found"}})
            return
        try:
            payload = _read_json(self)
            response = _openai_to_anthropic(_call_sakana(payload), payload.get("model", "fugu"))
            if payload.get("stream"):
                _stream_anthropic(self, response)
            else:
                _json_response(self, 200, response)
        except Exception as exc:
            _json_response(self, 400, {"error": {"type": "invalid_request_error", "message": str(exc)}})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4010)
    args = parser.parse_args()
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
