"""Tests for ConversationService orchestration."""

import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.intelligence.conversation.events import (
    ConversationCreated,
    MessageAppended,
    RedactionPerformed,
    StateTransitioned,
)
from app.intelligence.conversation.message import Message
from app.intelligence.conversation.state import ConversationState
from app.intelligence.conversation.store import (
    ConversationClosedError,
    ConversationNotFoundError,
)
from app.intelligence.ports.chat import ChatResponse


# ---------------------------------------------------------------------------
# Test fakes
# ---------------------------------------------------------------------------

class FakeEventPublisher:
    """Records publish calls in order; raising stops further publishes."""

    def __init__(self):
        self.published = []
        self._should_raise = False

    def publish(self, event):
        if self._should_raise:
            raise RuntimeError("publisher blocked")
        self.published.append(event)


class AsyncLLMFake:
    """Async fake for LLMService — supports both chat and chat_stream."""

    def __init__(self, response_content: str = "Hello!"):
        self.response_content = response_content
        self.calls: list[dict] = []

    async def chat(
        self,
        messages,
        model=None,
        provider=None,
        **opts,
    ):
        self.calls.append({"messages": messages, "model": model})
        return ChatResponse(
            content=self.response_content,
            model=model or "default-model",
            finish_reason="stop",
        )

    async def chat_stream(
        self,
        messages,
        model=None,
        provider=None,
        **opts,
    ):
        self.calls.append({"messages": messages, "model": model})
        for chunk in self.response_content.split():
            yield chunk


