#!/usr/bin/env python3
"""Small Ultron-only gateway for the OpenAI Responses API."""

from __future__ import annotations

import hmac
import json
import os
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OPENAI_URL = "https://api.openai.com/v1/responses"
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
CLIENT_TOKEN = os.environ.get("ULTRON_CLIENT_TOKEN", "")
PORT = int(os.environ.get("PORT", "8080"))
MAX_BODY_BYTES = 64_000
MAX_MESSAGES = 20
MAX_TOTAL_CHARS = 40_000
RATE_LIMIT_PER_MINUTE = 30
REQUESTS: dict[str, deque[float]] = defaultdict(deque)

INSTRUCTIONS = (
    "You are Ultron, a concise personal AI assistant. Be helpful, accurate, calm, "
    "and clear. Never claim to control a device unless a connected tool confirms it."
)


def valid_token(header: str) -> bool:
    scheme, _, value = header.partition(" ")
    return bool(CLIENT_TOKEN) and scheme.lower() == "bearer" and hmac.compare_digest(value, CLIENT_TOKEN)


def rate_limited(client: str) -> bool:
    now = time.monotonic()
    window = REQUESTS[client]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= RATE_LIMIT_PER_MINUTE:
        return True
    window.append(now)
    return False


def validate_messages(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_MESSAGES:
        raise ValueError(f"messages must contain 1 to {MAX_MESSAGES} items")
    cleaned: list[dict[str, str]] = []
    total = 0
    for item in value:
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            raise ValueError("each message needs a user or assistant role")
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("message content must be text")
        total += len(content)
        if total > MAX_TOTAL_CHARS:
            raise ValueError("conversation is too large")
        cleaned.append({"role": item["role"], "content": content})
    return cleaned


def call_openai(messages: list[dict[str, str]]) -> str:
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    payload = json.dumps(
        {
            "model": MODEL,
            "instructions": INSTRUCTIONS,
            "input": messages,
            "max_output_tokens": 1200,
            "store": False,
        }
    ).encode()
    request = urllib.request.Request(
        OPENAI_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.load(response)
    if isinstance(result.get("output_text"), str) and result["output_text"].strip():
        return result["output_text"]
    parts = []
    for item in result.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                parts.append(content["text"])
    if not parts:
        raise RuntimeError("OpenAI returned no text")
    return "\n".join(parts)


class Handler(BaseHTTPRequestHandler):
    server_version = "UltronBackend/1.0"

    def send_json(self, status: int, value: dict[str, object]) -> None:
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(200, {"status": "ok", "service": "ultron-backend"})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/v1/chat":
            return self.send_json(404, {"error": "not found"})
        if not valid_token(self.headers.get("Authorization", "")):
            return self.send_json(401, {"error": "unauthorized"})
        client = self.client_address[0]
        if rate_limited(client):
            return self.send_json(429, {"error": "too many requests"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY_BYTES:
                return self.send_json(413, {"error": "request too large"})
            body = json.loads(self.rfile.read(length))
            messages = validate_messages(body.get("messages"))
            self.send_json(200, {"reply": call_openai(messages), "model": MODEL})
        except ValueError as error:
            self.send_json(400, {"error": str(error)})
        except urllib.error.HTTPError as error:
            print(f"OpenAI HTTP error: {error.code}")
            self.send_json(502, {"error": "AI service request failed"})
        except Exception as error:
            print(f"Backend error: {type(error).__name__}: {error}")
            self.send_json(500, {"error": "backend request failed"})

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


if __name__ == "__main__":
    if not CLIENT_TOKEN:
        raise SystemExit("ULTRON_CLIENT_TOKEN must be configured")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

