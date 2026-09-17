"""Tests for JSONL export and hash chain."""

import io
import unittest

from app.intelligence.conversation.export import GENESIS_HASH, HashChain, export_jsonl
from app.intelligence.conversation.message import Message
from app.intelligence.conversation.state import ConversationState
from app.intelligence.conversation.store import ConversationSummary


class TestHashChain(unittest.TestCase):

    def test_empty_chain_prev_hash_is_genesis(self):
        chain = HashChain()
        self.assertEqual(chain.prev_hash, GENESIS_HASH)

    def test_extend_returns_hashes(self):
        chain = HashChain()
        msgs = [
            Message(role="user", content="hello"),
            Message(role="assistant", content="hi"),
        ]
        hashes = chain.extend(msgs)
        self.assertEqual(len(hashes), 2)
        self.assertIsInstance(hashes[0], str)

    def test_extend_updates_prev_hash(self):
        chain = HashChain()
        msg = Message(role="user", content="hello")
        chain.extend([msg])
        self.assertNotEqual(chain.prev_hash, GENESIS_HASH)
        self.assertEqual(chain.prev_hash, chain.line_hashes[0])

    def test_verify_returns_true_for_valid_chain(self):
        chain = HashChain()
        msgs = [
            Message(role="user", content="hello"),
            Message(role="assistant", content="hi"),
        ]
        hashes = chain.extend(msgs)
        chain2 = HashChain()
        self.assertTrue(chain2.verify(msgs, hashes))

    def test_verify_returns_false_for_tampered_content(self):
        chain = HashChain()
        msgs = [Message(role="user", content="hello")]
        hashes = chain.extend(msgs)
        tampered = [Message(role="user", content="tampered!")]
        chain2 = HashChain()
        self.assertFalse(chain2.verify(tampered, hashes))

    def test_verify_returns_false_for_wrong_hash_count(self):
        chain = HashChain()
        msgs = [Message(role="user", content="hello")]
        hashes = chain.extend(msgs)
        chain2 = HashChain()
        self.assertFalse(chain2.verify(msgs, hashes + ["bad"]))


class TestExportJsonl(unittest.TestCase):

    def _make_summary(self, messages, state=ConversationState.OPEN):
        return ConversationSummary(
            conversation_id="c1",
            state=state,
            messages=messages,
            created_at=messages[0].timestamp if messages else None,
            updated_at=messages[-1].timestamp if messages else None,
        )

    def test_export_empty_conversation(self):
        summary = ConversationSummary(
            conversation_id="c1",
            state=ConversationState.CREATED,
            messages=(),
            created_at=None,
            updated_at=None,
        )
        out = io.StringIO()
        chain = export_jsonl(summary, out, sign=True)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(len(chain.line_hashes), 0)

    def test_export_single_message(self):
        msg = Message(role="user", content="Hello world")
        summary = self._make_summary([msg])
        out = io.StringIO()
        chain = export_jsonl(summary, out, sign=True)
        lines = out.getvalue().strip().split("\n")
        self.assertEqual(len(lines), 1)
        import json
        record = json.loads(lines[0])
        self.assertEqual(record["role"], "user")
        self.assertEqual(record["content"], "Hello world")
        self.assertEqual(record["index"], 0)
        self.assertIn("hash", record)
        self.assertIn("timestamp", record)

    def test_export_without_signing(self):
        msg = Message(role="user", content="Hello")
        summary = self._make_summary([msg])
        out = io.StringIO()
        chain = export_jsonl(summary, out, sign=False)
        import json
        record = json.loads(out.getvalue().strip())
        self.assertNotIn("hash", record)

    def test_export_multiple_messages(self):
        msgs = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there"),
        ]
        summary = self._make_summary(msgs)
        out = io.StringIO()
        chain = export_jsonl(summary, out, sign=True)
        import json
        lines = [json.loads(l) for l in out.getvalue().strip().split("\n")]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["role"], "user")
        self.assertEqual(lines[1]["role"], "assistant")
        self.assertEqual(lines[0]["index"], 0)
        self.assertEqual(lines[1]["index"], 1)

    def test_export_hash_chain_is_verifiable(self):
        msgs = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi there"),
        ]
        summary = self._make_summary(msgs)
        out1 = io.StringIO()
        chain1 = export_jsonl(summary, out1, sign=True)
        import json
        lines1 = [json.loads(l)["hash"] for l in out1.getvalue().strip().split("\n")]
        # Verify the exported hashes
        from app.intelligence.conversation.export import HashChain
        verifier = HashChain()
        self.assertTrue(verifier.verify(msgs, lines1))


if __name__ == "__main__":
    unittest.main()