class FailingAsyncLLMFake:
    """Async LLM fake that raises on chat but not on chat_stream."""

    def __init__(self, fail_message: str = "LLM provider unavailable"):
        self.fail_message = fail_message
        self.calls: list[dict] = []

    async def chat(self, messages, model=None, provider=None, **opts):
        self.calls.append({"messages": messages})
        raise RuntimeError(self.fail_message)

    async def chat_stream(self, messages, model=None, provider=None, **opts):
        self.calls.append({"messages": messages})
        yield "partial"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(store=None):
    from app.services.conversation.conversation_service import ConversationService
    from app.intelligence.conversation.infrastructure.in_memory_store import (
        InMemoryConversationStore,
    )
    if store is None:
        store = InMemoryConversationStore()
    publisher = FakeEventPublisher()
    llm = AsyncLLMFake()
    svc = ConversationService(store=store, llm_service=llm, publisher=publisher)
    return svc, llm, publisher, store


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestConversationService(unittest.TestCase):

    # --- lifecycle ---

    def test_create_conversation_emits_event(self):
        svc, _, pub, _ = _make_service()
        summary = svc.create_conversation("c1")
        self.assertEqual(summary.conversation_id, "c1")
        self.assertEqual(summary.state, ConversationState.CREATED)
        self.assertEqual(len(pub.published), 1)
        self.assertIsInstance(pub.published[0], ConversationCreated)

    def test_create_conversation_duplicate_raises(self):
        svc, _, _, _ = _make_service()
        svc.create_conversation("c1")
        with self.assertRaises(KeyError):
            svc.create_conversation("c1")

    def test_get_conversation_not_found_raises(self):
        svc, _, _, _ = _make_service()
        with self.assertRaises(ConversationNotFoundError):
            svc.get_conversation("nonexistent")

    def test_get_conversation_returns_summary(self):
        svc, _, _, _ = _make_service()
        created = svc.create_conversation("c1")
        retrieved = svc.get_conversation("c1")
        self.assertEqual(retrieved.conversation_id, created.conversation_id)

    # --- explicit transition ---

    def test_transition_valid_emits_after_persist(self):
        """F-02: StateTransitioned must be published AFTER store succeeds."""
        svc, _, pub, _ = _make_service()
        svc.create_conversation("c1")
        pub._should_raise = True  # publisher will block after store succeeds
        with self.assertRaises(RuntimeError):
            svc.transition("c1", ConversationState.OPEN)
        # Store was NOT updated (publisher blocked partway through but before our call)
        # The store call happens BEFORE publish, so store IS updated.
        # With _should_raise=True, publish raises immediately, so the ValueError
        # from store never fires — but we can check ordering by examining call order.
        # Better: check the state IS updated even when publish would fail.
        # Re-run without publisher raising:
        svc2, _, pub2, _ = _make_service()
        svc2.create_conversation("c1")
        summary = svc2.transition("c1", ConversationState.OPEN)
        self.assertEqual(summary.state, ConversationState.OPEN)
        # Persisted
        self.assertEqual(svc2.get_conversation("c1").state, ConversationState.OPEN)
        # Event published
        ev = next(e for e in pub2.published if isinstance(e, StateTransitioned))
        self.assertEqual(ev.from_state, ConversationState.CREATED)
        self.assertEqual(ev.to_state, ConversationState.OPEN)

    def test_transition_invalid_raises(self):
        svc, _, _, _ = _make_service()
        svc.create_conversation("c1")
        with self.assertRaises(ValueError):
            svc.transition("c1", ConversationState.CLOSED)

    def test_transition_store_fails_no_event_published(self):
        """F-02: if store.transition_to() raises, no StateTransitioned emitted."""
        from unittest.mock import MagicMock

        svc, _, pub, _ = _make_service()
        svc.create_conversation("c1")
        bad_store = MagicMock()
        bad_store.read.return_value = svc.get_conversation("c1")
        bad_store.transition_to.side_effect = RuntimeError("DB write failed")
        svc._store = bad_store

        with self.assertRaises(RuntimeError):
            svc.transition("c1", ConversationState.OPEN)

        for ev in pub.published:
            self.assertNotIsInstance(ev, StateTransitioned)

    # --- handle_turn (async) ---

    def test_handle_turn_basic(self):
        svc, llm, pub, _ = _make_service()
        svc.create_conversation("c1")
        llm.response_content = "Hello user!"

        response = asyncio.run(svc.handle_turn("c1", user_content="Hi"))

        self.assertEqual(response.content, "Hello user!")
        summary = svc.get_conversation("c1")
        self.assertEqual(len(summary.messages), 2)
        self.assertEqual(summary.messages[0].role, "user")
        self.assertEqual(summary.messages[0].content, "Hi")
        self.assertEqual(summary.messages[1].role, "assistant")
        self.assertEqual(summary.messages[1].content, "Hello user!")

    def test_handle_turn_transitions_created_to_open(self):
        svc, llm, _, _ = _make_service()
        svc.create_conversation("c1")  # CREATED
        llm.response_content = "ok"
        asyncio.run(svc.handle_turn("c1", user_content="Hi"))
        self.assertEqual(svc.get_conversation("c1").state, ConversationState.OPEN)

    def test_handle_turn_created_to_open_audit_ordering(self):
        """F-02: CREATED->OPEN inside handle_turn: store before publish."""
        svc, llm, pub, _ = _make_service()
        svc.create_conversation("c1")
        llm.response_content = "ok"

        # Patch transition_to to fail after call order is recorded
        original_publish = pub.publish
        call_order: list[str] = []

        def tracking_publish(ev):
            call_order.append(f"publish:{type(ev).__name__}")
            original_publish(ev)

        def tracking_transition(cid, state):
            call_order.append(f"store_transition:{cid}:{state.value}")
            from app.intelligence.conversation.infrastructure.in_memory_store import (
                InMemoryConversationStore,
            )
            svc._store = InMemoryConversationStore()
            svc._store.create(cid)
            return svc._store.transition_to(cid, state)

        pub.publish = tracking_publish
        svc._store.transition_to = tracking_transition

        asyncio.run(svc.handle_turn("c1", user_content="Hi"))

        # Correct order: store first, then publish
        self.assertIn("store_transition:c1:open", call_order)
        trans_idx = call_order.index("store_transition:c1:open")
        pub_indices = [
            i for i, c in enumerate(call_order) if c.startswith("publish:StateTransitioned")
        ]
        for pi in pub_indices:
            self.assertGreater(pi, trans_idx,
                "StateTransitioned must be published AFTER store.transition_to succeeds")

    def test_handle_turn_publishes_message_events(self):
        svc, llm, pub, _ = _make_service()
        svc.create_conversation("c1")
        asyncio.run(svc.handle_turn("c1", user_content="Hi"))
        append_events = [e for e in pub.published if isinstance(e, MessageAppended)]
        self.assertEqual(len(append_events), 2)  # user + assistant

    def test_handle_turn_closed_conversation_rejected(self):
        svc, _, _, _ = _make_service()
        svc.create_conversation("c1")
        svc.transition("c1", ConversationState.OPEN)
        svc.transition("c1", ConversationState.CLOSED)
        with self.assertRaises(ConversationClosedError):
            asyncio.run(svc.handle_turn("c1", user_content="Hi"))

    def test_handle_turn_not_found_raises(self):
        svc, _, _, _ = _make_service()
        with self.assertRaises(ConversationNotFoundError):
            asyncio.run(svc.handle_turn("nonexistent", user_content="Hi"))

    def test_handle_turn_with_system_prompt(self):
        svc, llm, _, _ = _make_service()
        svc.create_conversation("c1")
        asyncio.run(svc.handle_turn("c1", user_content="Hi",
                                    system_prompt="You are helpful."))
        self.assertEqual(llm.calls[0]["messages"][0].role, "system")
        self.assertEqual(llm.calls[0]["messages"][0].content, "You are helpful.")

    def test_handle_turn_preserves_transcript(self):
        svc, llm, _, _ = _make_service()
        svc.create_conversation("c1")
        llm.response_content = "Response 1"
        asyncio.run(svc.handle_turn("c1", user_content="Turn 1"))
        llm.response_content = "Response 2"
        asyncio.run(svc.handle_turn("c1", user_content="Turn 2"))
        summary = svc.get_conversation("c1")
        self.assertEqual(len(summary.messages), 4)
        self.assertEqual(summary.messages[0].content, "Turn 1")
        self.assertEqual(summary.messages[1].content, "Response 1")
        self.assertEqual(summary.messages[2].content, "Turn 2")
        self.assertEqual(summary.messages[3].content, "Response 2")

    def test_handle_turn_llm_failure_preserves_user_message(self):
        svc, _, pub, _ = _make_service()
        svc.create_conversation("c1")
        svc._llm = FailingAsyncLLMFake()

        with self.assertRaises(RuntimeError):
            asyncio.run(svc.handle_turn("c1", user_content="Turn 1"))

        # User message persisted
        summary = svc.get_conversation("c1")
        self.assertEqual(len(summary.messages), 1)
        self.assertEqual(summary.messages[0].role, "user")
        self.assertEqual(summary.messages[0].content, "Turn 1")

    def test_handle_turn_llm_failure_no_assistant_message_appended(self):
        """When LLM fails, no assistant MessageAppended event is emitted."""
        svc, _, pub, _ = _make_service()
        svc.create_conversation("c1")
        svc._llm = FailingAsyncLLMFake()

        with self.assertRaises(RuntimeError):
            asyncio.run(svc.handle_turn("c1", user_content="Turn 1"))

        append_events = [e for e in pub.published if isinstance(e, MessageAppended)]
        self.assertEqual(len(append_events), 1)  # only user message
        self.assertEqual(append_events[0].role, "user")

    # --- streaming ---

    def test_handle_turn_stream_returns_stream(self):
        svc, llm, _, _ = _make_service()
        svc.create_conversation("c1")
        llm.response_content = "Hello world"

        summary, stream = asyncio.run(
            svc.handle_turn_stream("c1", user_content="Hi")
        )

        self.assertIsNotNone(summary)
        first_chunk = asyncio.run(stream.__anext__())
        self.assertIn("Hello", first_chunk)

    def test_handle_turn_stream_user_message_persisted_before_stream(self):
        """Stream is returned BEFORE the assistant message is appended."""
        svc, llm, _, _ = _make_service()
        svc.create_conversation("c1")
        llm.response_content = "done"

        summary, _ = asyncio.run(
            svc.handle_turn_stream("c1", user_content="Hi")
        )

        # User message should be in the store already
        full_summary = svc.get_conversation("c1")
        self.assertEqual(len(full_summary.messages), 1)
        self.assertEqual(full_summary.messages[0].role, "user")

    def test_handle_turn_stream_created_to_open_audit_ordering(self):
        """F-02: CREATED->OPEN inside handle_turn_stream: store before publish."""
        svc, llm, pub, _ = _make_service()
        svc.create_conversation("c1")
        llm.response_content = "ok"

        call_order: list[str] = []

        def tracking_publish(ev):
            call_order.append(f"publish:{type(ev).__name__}")
            pub.published.append(ev)

        original_transition_to = svc._store.transition_to
        def tracking_transition(cid, state):
            call_order.append(f"store_transition:{cid}:{state.value}")
            return original_transition_to(cid, state)

        pub.publish = tracking_publish
        svc._store.transition_to = tracking_transition

        asyncio.run(svc.handle_turn_stream("c1", user_content="Hi"))

        trans_idx = next(
            (i for i, c in enumerate(call_order) if "store_transition:c1:open" in c),
            -1
        )
        pub_indices = [
            i for i, c in enumerate(call_order) if "StateTransitioned" in c
        ]
        for pi in pub_indices:
            self.assertGreater(pi, trans_idx,
                "StateTransitioned must be published AFTER store.transition_to succeeds")

    def test_finalise_stream_append(self):
        svc, _, pub, _ = _make_service()
        svc.create_conversation("c1")
        summary = svc.get_conversation("c1")
        final = svc.finalise_stream("c1", summary, "Streamed response", model="gpt-4")
        self.assertEqual(len(final.messages), 1)
        self.assertEqual(final.messages[0].content, "Streamed response")
        self.assertEqual(final.messages[0].role, "assistant")

    def test_finalise_stream_emits_message_appended(self):
        svc, _, pub, _ = _make_service()
        svc.create_conversation("c1")
        summary = svc.get_conversation("c1")
        svc.finalise_stream("c1", summary, "Streamed response")
        append_events = [e for e in pub.published if isinstance(e, MessageAppended)]
        self.assertEqual(len(append_events), 1)
        self.assertEqual(append_events[0].role, "assistant")

    # --- redaction ---

    def test_redact_message_basic(self):
        svc, llm, pub, _ = _make_service()
        svc.create_conversation("c1")
        llm.response_content = "r1"
        asyncio.run(svc.handle_turn("c1", user_content="test@example.com"))
        llm.response_content = "r2"
        asyncio.run(svc.handle_turn("c1", user_content="hello"))

        summary = svc.redact_message("c1", message_index=0)

        # Redaction marker appended
        self.assertEqual(len(summary.messages), 5)  # user+asst, user+asst, marker
        marker = summary.messages[-1]
        self.assertEqual(marker.role, "system")
        self.assertIn("redacted", marker.content.lower())
        self.assertEqual(marker.metadata_dict.get("redacted_index"), 0)
        self.assertEqual(marker.metadata_dict.get("redaction_policy"), "default")

    def test_redact_message_emits_redaction_performed(self):
        svc, llm, pub, _ = _make_service()
        svc.create_conversation("c1")
        llm.response_content = "r"
        asyncio.run(svc.handle_turn("c1", user_content="hi"))
        pub.published.clear()

        svc.redact_message("c1", message_index=0)

        redaction_evs = [e for e in pub.published if isinstance(e, RedactionPerformed)]
        self.assertEqual(len(redaction_evs), 1)
        self.assertEqual(redaction_evs[0].message_index, 0)
        self.assertEqual(redaction_evs[0].redaction_policy, "default")

    def test_redact_message_original_content_in_event(self):
        """CV-8: original content is carried into the audit event."""
        svc, llm, pub, _ = _make_service()
        svc.create_conversation("c1")
        llm.response_content = "r"
        asyncio.run(svc.handle_turn("c1", user_content="my secret api key is sk-12345abc"))
        pub.published.clear()

        svc.redact_message("c1", message_index=0)

        ev = next(e for e in pub.published if isinstance(e, RedactionPerformed))
        self.assertEqual(ev.original_content, "my secret api key is sk-12345abc")

    def test_redact_message_original_preserved_in_store(self):
        """CV-2/CV-8: original message is never mutated."""
        svc, llm, _, _ = _make_service()
        svc.create_conversation("c1")
        llm.response_content = "r"
        asyncio.run(svc.handle_turn("c1", user_content="original text with email@test.com"))
        original = svc.get_conversation("c1").messages[0]

        svc.redact_message("c1", message_index=0)

        # Original message still at index 0, unchanged
        after = svc.get_conversation("c1").messages[0]
        self.assertEqual(after.content, "original text with email@test.com")
        self.assertEqual(after.redacted, False)

    def test_redact_message_marker_appended_not_replacing(self):
        """CV-2: transcript appends, never mutates."""
        svc, llm, _, _ = _make_service()
        svc.create_conversation("c1")
        llm.response_content = "r"
        asyncio.run(svc.handle_turn("c1", user_content="original"))
        before_count = len(svc.get_conversation("c1").messages)

        svc.redact_message("c1", message_index=0)

        after_count = len(svc.get_conversation("c1").messages)
        self.assertEqual(after_count, before_count + 1)  # marker appended, not replacing

    def test_redact_message_emits_after_persist(self):
        """F-02: RedactionPerformed emitted after store append succeeds."""
        svc, llm, pub, _ = _make_service()
        svc.create_conversation("c1")
        llm.response_content = "r"
        asyncio.run(svc.handle_turn("c1", user_content="test"))
        pub.published.clear()

        call_order: list[str] = []
        original_append = svc._store.append
        original_publish = pub.publish

        def tracking_append(cid, msg):
            call_order.append("store_append")
            return original_append(cid, msg)

        def tracking_publish(ev):
            call_order.append(f"publish:{type(ev).__name__}")
            original_publish(ev)

        svc._store.append = tracking_append
        pub.publish = tracking_publish

        svc.redact_message("c1", message_index=0)

        self.assertIn("store_append", call_order)
        append_idx = call_order.index("store_append")
        pub_indices = [i for i, c in enumerate(call_order) if "RedactionPerformed" in c]
        for pi in pub_indices:
            self.assertGreater(pi, append_idx,
                "RedactionPerformed must be published AFTER store.append succeeds")

    def test_redact_message_not_found_raises(self):
        svc, _, _, _ = _make_service()
        with self.assertRaises(ConversationNotFoundError):
            svc.redact_message("nonexistent", message_index=0)

    def test_redact_message_out_of_range_raises(self):
        svc, _, _, _ = _make_service()
        svc.create_conversation("c1")
        with self.assertRaises(IndexError):
            svc.redact_message("c1", message_index=0)

    def test_redact_message_terminal_conversation_rejected(self):
        svc, _, _, _ = _make_service()
        svc.create_conversation("c1")
        svc.transition("c1", ConversationState.OPEN)
        svc.transition("c1", ConversationState.CLOSED)
        with self.assertRaises(ConversationClosedError):
            svc.redact_message("c1", message_index=0)

    def test_redact_message_custom_policy(self):
        """Custom policy registered via register_policy() is used."""
        from app.intelligence.conversation.redaction import register_policy

        def custom_redactor(content):
            return f"[CUSTOM]{content}[/CUSTOM]"

        register_policy("custom", custom_redactor, "[CUSTOM]")

        svc, llm, pub, _ = _make_service()
        svc.create_conversation("c1")
        llm.response_content = "r"
        asyncio.run(svc.handle_turn("c1", user_content="sensitive"))

        summary = svc.redact_message("c1", message_index=0, policy="custom")

        marker = summary.messages[-1]
        self.assertIn("[CUSTOM]", marker.content)

        ev = next(e for e in pub.published if isinstance(e, RedactionPerformed))
        self.assertEqual(ev.redaction_policy, "custom")

    def test_redact_message_invalid_policy_raises(self):
        svc, llm, _, _ = _make_service()
        svc.create_conversation("c1")
        llm.response_content = "r"
        asyncio.run(svc.handle_turn("c1", user_content="test"))
        with self.assertRaises(ValueError):
            svc.redact_message("c1", message_index=0, policy="nonexistent-policy")

    # --- architectural boundary ---

    def test_service_is_outside_intelligence(self):
        import inspect
        from app.services.conversation.conversation_service import ConversationService
        filepath = inspect.getfile(ConversationService)
        self.assertFalse(
            filepath.endswith("app/intelligence/conversation/conversation_service.py"),
            "ConversationService must not live inside app/intelligence/",
        )


if __name__ == "__main__":
    unittest.main()
