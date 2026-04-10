"""HTTP API channel — exposes a REST interface for programmatic access.

Endpoints (served on ``host:port``):
- ``POST /api/chat``          synchronous request → wait for final reply
- ``POST /api/chat/stream``   SSE stream of intermediate + final updates
- ``GET  /api/status``        gateway health check
- ``GET  /api/history``       retrieve recent messages for a session

SSE event ``kind`` values emitted by ``/api/chat/stream``:

  ``thinking``     agent is reasoning
  ``tool_start``   a tool execution has begun  (includes ``tool_name``)
  ``tool_end``     a tool execution has finished
  ``status``       general status update
  ``token``        incremental text token (for Chainlit ``stream_token``)
  ``error``        something went wrong
  ``final``        complete assistant reply

Every inbound request is mapped to an :class:`InboundMessage` that flows
through the standard gateway bridge, so sessions, tools, memory and all
other harness features work identically to IM channels.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from openharness.channels.bus.events import OutboundMessage
from openharness.channels.bus.queue import MessageBus
from openharness.channels.impl.base import BaseChannel
from openharness.config.schema import HttpApiConfig

logger = logging.getLogger(__name__)

try:
    from aiohttp import web

    AIOHTTP_AVAILABLE = True
except ImportError:
    web = None  # type: ignore[assignment]
    AIOHTTP_AVAILABLE = False

def _classify_event(msg: OutboundMessage) -> dict[str, Any]:
    """Turn an OutboundMessage into a structured SSE payload.

    The gateway runtime annotates every ``OutboundMessage.metadata`` with
    ``_event_kind`` (one of ``thinking``, ``status``, ``tool_start``,
    ``tool_end``, ``error``).  We read that directly instead of guessing
    from the message text.
    """
    meta = msg.metadata or {}
    is_progress = meta.get("_progress", False)

    if not is_progress:
        return {"kind": "final", "content": msg.content}

    event_kind = meta.get("_event_kind", "")

    if meta.get("_tool_hint"):
        return {
            "kind": "tool_start",
            "content": msg.content,
            "tool_name": meta.get("_tool_name", ""),
        }

    if event_kind in ("thinking", "status", "tool_end", "error"):
        return {"kind": event_kind, "content": msg.content}

    return {"kind": "status", "content": msg.content}


class _PendingRequest:
    """Tracks one in-flight HTTP request waiting for the assistant reply."""

    __slots__ = ("future", "queue", "streaming")

    def __init__(self, *, streaming: bool = False) -> None:
        self.streaming = streaming
        self.future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
        self.queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

def _cors_headers(config: HttpApiConfig) -> dict[str, str]:
    origin = config.cors_allow_origin or "*"
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Chat-Id",
        "Access-Control-Expose-Headers": "X-Chat-Id",
    }


@web.middleware
async def _cors_middleware(request: Any, handler: Any) -> Any:
    if request.method == "OPTIONS":
        config: HttpApiConfig = request.app["_http_api_config"]
        return web.Response(headers=_cors_headers(config))
    resp = await handler(request)
    config = request.app["_http_api_config"]
    resp.headers.update(_cors_headers(config))
    return resp


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------

class HttpApiChannel(BaseChannel):
    """HTTP REST/SSE channel backed by aiohttp.

    Designed for easy integration with Chainlit and other web front-ends.
    """

    name = "http_api"

    def __init__(self, config: HttpApiConfig, bus: MessageBus) -> None:
        super().__init__(config, bus)
        self.config: HttpApiConfig = config
        self._app: Any = None
        self._runner: Any = None
        self._pending: dict[str, _PendingRequest] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if not AIOHTTP_AVAILABLE:
            logger.error("aiohttp is not installed.  Run: pip install aiohttp")
            return

        self._running = True
        self._app = web.Application(middlewares=[_cors_middleware])
        self._app["_http_api_config"] = self.config

        self._app.router.add_post("/api/chat", self._handle_chat)
        self._app.router.add_post("/api/chat/stream", self._handle_chat_stream)
        self._app.router.add_get("/api/status", self._handle_status)
        self._app.router.add_get("/api/history", self._handle_history)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(
            self._runner,
            self.config.host,
            self.config.port,
        )
        await site.start()
        logger.info(
            "HTTP API channel listening on %s:%s", self.config.host, self.config.port
        )

    async def stop(self) -> None:
        self._running = False
        for req in self._pending.values():
            if not req.future.done():
                req.future.cancel()
            await req.queue.put(None)
        self._pending.clear()
        if self._runner:
            await self._runner.cleanup()
            self._runner = None

    # ------------------------------------------------------------------
    # Outbound dispatch (called by ChannelManager)
    # ------------------------------------------------------------------

    async def send(self, msg: OutboundMessage) -> None:
        pending = self._pending.get(msg.chat_id)
        if pending is None:
            return

        event = _classify_event(msg)

        if pending.streaming:
            await pending.queue.put(event)
            if event["kind"] == "final":
                await pending.queue.put(None)
        else:
            if event["kind"] == "final" and not pending.future.done():
                pending.future.set_result(msg.content)

    # ------------------------------------------------------------------
    # HTTP handlers
    # ------------------------------------------------------------------

    async def _parse_body(self, request: Any) -> dict[str, Any]:
        try:
            return await request.json()
        except Exception:
            return {}

    async def _handle_chat(self, request: Any) -> Any:
        """Synchronous chat: wait for the full reply and return it."""
        body = await self._parse_body(request)
        message = (body.get("message") or "").strip()
        if not message:
            return web.json_response({"error": "message is required"}, status=400)

        sender_id = body.get("sender_id", "http_user")
        chat_id = body.get("chat_id") or str(uuid.uuid4())
        timeout = float(body.get("timeout", self.config.timeout))

        pending = _PendingRequest(streaming=False)
        self._pending[chat_id] = pending

        try:
            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=message,
                metadata={"platform": "http_api"},
            )
            reply = await asyncio.wait_for(pending.future, timeout=timeout)
            return web.json_response({
                "reply": reply,
                "chat_id": chat_id,
                "session_key": f"http_api:{chat_id}",
            })
        except asyncio.TimeoutError:
            return web.json_response(
                {"error": "timeout waiting for assistant reply"}, status=504
            )
        except Exception as exc:
            logger.exception("HTTP API chat error")
            return web.json_response({"error": str(exc)}, status=500)
        finally:
            self._pending.pop(chat_id, None)

    async def _handle_chat_stream(self, request: Any) -> Any:
        """SSE streaming: send fine-grained events as they arrive.

        Each SSE ``data`` line is a JSON object with at least ``kind`` and
        ``content``.  Possible *kind* values are documented in the module
        docstring and align with Chainlit Step types.
        """
        body = await self._parse_body(request)
        message = (body.get("message") or "").strip()
        if not message:
            return web.json_response({"error": "message is required"}, status=400)

        sender_id = body.get("sender_id", "http_user")
        chat_id = body.get("chat_id") or str(uuid.uuid4())

        pending = _PendingRequest(streaming=True)
        self._pending[chat_id] = pending

        cors = _cors_headers(self.config)
        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Chat-Id": chat_id,
                **cors,
            },
        )
        await response.prepare(request)

        try:
            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=message,
                metadata={"platform": "http_api"},
            )
            while True:
                item = await pending.queue.get()
                if item is None:
                    break
                sse_data = json.dumps(item, ensure_ascii=False)
                await response.write(f"data: {sse_data}\n\n".encode())
        except Exception as exc:
            logger.exception("HTTP API stream error")
            err = json.dumps({"kind": "error", "content": str(exc)}, ensure_ascii=False)
            await response.write(f"data: {err}\n\n".encode())
        finally:
            self._pending.pop(chat_id, None)
            await response.write_eof()

        return response

    async def _handle_status(self, request: Any) -> Any:
        return web.json_response({
            "running": self._running,
            "pending_requests": len(self._pending),
        })

    async def _handle_history(self, request: Any) -> Any:
        """Return recent conversation messages for a given chat_id / session.

        Query params:
        - ``chat_id`` (required)
        - ``limit``   (optional, default 50)
        """
        chat_id = request.query.get("chat_id", "").strip()
        if not chat_id:
            return web.json_response({"error": "chat_id is required"}, status=400)
        limit = int(request.query.get("limit", "50"))
        session_key = f"http_api:{chat_id}"

        try:
            from ohmo.session_storage import OhmoSessionBackend
            from ohmo.workspace import initialize_workspace
            import os

            workspace = os.environ.get("OHMO_WORKSPACE")
            if workspace:
                backend = OhmoSessionBackend(workspace)
                snapshot = backend.load_latest_for_session_key(session_key)
                if snapshot:
                    messages = snapshot.get("messages") or []
                    return web.json_response({
                        "chat_id": chat_id,
                        "session_key": session_key,
                        "messages": messages[-limit:],
                    })
            return web.json_response({
                "chat_id": chat_id,
                "session_key": session_key,
                "messages": [],
            })
        except Exception:
            logger.exception("HTTP API history fetch error")
            return web.json_response({
                "chat_id": chat_id,
                "session_key": session_key,
                "messages": [],
            })
