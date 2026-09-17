-- Migration 0003: Create conversations table for Phase 5 Conversation Context.
--
-- Schema design:
--   conversation_id  TEXT PRIMARY KEY
--   current_state   TEXT NOT NULL  (ConversationState enum value)
--   messages        JSONB NOT NULL DEFAULT '[]'  (ordered list of Message objects)
--   state_history   JSONB NOT NULL DEFAULT '[]'  (list of {state, at} transitions)
--   created_at      TIMESTAMPTZ NOT NULL
--   updated_at      TIMESTAMPTZ NOT NULL
--
-- JSONB is used for messages and state_history to enable:
--   - Append-only event replay (CV-3) without a separate event table
--   - Flexible Message schema evolution
--   - Efficient JSONB operators for future queries (e.g. message count, search)

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id  TEXT        PRIMARY KEY,
    current_state   TEXT        NOT NULL,
    messages        JSONB       NOT NULL DEFAULT '[]',
    state_history   JSONB       NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL
);
