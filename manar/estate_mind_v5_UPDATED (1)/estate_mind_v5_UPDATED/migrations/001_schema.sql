-- migrations/001_schema.sql
-- Estate Mind BO6 — Tables de tracabilite uniquement
-- BO6 n'utilise QUE ces 3 tables (pas estate_mind_db)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Sessions utilisateur
CREATE TABLE IF NOT EXISTS chat_sessions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     VARCHAR(128),
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON chat_sessions(user_id);

-- Interactions (DSO3 — tracabilite complete)
CREATE TABLE IF NOT EXISTS chat_interactions (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id            UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    sequence_number       INTEGER DEFAULT 1,
    original_query        TEXT NOT NULL,
    detected_language     VARCHAR(10) DEFAULT 'unknown',
    translated_query      TEXT,
    detected_intent       VARCHAR(64),
    intent_confidence     DOUBLE PRECISION,
    intent_probabilities  JSONB,
    routed_to_agent       VARCHAR(64),
    agent_url             VARCHAR(256),
    agent_raw_response    JSONB,
    response_text         TEXT,
    explanation_json      JSONB,
    pipeline_steps_json   JSONB,
    confidence_score      DOUBLE PRECISION,
    report_generated      BOOLEAN DEFAULT FALSE,
    report_path           VARCHAR(512),
    processing_ms         INTEGER,
    error_message         TEXT,
    is_darija             BOOLEAN DEFAULT FALSE,
    darija_terms          JSONB,
    top_ngrams            JSONB,
    created_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_interactions_session ON chat_interactions(session_id);
CREATE INDEX IF NOT EXISTS idx_interactions_intent  ON chat_interactions(detected_intent);
CREATE INDEX IF NOT EXISTS idx_interactions_created ON chat_interactions(created_at DESC);

-- Rapports PDF (DSO2)
CREATE TABLE IF NOT EXISTS report_records (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    report_type     VARCHAR(64) NOT NULL,
    file_path       VARCHAR(512) NOT NULL,
    file_size_bytes INTEGER,
    parameters      JSONB,
    summary         TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reports_session ON report_records(session_id);
