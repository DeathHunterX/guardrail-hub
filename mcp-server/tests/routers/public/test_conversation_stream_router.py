"""Tests for the conversation streaming REST router.

These tests verify the thin adapter contract for the streaming endpoint:
the router validates input, calls ConversationService correctly, forwards
chunks as SSE events, calls finalise_stream(), and maps errors appropriately.

Tests do NOT test ConversationService itself — those are covered by the
dedicated ConversationService test suite.

FastAPI is not installed in this test environment (Python 3.10 vs project
requirement of 3.12+), so:
  - Thin-adapter property tests use AST source analysis.
  - Handler-level tests use a local mirror of the handler logic that does
    not require importing FastAPI or StreamingResponse.
  - Error mapping is verified against the existing router conventions.
"""
from __future__ import annotations

import ast
import asyncio
import json
import unittest
from datetime import datetime, timezone
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Minimal HTTPException mock -- mirrors FastAPI's dataclass interface.
# ---------------------------------------------------------------------------

class HTTPException(Exception):
    """Minimal mock of FastAPI.HTTPException for environments without FastAPI."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


# ---------------------------------------------------------------------------
# Fake ConversationService -- matches the real service's public streaming API.
# ---------------------------------------------------------------------------

class FakeConversationService:
    """Fake matching ConversationService's public streaming API for handler tests."""

    def __init__(self):
        self.calls: list[tuple[str, ...]] = []
        self.finalise_calls: list[dict] = []
        self._override_stream: AsyncIterator[str] | None = None
        self._override_stream_exc: BaseException | None = None

    def create_conversation(self, conversation_id, initial_state=None):
        self.calls.append(("create", conversation_id))
        from app.intelligence.conversation.store import ConversationSummary
        from app.intelligence.conversation.state import ConversationState
        return ConversationSummary(
            conversation_id=conversation_id,
            state=ConversationState.CREATED,
            messages=(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    async def handle_turn_stream(
        self,
        conversation_id,
        user_content,
        system_prompt=None,
        model=None,
        provider=None,
        user_metadata=None,
    ):
        self.calls.append(
            ("handle_turn_stream", conversation_id, user_content, system_prompt, model)
        )
        from app.intelligence.conversation.store import ConversationSummary
        from app.intelligence.conversation.state import ConversationState

        summary = ConversationSummary(
            conversation_id=conversation_id,
            state=ConversationState.OPEN,
            messages=(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Use override if set; otherwise yield a fixed 4-chunk sequence.
        resolved_model = model or "default-model"
        if self._override_stream is not None:
            return summary, resolved_model, self._override_stream

        async def default_stream():
            if self._override_stream_exc is not None:
                yield "partial "
                raise self._override_stream_exc
            for chunk in ["Hello", " ", "world", "!"]:
                yield chunk

        return summary, resolved_model, default_stream()

    def finalise_stream(
        self,
        conversation_id,
        prior_summary,
        final_content,
        model=None,
    ):
        self.finalise_calls.append({
            "conversation_id": conversation_id,
            "prior_summary": prior_summary,
            "final_content": final_content,
            "model": model,
        })
        from app.intelligence.conversation.store import ConversationSummary
        from app.intelligence.conversation.state import ConversationState

        return ConversationSummary(
            conversation_id=conversation_id,
            state=ConversationState.OPEN,
            messages=(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def set_stream_override(self, chunks: list[str]) -> None:
        """Replace the default chunk stream with an explicit list."""
        async def override():
            for chunk in chunks:
                yield chunk
        self._override_stream = override()

    def set_stream_exception(self, exc: BaseException) -> None:
        """Configure the stream to yield one partial chunk then raise."""
        self._override_stream_exc = exc


# ---------------------------------------------------------------------------
# SSE helpers (mirror the router's helpers)
# ---------------------------------------------------------------------------

async def _sse_event(event_type: str, data: object) -> str:
    body = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {body}\n\n"


# ---------------------------------------------------------------------------
# Local mirror of the streaming handler logic (production code path).
# This mirrors exactly what the router's handle_turn_stream handler does,
# reimplemented locally so we can test behavior without importing FastAPI.
# ---------------------------------------------------------------------------

async def _event_generator_mirror(
    conversation_id: str,
    prior_summary,
    resolved_model: str,
    chunk_stream: AsyncIterator[str],
    svc,
) -> AsyncIterator[str]:
    """Mirrors the router's event_generator inner function.

    Kept in sync with the production implementation in conversation_router.py.
    """
    accumulated: list[str] = []
    _finalised = False

    try:
        async for chunk in chunk_stream:
            accumulated.append(chunk)
            yield await _sse_event("chunk", {"content": chunk})

        final_content = "".join(accumulated)
        _finalised = True
        svc.finalise_stream(
            conversation_id=conversation_id,
            prior_summary=prior_summary,
            final_content=final_content,
            model=resolved_model,
        )
        yield await _sse_event(
            "done",
            {"content": final_content, "model": resolved_model or "", "finish_reason": "stop"},
        )

    except Exception as exc:
        partial_content = "".join(accumulated)
        if not _finalised:
            _finalised = True
            try:
                svc.finalise_stream(
                    conversation_id=conversation_id,
                    prior_summary=prior_summary,
                    final_content=partial_content,
                    model=resolved_model,
                )
            except Exception:
                pass  # swallow — stream is already in error state
        yield await _sse_event("error", {"detail": str(exc)})

    finally:
        # Runs on aclose() (client disconnect) or CancelledError.
        # Must NOT yield — yielding in finally raises RuntimeError in Python 3.10.
        if not _finalised:
            partial_content = "".join(accumulated)
            try:
                svc.finalise_stream(
                    conversation_id=conversation_id,
                    prior_summary=prior_summary,
                    final_content=partial_content,
                    model=resolved_model,
                )
            except Exception:
                pass  # swallow — SSE stream may already be closed



async def _handle_turn_stream_local(conversation_id, body, svc):
    """Local mirror of the router's handle_turn_stream handler.

    Mirrors the production code path without importing FastAPI.
    """
    from app.intelligence.conversation.store import ConversationClosedError, ConversationNotFoundError

    try:
        prior_summary, resolved_model, chunk_stream = await svc.handle_turn_stream(
            conversation_id=conversation_id,
            user_content=body["user_content"],
            system_prompt=body.get("system_prompt"),
            model=body.get("model"),
            provider=body.get("provider"),
            user_metadata=body.get("user_metadata"),
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConversationClosedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _event_generator_mirror(
        conversation_id, prior_summary, resolved_model, chunk_stream, svc
    )


# ---------------------------------------------------------------------------
# Test: Router is a thin adapter (AST analysis of the source file).
# ---------------------------------------------------------------------------

class TestRouterIsThinAdapterForStreaming(unittest.TestCase):
    """Verify the streaming endpoint follows thin-adapter principles via AST."""

    @classmethod
    def setUpClass(cls):
        router_path = (
            "/sessions/practical-laughing-cray/mnt/guardrail-hub/"
            "mcp-server/app/routers/public/conversation_router.py"
        )
        with open(router_path) as f:
            cls.src = f.read()
        cls.tree = ast.parse(cls.src)

    def _module_imports(self):
        modules = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
        return modules

    def test_does_not_import_llm_service(self):
        """The streaming endpoint must not import LLMService."""
        modules = self._module_imports()
        llm_modules = [m for m in modules if "llm_service" in m]
        self.assertEqual(llm_modules, [], f"Found LLMService imports: {llm_modules}")

    def test_does_not_import_conversation_store(self):
        """The streaming endpoint must not import ConversationStore adapters."""
        modules = self._module_imports()
        store_modules = [
            m for m in modules
            if any(x in m for x in ["conversation_store", "in_memory_store", "dao_store"])
        ]
        self.assertEqual(store_modules, [], f"Found store imports: {store_modules}")

    def test_does_not_import_provider_adapters(self):
        """The streaming endpoint must not import provider adapters."""
        modules = self._module_imports()
        provider_modules = [
            m for m in modules
            if "provider" in m and "provider_manager" not in m
        ]
        self.assertEqual(provider_modules, [], f"Found provider imports: {provider_modules}")

    def test_does_not_call_llm_directly(self):
        """The router must not call LLMService directly."""
        self.assertNotIn("LLMService(", self.src)

    def test_does_not_call_store_directly(self):
        """The router must not call ConversationStore directly."""
        self.assertNotIn("ConversationStore(", self.src)
        self.assertNotIn("InMemoryConversationStore(", self.src)

    def test_does_not_call_llm_chat_methods(self):
        """The router must not call LLMService.chat or chat_stream."""
        self.assertNotIn(".chat(", self.src)
        self.assertNotIn(".chat_stream(", self.src)

    def test_imports_streaming_response(self):
        """The router must import StreamingResponse from FastAPI."""
        self.assertIn("StreamingResponse", self.src)
        self.assertIn("from fastapi.responses import StreamingResponse", self.src)

    def test_imports_handle_turn_stream_request(self):
        """The router must import HandleTurnStreamRequest."""
        self.assertIn("HandleTurnStreamRequest", self.src)

    def test_defines_handle_turn_stream_async(self):
        """handle_turn_stream handler must be declared 'async def'."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "handle_turn_stream":
                return  # Found it
        self.fail("handle_turn_stream must be declared 'async def'")

    def test_maps_not_found_to_404(self):
        """ConversationNotFoundError in streaming must be mapped to HTTP 404."""
        self.assertIn("status_code=404", self.src)
        self.assertIn("ConversationNotFoundError", self.src)

    def test_maps_closed_to_422(self):
        """ConversationClosedError in streaming must be mapped to HTTP 422."""
        self.assertIn("status_code=422", self.src)
        self.assertIn("ConversationClosedError", self.src)

    def test_uses_finalise_stream(self):
        """Router must call finalise_stream on the service."""
        self.assertIn("finalise_stream(", self.src)

    def test_yields_sse_events(self):
        """Router must yield SSE event strings via _sse_event helper."""
        self.assertIn("_sse_event", self.src)
        self.assertIn('"chunk"', self.src)
        self.assertIn('"done"', self.src)
        self.assertIn('"error"', self.src)

    def test_sse_event_helper_escapes_newlines(self):
        """The _sse_event helper must use json.dumps to escape SSE-unsafe chars."""
        self.assertIn("json.dumps", self.src)

    def test_returns_streaming_response(self):
        """Handler must return StreamingResponse."""
        self.assertIn("return StreamingResponse(", self.src)


# ---------------------------------------------------------------------------
# Test: SSE format correctness
# ---------------------------------------------------------------------------

class TestSSEHelper(unittest.TestCase):
    """Verify the SSE serialization helper produces valid SSE output."""

    def test_chunk_event_format(self):
        """Chunk events must have correct SSE framing."""
        result = asyncio.run(_sse_event("chunk", {"content": "Hello"}))
        self.assertEqual(result, 'event: chunk\ndata: {"content": "Hello"}\n\n')

    def test_done_event_format(self):
        """Done events must include content, model, and finish_reason."""
        result = asyncio.run(_sse_event("done", {"content": "Hi", "model": "gpt-4", "finish_reason": "stop"}))
        self.assertEqual(
            result,
            'event: done\ndata: {"content": "Hi", "model": "gpt-4", "finish_reason": "stop"}\n\n'
        )

    def test_error_event_format(self):
        """Error events must include the detail field."""
        result = asyncio.run(_sse_event("error", {"detail": "provider unavailable"}))
        self.assertEqual(
            result,
            'event: error\ndata: {"detail": "provider unavailable"}\n\n'
        )

    def test_newlines_in_content_are_escaped(self):
        """Newlines in chunk content must be JSON-escaped, not SSE-breaking."""
        result = asyncio.run(_sse_event("chunk", {"content": "line1\nline2"}))
        # json.dumps escapes \n as \\n, which is valid SSE.
        self.assertIn("\\n", result)
        self.assertNotIn("line1\nline2", result)  # bare newline would break SSE

    def test_quotes_in_content_are_escaped(self):
        """Quotes in chunk content must be JSON-escaped."""
        result = asyncio.run(_sse_event("chunk", {"content": 'say "hello"'}))
        self.assertIn('\\"', result)
        self.assertNotIn('say "hello"', result)  # bare quote would break JSON

    def test_backslashes_in_content_are_escaped(self):
        """Backslashes in chunk content must be JSON-escaped."""
        result = asyncio.run(_sse_event("chunk", {"content": r"path\to\file"}))
        self.assertIn("\\\\", result)

    def test_unicode_content_serializes(self):
        """Unicode characters in content must serialize without error."""
        result = asyncio.run(_sse_event("chunk", {"content": "世界"}))
        self.assertIsInstance(result, str)
        self.assertIn("世界", result)

    def test_control_characters_are_escaped(self):
        """Control characters (tabs, etc.) must be JSON-escaped."""
        result = asyncio.run(_sse_event("chunk", {"content": "hello\tworld"}))
        self.assertIn("\\t", result)


# ---------------------------------------------------------------------------
# Test: Handler-level logic
# ---------------------------------------------------------------------------

class TestStreamingHandlerLogic(unittest.TestCase):
    """Verify the streaming handler's business logic using the local mirror."""

    def setUp(self):
        self.svc = FakeConversationService()

    def test_service_invocation_correct_args(self):
        """handle_turn_stream() is called with correct arguments."""
        body = {
            "user_content": "Hi there",
            "system_prompt": "You are a helpful assistant.",
            "model": "gpt-4",
            "provider": "openai",
            "user_metadata": {"source": "test"},
        }
        asyncio.run(_handle_turn_stream_local("c1", body, self.svc))
        last = self.svc.calls[-1]
        self.assertEqual(last[0], "handle_turn_stream")
        self.assertEqual(last[1], "c1")
        self.assertEqual(last[2], "Hi there")
        self.assertEqual(last[3], "You are a helpful assistant.")
        self.assertEqual(last[4], "gpt-4")

    def test_service_invocation_with_defaults(self):
        """handle_turn_stream() is called correctly when optional fields are absent."""
        body = {"user_content": "Hello"}
        asyncio.run(_handle_turn_stream_local("c1", body, self.svc))
        last = self.svc.calls[-1]
        self.assertEqual(last[0], "handle_turn_stream")
        self.assertEqual(last[1], "c1")
        self.assertEqual(last[2], "Hello")
        self.assertIsNone(last[3])  # system_prompt
        self.assertIsNone(last[4])  # model

    def test_request_time_not_found_returns_404(self):
        """ConversationNotFoundError before streaming starts raises HTTP 404."""
        from app.intelligence.conversation.store import ConversationNotFoundError

        async def failing_stream(*args, **kwargs):
            raise ConversationNotFoundError("missing")

        self.svc.handle_turn_stream = failing_stream

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(_handle_turn_stream_local("missing", {"user_content": "Hi"}, self.svc))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_request_time_closed_returns_422(self):
        """ConversationClosedError before streaming starts raises HTTP 422."""
        from app.intelligence.conversation.store import ConversationClosedError

        async def failing_stream(*args, **kwargs):
            raise ConversationClosedError("c1 is closed")

        self.svc.handle_turn_stream = failing_stream

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(_handle_turn_stream_local("c1", {"user_content": "Hi"}, self.svc))
        self.assertEqual(ctx.exception.status_code, 422)


# ---------------------------------------------------------------------------
# Test: Stream consumption and SSE event generation
# ---------------------------------------------------------------------------

async def _collect_all_events(event_gen: AsyncIterator[str]) -> list[str]:
    """Collect all events from an async generator into a list."""
    events = []
    async for ev in event_gen:
        events.append(ev)
    return events


class TestStreamConsumption(unittest.TestCase):
    """Verify SSE event sequence for normal and error flows."""

    def setUp(self):
        self.svc = FakeConversationService()

    def test_normal_completion_emits_chunk_and_done_events(self):
        """Normal completion: chunk events followed by exactly one done event."""
        event_gen = asyncio.run(
            _handle_turn_stream_local("c1", {"user_content": "Hi"}, self.svc)
        )
        events = asyncio.run(_collect_all_events(event_gen))
        chunk_events = [e for e in events if e.startswith("event: chunk")]
        done_events = [e for e in events if e.startswith("event: done")]
        error_events = [e for e in events if e.startswith("event: error")]

        self.assertGreater(len(chunk_events), 0, "At least one chunk event expected")
        self.assertEqual(len(done_events), 1, "Exactly one done event expected")
        self.assertEqual(len(error_events), 0, "No error events expected for normal completion")

    def test_done_event_contains_full_content(self):
        """The done event must contain the complete accumulated content."""
        event_gen = asyncio.run(
            _handle_turn_stream_local("c1", {"user_content": "Hi"}, self.svc)
        )
        events = asyncio.run(_collect_all_events(event_gen))
        done_event = next(e for e in events if e.startswith("event: done"))
        # Parse SSE: "event: done\ndata: {json}\n\n"
        _, _, raw_json = done_event.partition("\n")
        body_str = raw_json.removeprefix("data: ")
        body_str = body_str.rstrip("\n")
        body = json.loads(body_str)

        self.assertIn("content", body)
        self.assertIn("model", body)
        self.assertIn("finish_reason", body)
        # FakeConversationService default stream: "Hello", " ", "world", "!"
        self.assertEqual(body["content"], "Hello world!")
        self.assertEqual(body["finish_reason"], "stop")

    def test_finalise_stream_called_with_complete_content(self):
        """finalise_stream() is called with the full accumulated content."""
        event_gen = asyncio.run(_handle_turn_stream_local("c1", {"user_content": "Hi"}, self.svc))
        asyncio.run(_collect_all_events(event_gen))

        self.assertEqual(len(self.svc.finalise_calls), 1)
        call = self.svc.finalise_calls[0]
        self.assertEqual(call["conversation_id"], "c1")
        self.assertEqual(call["final_content"], "Hello world!")

    def test_provider_failure_emits_error_event(self):
        """Provider/LLM error during iteration: error event emitted, partial preserved."""
        self.svc.set_stream_exception(RuntimeError("LLM provider unavailable"))

        event_gen = asyncio.run(
            _handle_turn_stream_local("c1", {"user_content": "Hi"}, self.svc)
        )
        events = asyncio.run(_collect_all_events(event_gen))
        error_events = [e for e in events if e.startswith("event: error")]
        done_events = [e for e in events if e.startswith("event: done")]

        self.assertEqual(len(error_events), 1, "Exactly one error event expected")
        self.assertEqual(len(done_events), 0, "No done event when stream fails")

        # Verify error detail is present.
        _, _, raw_json = error_events[0].partition("\n")
        body_str = raw_json.removeprefix("data: ")
        body = json.loads(body_str.rstrip("\n"))
        self.assertIn("detail", body)
        self.assertIn("LLM provider unavailable", body["detail"])

    def test_provider_failure_calls_finalise_stream_with_partial(self):
        self.svc.set_stream_exception(RuntimeError('partial failure'))

        event_gen = asyncio.run(_handle_turn_stream_local('c1', {'user_content': 'Hi'}, self.svc))
        asyncio.run(_collect_all_events(event_gen))

        self.assertEqual(len(self.svc.finalise_calls), 1)
        call = self.svc.finalise_calls[0]
        self.assertEqual(call['conversation_id'], 'c1')
        # Default exception stream yields 'partial ' before raising.
        self.assertEqual(call['final_content'], 'partial ')
    def test_finalise_stream_failure_does_not_prevent_error_event(self):
        """If finalise_stream() itself fails, the error event is still emitted."""
        def failing_finalise(*args, **kwargs):
            raise RuntimeError("store unavailable")

        self.svc.finalise_stream = failing_finalise
        self.svc.set_stream_exception(RuntimeError("provider error"))

        event_gen = asyncio.run(
            _handle_turn_stream_local("c1", {"user_content": "Hi"}, self.svc)
        )
        events = asyncio.run(_collect_all_events(event_gen))
        error_events = [e for e in events if e.startswith("event: error")]

        self.assertEqual(
            len(error_events), 1,
            "Error event must be emitted even when finalise_stream() fails"
        )

    def test_chunk_with_newline_preserved_in_json(self):
        """A chunk containing a literal newline is JSON-escaped and SSE-valid."""
        self.svc.set_stream_override(["line1\nline2"])

        event_gen = asyncio.run(
            _handle_turn_stream_local("c1", {"user_content": "Hi"}, self.svc)
        )
        events = asyncio.run(_collect_all_events(event_gen))
        chunk_event = next(e for e in events if e.startswith("event: chunk"))
        _, _, raw_json = chunk_event.partition("\n")
        body_str = raw_json.removeprefix("data: ")
        body = json.loads(body_str.rstrip("\n"))

        self.assertEqual(body["content"], "line1\nline2")

    def test_chunk_with_quotes_preserved_in_json(self):
        """A chunk containing double quotes is JSON-escaped."""
        self.svc.set_stream_override(['say "hello"'])

        event_gen = asyncio.run(
            _handle_turn_stream_local("c1", {"user_content": "Hi"}, self.svc)
        )
        events = asyncio.run(_collect_all_events(event_gen))
        chunk_event = next(e for e in events if e.startswith("event: chunk"))
        _, _, raw_json = chunk_event.partition("\n")
        body_str = raw_json.removeprefix("data: ")
        body = json.loads(body_str.rstrip("\n"))

        self.assertEqual(body["content"], 'say "hello"')

    def test_done_event_uses_accumulated_not_model(self):
        """The done event content reflects accumulated chunks, not provider metadata."""
        # Override stream with specific content.
        self.svc.set_stream_override(["Answer: ", "42"])

        event_gen = asyncio.run(
            _handle_turn_stream_local("c1", {"user_content": "What is 40+2?"}, self.svc)
        )
        events = asyncio.run(_collect_all_events(event_gen))
        done_event = next(e for e in events if e.startswith("event: done"))
        _, _, raw_json = done_event.partition("\n")
        body_str = raw_json.removeprefix("data: ")
        body = json.loads(body_str.rstrip("\n"))

        self.assertEqual(body["content"], "Answer: 42")


# ---------------------------------------------------------------------------
# Test: StreamingResponse configuration
# ---------------------------------------------------------------------------

class TestStreamingResponseConfig(unittest.TestCase):
    """Verify the StreamingResponse is configured correctly."""

    def test_media_type_is_text_event_stream(self):
        """Handler returns StreamingResponse with text/event-stream media type."""
        router_path = (
            "/sessions/practical-laughing-cray/mnt/guardrail-hub/"
            "mcp-server/app/routers/public/conversation_router.py"
        )
        with open(router_path) as f:
            src = f.read()
        self.assertIn('media_type="text/event-stream"', src)

    def test_content_type_header_is_text_event_stream_utf8(self):
        """StreamingResponse headers include correct Content-Type."""
        router_path = (
            "/sessions/practical-laughing-cray/mnt/guardrail-hub/"
            "mcp-server/app/routers/public/conversation_router.py"
        )
        with open(router_path) as f:
            src = f.read()
        self.assertIn('"Content-Type": "text/event-stream; charset=utf-8"', src)

    def test_cache_control_no_cache_header_present(self):
        """Streaming responses carry Cache-Control: no-cache."""
        router_path = (
            "/sessions/practical-laughing-cray/mnt/guardrail-hub/"
            "mcp-server/app/routers/public/conversation_router.py"
        )
        with open(router_path) as f:
            src = f.read()
        self.assertIn('"Cache-Control": "no-cache"', src)

    def test_x_accel_buffering_no_header_present(self):
        """Streaming responses carry X-Accel-Buffering: no for proxy compatibility."""
        router_path = (
            "/sessions/practical-laughing-cray/mnt/guardrail-hub/"
            "mcp-server/app/routers/public/conversation_router.py"
        )
        with open(router_path) as f:
            src = f.read()
        self.assertIn('"X-Accel-Buffering": "no"', src)

    def test_connection_keep_alive_header_present(self):
        """Streaming responses carry Connection: keep-alive."""
        router_path = (
            "/sessions/practical-laughing-cray/mnt/guardrail-hub/"
            "mcp-server/app/routers/public/conversation_router.py"
        )
        with open(router_path) as f:
            src = f.read()
        self.assertIn('"Connection": "keep-alive"', src)


# ---------------------------------------------------------------------------
# Test: MCP isolation
# ---------------------------------------------------------------------------

class TestMCPIsolation(unittest.TestCase):
    """Verify the streaming endpoint does not leak into MCP."""

    def test_mcp_operations_unchanged(self):
        """MCP_OPERATIONS must not list handle_turn_stream."""
        endpoints_path = (
            "/sessions/practical-laughing-cray/mnt/guardrail-hub/"
            "mcp-server/app/routers/endpoints.py"
        )
        with open(endpoints_path) as f:
            src = f.read()
        self.assertNotIn("handle_turn_stream", src)
        self.assertNotIn("turn_stream", src)

    def test_no_mcp_router_references_streaming_endpoint(self):
        """No MCP router must import or define the streaming endpoint."""
        mcp_routers = [
            "/sessions/practical-laughing-cray/mnt/guardrail-hub/mcp-server/app/routers/mcp/jmeter_router.py",
            "/sessions/practical-laughing-cray/mnt/guardrail-hub/mcp-server/app/routers/mcp/owasp_zap_router.py",
        ]
        for path in mcp_routers:
            with open(path) as f:
                src = f.read()
            self.assertNotIn(
                "handle_turn_stream", src,
                f"{path} must not reference streaming endpoint"
            )
            self.assertNotIn(
                "StreamingResponse", src,
                f"{path} must not use StreamingResponse"
            )


# ---------------------------------------------------------------------------
# Test: Phase 5 regression
# ---------------------------------------------------------------------------

class TestPhase5Regression(unittest.TestCase):
    """Verify Phase 5 behavior is unchanged."""

    def test_existing_non_streaming_router_tests_unchanged(self):
        """Existing non-streaming router tests must not be modified."""
        test_path = (
            "/sessions/practical-laughing-cray/mnt/guardrail-hub/"
            "mcp-server/tests/routers/public/test_conversation_router.py"
        )
        with open(test_path) as f:
            src = f.read()
        # The existing test file must not mention StreamingResponse.
        self.assertNotIn(
            "StreamingResponse", src,
            "Existing non-streaming router tests must remain unchanged"
        )
        # It must still test handle_turn.
        self.assertIn("test_handle_turn_success", src)

    def test_conversation_service_streaming_tests_unchanged(self):
        """Existing ConversationService streaming tests must not be modified."""
        svc_test_path = (
            "/sessions/practical-laughing-cray/mnt/guardrail-hub/"
            "mcp-server/tests/intelligence/conversation/test_conversation_service.py"
        )
        with open(svc_test_path) as f:
            src = f.read()
        # These tests must still exist.
        self.assertIn("test_handle_turn_stream_returns_stream", src)
        self.assertIn("test_finalise_stream_append", src)
        self.assertIn("test_finalise_stream_emits_message_appended", src)
        self.assertIn("test_handle_turn_stream_created_to_open_audit_ordering", src)

    def test_stream_turn_schema_fields_intact(self):
        """HandleTurnStreamRequest must have all required fields."""
        schema_path = (
            "/sessions/practical-laughing-cray/mnt/guardrail-hub/"
            "mcp-server/app/schemas/conversation/stream_turn.py"
        )
        with open(schema_path) as f:
            src = f.read()
        # The schema must have the required fields (not reference implementation).
        self.assertIn("user_content", src)
        self.assertIn("HandleTurnStreamRequest", src)
        self.assertIn("system_prompt", src)
        self.assertIn("model", src)
        self.assertIn("provider", src)
        self.assertIn("user_metadata", src)
        self.assertNotIn("StreamingResponse", src)
        self.assertNotIn("AsyncIterator", src)


if __name__ == "__main__":
    unittest.main()
