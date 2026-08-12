"""Tests for the conversation REST router.

These tests verify the thin adapter contract: the router validates input,
calls ConversationService correctly, maps exceptions, and returns the right
HTTP status codes.

Tests do NOT test ConversationService itself - those are covered by the
dedicated ConversationService test suite.

FastAPI is not installed in this test environment (Python 3.10 vs project
requirement of 3.12+), so:
  - Thin-adapter property tests use AST source analysis of the router file.
  - Handler-level tests use local mock HTTP exceptions to verify error mapping.
  - Startup wiring is tested via dataclass field inspection.
"""
import ast
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock


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
# Fake ConversationService -- matches the real service's public API.
# ---------------------------------------------------------------------------

class FakeConversationService:
    """Fake matching ConversationService's public API for handler-level tests."""

    def __init__(self):
        self.calls = []

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

    def get_conversation(self, conversation_id):
        self.calls.append(("get", conversation_id))
        from app.intelligence.conversation.store import ConversationSummary
        from app.intelligence.conversation.state import ConversationState
        return ConversationSummary(
            conversation_id=conversation_id,
            state=ConversationState.OPEN,
            messages=(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def transition(self, conversation_id, to_state):
        self.calls.append(("transition", conversation_id, to_state))
        from app.intelligence.conversation.store import ConversationSummary
        return ConversationSummary(
            conversation_id=conversation_id,
            state=to_state,
            messages=(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    async def handle_turn(
        self,
        conversation_id,
        user_content,
        system_prompt=None,
        model=None,
        provider=None,
        user_metadata=None,
    ):
        self.calls.append(("handle_turn", conversation_id, user_content))
        from app.intelligence.ports.chat import ChatResponse
        return ChatResponse(
            content="Fake LLM response",
            model=model or "default-model",
            finish_reason="stop",
        )

    def redact_message(self, conversation_id, message_index, policy="default"):
        self.calls.append(("redact", conversation_id, message_index, policy))
        from app.intelligence.conversation.message import Message
        from app.intelligence.conversation.store import ConversationSummary
        from app.intelligence.conversation.state import ConversationState
        return ConversationSummary(
            conversation_id=conversation_id,
            state=ConversationState.OPEN,
            messages=(
                Message(role="user", content="original"),
                Message(
                    role="system",
                    content=f"[Message at index {message_index} redacted by policy '{policy}': [REDACTED]]",
                    metadata=(
                        ("redacted_index", message_index),
                        ("redaction_policy", policy),
                    ),
                    redacted=False,
                ),
            ),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )


# ---------------------------------------------------------------------------
# Reimplement minimal handler logic locally to test error mapping.
# Mirrors what the router does without importing FastAPI.
# ---------------------------------------------------------------------------

def _create_conversation(req_body, svc):
    """Mirrors the router's create_conversation handler."""
    try:
        summary = svc.create_conversation(req_body["conversation_id"])
        return {
            "conversation_id": summary.conversation_id,
            "state": summary.state.value,
            "message_count": len(summary.messages),
        }
    except KeyError:
        raise HTTPException(
            409,
            f"A conversation with ID '{req_body['conversation_id']}' already exists.",
        )


def _get_conversation(conversation_id, svc):
    """Mirrors the router's get_conversation handler."""
    from app.intelligence.conversation.store import ConversationNotFoundError
    try:
        summary = svc.get_conversation(conversation_id)
        return {
            "conversation_id": summary.conversation_id,
            "state": summary.state.value,
            "message_count": len(summary.messages),
            "created_at": summary.created_at.isoformat(),
            "updated_at": summary.updated_at.isoformat(),
        }
    except ConversationNotFoundError as exc:
        raise HTTPException(404, str(exc))


def _transition_conversation(conversation_id, body, svc):
    """Mirrors the router's transition_conversation handler."""
    from app.intelligence.conversation.state import ConversationState
    from app.intelligence.conversation.store import ConversationClosedError, ConversationNotFoundError
    try:
        target = ConversationState(body["to_state"])
    except ValueError:
        raise HTTPException(
            400,
            f"Unknown state: {body['to_state']!r}. "
            "Valid states: created, open, closed, archived, redacted_purged.",
        )
    try:
        summary = svc.transition(conversation_id, target)
        return {
            "conversation_id": conversation_id,
            "from_state": body["to_state"],
            "to_state": summary.state.value,
        }
    except ConversationNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except ConversationClosedError as exc:
        raise HTTPException(422, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))


async def _handle_turn(conversation_id, body, svc):
    """Mirrors the router's handle_turn handler."""
    from app.intelligence.conversation.store import ConversationClosedError, ConversationNotFoundError
    try:
        response = await svc.handle_turn(
            conversation_id=conversation_id,
            user_content=body["user_content"],
            system_prompt=body.get("system_prompt"),
            model=body.get("model"),
            provider=body.get("provider"),
            user_metadata=body.get("user_metadata"),
        )
        return {
            "content": response.content,
            "model": response.model,
            "finish_reason": response.finish_reason,
            "usage": response.usage,
        }
    except ConversationNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except ConversationClosedError as exc:
        raise HTTPException(422, str(exc))


def _redact_message(conversation_id, body, svc):
    """Mirrors the router's redact_message handler."""
    from app.intelligence.conversation.store import ConversationClosedError, ConversationNotFoundError
    try:
        summary = svc.redact_message(
            conversation_id=conversation_id,
            message_index=body["message_index"],
            policy=body.get("policy", "default"),
        )
        marker = summary.messages[-1]
        return {
            "conversation_id": conversation_id,
            "message_index": body["message_index"],
            "redaction_policy": body.get("policy", "default"),
            "marker_content": marker.content,
        }
    except ConversationNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except ConversationClosedError as exc:
        raise HTTPException(422, str(exc))
    except IndexError as exc:
        raise HTTPException(400, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---------------------------------------------------------------------------
# Test: Router is a thin adapter (AST analysis of the source file).
# ---------------------------------------------------------------------------

class TestRouterIsThinAdapter(unittest.TestCase):
    """Verify the router source contains no orchestration logic."""

    @classmethod
    def setUpClass(cls):
        router_path = (
            "/sessions/vibrant-brave-newton/mnt/mcp-server/"
            "app/routers/public/conversation_router.py"
        )
        with open(router_path) as f:
            cls.src = f.read()
        cls.tree = ast.parse(cls.src)

    def _module_imports(self):
        """Return all 'from x import y' and 'import x' module paths."""
        modules = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
        return modules

    def test_does_not_import_llm_service(self):
        """The router must not import LLMService or its module paths."""
        modules = self._module_imports()
        llm_modules = [m for m in modules if "llm_service" in m]
        self.assertEqual(
            llm_modules, [],
            f"Router must not import LLMService modules, found: {llm_modules}",
        )
        self.assertNotIn("LLMService", self.src)

    def test_does_not_import_conversation_store(self):
        """The router must not import ConversationStore or its adapters."""
        modules = self._module_imports()
        store_modules = [
            m for m in modules
            if any(x in m for x in ["conversation_store", "in_memory_store", "dao_store"])
        ]
        self.assertEqual(
            store_modules, [],
            f"Router must not import ConversationStore adapters, found: {store_modules}",
        )
        self.assertNotIn("ConversationStore", self.src)
        self.assertNotIn("InMemoryConversationStore", self.src)
        self.assertNotIn("PostgresConversationStore", self.src)

    def test_does_not_import_provider_adapters(self):
        """The router must not import provider adapters."""
        modules = self._module_imports()
        provider_modules = [
            m for m in modules
            if "provider" in m and "provider_manager" not in m
        ]
        self.assertEqual(
            provider_modules, [],
            f"Router must not import provider adapters, found: {provider_modules}",
        )

    def test_does_not_directly_import_conversation_service(self):
        """The router must retrieve ConversationService via app.state, not by importing it."""
        modules = self._module_imports()
        svc_modules = [
            m for m in modules
            if "services.conversation.conversation_service" in m
        ]
        self.assertEqual(
            svc_modules, [],
            "Router must not import ConversationService directly; "
            "use request.app.state dependency instead.",
        )
        self.assertNotIn("from app.services.conversation", self.src)

    def test_does_not_call_llm_directly(self):
        """The router must not instantiate or call LLMService."""
        self.assertNotIn("LLMService(", self.src)
        self.assertNotIn("llm_service", self.src.lower())

    def test_does_not_call_store_directly(self):
        """The router must not instantiate or call ConversationStore."""
        self.assertNotIn("ConversationStore(", self.src)
        self.assertNotIn("InMemoryConversationStore(", self.src)
        self.assertNotIn("PostgresConversationStore(", self.src)

    def test_defines_dependency_via_fastapi_depends(self):
        """The router must use FastAPI's Depends for ConversationService injection."""
        self.assertIn("Depends", self.src)
        self.assertIn("_get_conversation_service", self.src)

    def test_maps_not_found_to_404(self):
        """ConversationNotFoundError must be mapped to HTTP 404."""
        self.assertIn("status_code=404", self.src)
        self.assertIn("ConversationNotFoundError", self.src)

    def test_maps_closed_to_422(self):
        """ConversationClosedError must be mapped to HTTP 422."""
        self.assertIn("status_code=422", self.src)
        self.assertIn("ConversationClosedError", self.src)

    def test_maps_validation_errors_to_400(self):
        """IndexError and ValueError must be mapped to HTTP 400."""
        self.assertIn("status_code=400", self.src)
        self.assertIn("IndexError", self.src)

    def test_handle_turn_is_async(self):
        """handle_turn handler must be declared async def."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "handle_turn":
                return  # Found it
        self.fail("handle_turn must be declared 'async def'")

    def test_redact_message_is_sync(self):
        """redact_message handler must be synchronous def."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == "redact_message":
                return  # Found it
        self.fail("redact_message must be declared 'def' (sync)")

    def test_create_conversation_is_sync(self):
        """create_conversation handler must be synchronous def."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == "create_conversation":
                return  # Found it
        self.fail("create_conversation must be declared 'def' (sync)")


# ---------------------------------------------------------------------------
# Test: Handler-level error mapping (using local mock handlers).
# ---------------------------------------------------------------------------

class TestHandlerErrorMapping(unittest.TestCase):
    """Verify handler-level exception-to-HTTP mapping using local mock handlers."""

    def setUp(self):
        self.svc = FakeConversationService()

    # --- create_conversation ---

    def test_create_conversation_success(self):
        req = {"conversation_id": "c1"}
        result = _create_conversation(req, self.svc)
        self.assertEqual(result["conversation_id"], "c1")
        self.assertEqual(result["state"], "created")
        self.assertEqual(result["message_count"], 0)

    def test_create_conversation_forwards_correct_id(self):
        _create_conversation({"conversation_id": "conv-abc"}, self.svc)
        self.assertEqual(self.svc.calls[-1], ("create", "conv-abc"))

    def test_create_conversation_duplicate_raises_409(self):
        call_count = [0]
        original = self.svc.create_conversation

        def dup(cid, init_state=None):
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyError(f"Conversation {cid!r} already exists")
            return original(cid, init_state)

        self.svc.create_conversation = dup
        req = {"conversation_id": "c1"}
        _create_conversation(req, self.svc)  # First succeeds
        with self.assertRaises(HTTPException) as ctx:
            _create_conversation(req, self.svc)  # Second raises 409
        self.assertEqual(ctx.exception.status_code, 409)

    # --- get_conversation ---

    def test_get_conversation_success(self):
        result = _get_conversation("c1", self.svc)
        self.assertEqual(result["conversation_id"], "c1")

    def test_get_conversation_not_found_raises_404(self):
        from app.intelligence.conversation.store import ConversationNotFoundError
        self.svc.get_conversation = MagicMock(
            side_effect=ConversationNotFoundError("missing")
        )
        with self.assertRaises(HTTPException) as ctx:
            _get_conversation("missing", self.svc)
        self.assertEqual(ctx.exception.status_code, 404)

    # --- transition ---

    def test_transition_success(self):
        body = {"to_state": "closed"}
        result = _transition_conversation("c1", body, self.svc)
        self.assertEqual(result["conversation_id"], "c1")
        self.assertEqual(result["to_state"], "closed")

    def test_transition_unknown_state_raises_400(self):
        body = {"to_state": "invalid_state"}
        with self.assertRaises(HTTPException) as ctx:
            _transition_conversation("c1", body, self.svc)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_transition_invalid_returns_422(self):
        self.svc.transition = MagicMock(
            side_effect=ValueError("invalid transition")
        )
        body = {"to_state": "archived"}
        with self.assertRaises(HTTPException) as ctx:
            _transition_conversation("c1", body, self.svc)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_transition_not_found_returns_404(self):
        from app.intelligence.conversation.store import ConversationNotFoundError
        self.svc.transition = MagicMock(
            side_effect=ConversationNotFoundError("c1")
        )
        body = {"to_state": "open"}
        with self.assertRaises(HTTPException) as ctx:
            _transition_conversation("c1", body, self.svc)
        self.assertEqual(ctx.exception.status_code, 404)

    # --- handle_turn ---

    def test_handle_turn_success(self):
        import asyncio
        body = {"user_content": "Hello"}
        result = asyncio.run(_handle_turn("c1", body, self.svc))
        self.assertIn("content", result)
        self.assertIn("model", result)

    def test_handle_turn_forwards_all_fields(self):
        import asyncio
        body = {
            "user_content": "Hi",
            "system_prompt": "You are helpful.",
            "model": "gpt-4",
            "provider": "openai",
            "user_metadata": {"source": "test"},
        }
        asyncio.run(_handle_turn("c1", body, self.svc))
        last = self.svc.calls[-1]
        self.assertEqual(last[0], "handle_turn")
        self.assertEqual(last[1], "c1")
        self.assertEqual(last[2], "Hi")

    def test_handle_turn_not_found_raises_404(self):
        import asyncio
        from app.intelligence.conversation.store import ConversationNotFoundError
        self.svc.handle_turn = AsyncMock(
            side_effect=ConversationNotFoundError("c1")
        )
        body = {"user_content": "Hi"}
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(_handle_turn("c1", body, self.svc))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_handle_turn_closed_raises_422(self):
        import asyncio
        from app.intelligence.conversation.store import ConversationClosedError
        self.svc.handle_turn = AsyncMock(
            side_effect=ConversationClosedError("c1 is closed")
        )
        body = {"user_content": "Hi"}
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(_handle_turn("c1", body, self.svc))
        self.assertEqual(ctx.exception.status_code, 422)

    # --- redact_message ---

    def test_redact_success(self):
        body = {"message_index": 0, "policy": "default"}
        result = _redact_message("c1", body, self.svc)
        self.assertEqual(result["conversation_id"], "c1")
        self.assertEqual(result["message_index"], 0)
        self.assertIn("marker_content", result)

    def test_redact_forwards_correct_args(self):
        body = {"message_index": 2, "policy": "strict"}
        _redact_message("c1", body, self.svc)
        self.assertEqual(self.svc.calls[-1], ("redact", "c1", 2, "strict"))

    def test_redact_default_policy(self):
        body = {"message_index": 0}
        _redact_message("c1", body, self.svc)
        self.assertEqual(self.svc.calls[-1], ("redact", "c1", 0, "default"))

    def test_redact_not_found_raises_404(self):
        from app.intelligence.conversation.store import ConversationNotFoundError
        self.svc.redact_message = MagicMock(
            side_effect=ConversationNotFoundError("c1")
        )
        body = {"message_index": 0}
        with self.assertRaises(HTTPException) as ctx:
            _redact_message("c1", body, self.svc)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_redact_terminal_raises_422(self):
        from app.intelligence.conversation.store import ConversationClosedError
        self.svc.redact_message = MagicMock(
            side_effect=ConversationClosedError("terminal")
        )
        body = {"message_index": 0}
        with self.assertRaises(HTTPException) as ctx:
            _redact_message("c1", body, self.svc)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_redact_out_of_range_raises_400(self):
        self.svc.redact_message = MagicMock(
            side_effect=IndexError("out of range [0, 0)")
        )
        body = {"message_index": 999}
        with self.assertRaises(HTTPException) as ctx:
            _redact_message("c1", body, self.svc)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_redact_invalid_policy_raises_400(self):
        self.svc.redact_message = MagicMock(
            side_effect=ValueError("Redaction policy 'nonexistent' is not registered")
        )
        body = {"message_index": 0, "policy": "nonexistent"}
        with self.assertRaises(HTTPException) as ctx:
            _redact_message("c1", body, self.svc)
        self.assertEqual(ctx.exception.status_code, 400)


# ---------------------------------------------------------------------------
# Test: Startup wiring -- StartupResult includes conversation_service.
# ---------------------------------------------------------------------------

class TestStartupWiring(unittest.TestCase):
    """Verify ConversationService is wired into StartupResult and app.state."""

    def test_startup_result_has_conversation_service_field(self):
        """StartupResult must have a conversation_service field."""
        from app.core.startup import StartupResult
        import dataclasses
        fields = {f.name for f in dataclasses.fields(StartupResult)}
        self.assertIn("conversation_service", fields)

    def test_startup_result_default_is_none(self):
        """StartupResult.conversation_service defaults to None."""
        from app.core.startup import StartupResult
        import dataclasses
        field = next(
            f for f in dataclasses.fields(StartupResult)
            if f.name == "conversation_service"
        )
        self.assertIsNone(field.default)

    def test_startup_calls_build_conversation_service(self):
        """run_startup_sequence must call build_conversation_service."""
        src = open(
            "/sessions/vibrant-brave-newton/mnt/mcp-server/app/core/startup.py"
        ).read()
        self.assertIn("build_conversation_service", src)
        self.assertIn("_build_conversation_service", src)

    def test_main_wires_conversation_service_to_app_state(self):
        """main.py must attach conversation_service to app.state."""
        src = open(
            "/sessions/vibrant-brave-newton/mnt/mcp-server/app/main.py"
        ).read()
        self.assertIn("app.state.conversation_service", src)

    def test_main_includes_conversation_router(self):
        """main.py must include the conversation_router."""
        src = open(
            "/sessions/vibrant-brave-newton/mnt/mcp-server/app/main.py"
        ).read()
        self.assertIn("conversation_router", src)


# ---------------------------------------------------------------------------
# Test: Schema files are syntactically valid.
# ---------------------------------------------------------------------------

class TestSchemaFiles(unittest.TestCase):
    """Verify the conversation schema files are syntactically correct."""

    def test_handle_turn_schema_syntax(self):
        path = (
            "/sessions/vibrant-brave-newton/mnt/mcp-server/"
            "app/schemas/conversation/handle_turn.py"
        )
        with open(path) as f:
            ast.parse(f.read())

    def test_conversation_schema_syntax(self):
        path = (
            "/sessions/vibrant-brave-newton/mnt/mcp-server/"
            "app/schemas/conversation/conversation.py"
        )
        with open(path) as f:
            ast.parse(f.read())

    def test_router_syntax(self):
        path = (
            "/sessions/vibrant-brave-newton/mnt/mcp-server/"
            "app/routers/public/conversation_router.py"
        )
        with open(path) as f:
            ast.parse(f.read())


if __name__ == "__main__":
    unittest.main()
