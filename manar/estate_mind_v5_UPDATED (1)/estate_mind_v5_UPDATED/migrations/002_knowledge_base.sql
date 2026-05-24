-- migrations/002_knowledge_base.sql
-- ══════════════════════════════════════════════════════════════
-- Estate Mind BO6 — Knowledge Base Schema
-- Sources : BO3 (prix / marché) + BO4 (investissement / ROI)
--
-- Exécuter dans Supabase SQL Editor APRÈS 001_schema.sql
-- ══════════════════════════════════════════════════════════════

CREATE SCHEMA IF NOT EXISTS bo6_knowledge;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── TABLE 1 : Cache générique inter-agents ────────────────────
-- Stocke les réponses FILTRÉES de tous les agents (BO3, BO4, BO1, BO2)
-- Jamais les données brutes — uniquement les insights extraits
CREATE TABLE IF NOT EXISTS bo6_knowledge.agent_cache (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    cache_key       VARCHAR(64) NOT NULL UNIQUE,
    source_agent    VARCHAR(8)  NOT NULL,           -- 'BO3' ou 'BO4'
    intent          VARCHAR(64) NOT NULL,            -- 'price_estimation', 'investment_analysis'...
    query_params    JSONB       NOT NULL,            -- paramètres anonymisés (budget en tranche)
    extracted_data  JSONB       NOT NULL,            -- données filtrées — JAMAIS brutes
    confidence      VARCHAR(32),
    hit_count       INTEGER     DEFAULT 1,           -- nb de fois ce cache a servi
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    CONSTRAINT chk_agent CHECK (source_agent IN ('BO1','BO2','BO3','BO4','BO5'))
);
CREATE INDEX IF NOT EXISTS idx_kb_cache_key    ON bo6_knowledge.agent_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_kb_cache_agent  ON bo6_knowledge.agent_cache(source_agent, intent);
CREATE INDEX IF NOT EXISTS idx_kb_cache_expiry ON bo6_knowledge.agent_cache(expires_at);

-- ── TABLE 2 : Tendances marché (BO3 + BO4 partagent cette table)
-- BO3 contribue : avg_price, trend_direction
-- BO4 contribue : avg_roi, projected growth
CREATE TABLE IF NOT EXISTS bo6_knowledge.market_trends (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    city            VARCHAR(64) NOT NULL,
    property_type   VARCHAR(32),                    -- S+1, S+2, villa...
    goal            VARCHAR(32),                    -- achat, location, revente
    avg_price       DOUBLE PRECISION,               -- BO3
    avg_roi         DOUBLE PRECISION,               -- BO4
    trend_direction VARCHAR(8),                     -- 'up' / 'down' / 'stable'
    trend_label     VARCHAR(128),
    source_agent    VARCHAR(8),
    recorded_at     TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,                    -- TTL 24h
    UNIQUE(city, property_type, goal, source_agent, DATE(recorded_at))
);
CREATE INDEX IF NOT EXISTS idx_kb_trends_city   ON bo6_knowledge.market_trends(city, goal);
CREATE INDEX IF NOT EXISTS idx_kb_trends_expiry ON bo6_knowledge.market_trends(expires_at);

-- ── TABLE 3 : Règles métier extraites (BO3 + BO4) ─────────────
-- Patterns stables : "ROI > 6% à Sousse = BUY", "Ariana +14% cette année"
-- TTL 7 jours — changent lentement
CREATE TABLE IF NOT EXISTS bo6_knowledge.business_rules (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    rule_key        VARCHAR(128) NOT NULL UNIQUE,
    source_agent    VARCHAR(8),
    rule_type       VARCHAR(64),
    -- ex: 'price_threshold', 'zone_preference', 'roi_benchmark', 'seasonal_pattern'
    description     TEXT        NOT NULL,
    conditions      JSONB,
    recommendation  TEXT,
    confidence      DOUBLE PRECISION,
    valid_until     TIMESTAMPTZ,                    -- TTL 7 jours
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── TABLE 4 : Patterns XAI de BO4 (résumés SHAP lisibles) ────
-- Jamais les valeurs SHAP brutes — uniquement les résumés textuels
-- Ex: "Pour un budget medium en revente : location_score est le facteur principal (42%)"
CREATE TABLE IF NOT EXISTS bo6_knowledge.xai_patterns (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    pattern_key     VARCHAR(128) NOT NULL UNIQUE,
    context         VARCHAR(64),            -- 'medium_risk_revente', 'low_budget_sousse'
    top_features    JSONB,                  -- [{"feature":"location_score","impact":0.42}]
    summary_text    TEXT,                   -- explication lisible pour templates BO6
    frequency       INTEGER     DEFAULT 1,
    last_seen       TIMESTAMPTZ DEFAULT NOW()
);

-- ── TABLE 5 : Zones recommandées (spécifique BO3) ─────────────
-- Permet à BO6 de suggérer des zones sans appeler BO3 si données fraîches
CREATE TABLE IF NOT EXISTS bo6_knowledge.recommended_zones (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    city            VARCHAR(64) NOT NULL,
    zone_name       VARCHAR(128) NOT NULL,
    property_type   VARCHAR(32),
    budget_range    VARCHAR(16),            -- 'low', 'medium', 'high'
    avg_price       DOUBLE PRECISION,
    advantages      TEXT[],
    score           DOUBLE PRECISION,
    source_agent    VARCHAR(8)  DEFAULT 'BO3',
    valid_until     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(city, zone_name, budget_range, property_type)
);

-- ── VUE : récupération rapide des données encore valides ──────
CREATE OR REPLACE VIEW bo6_knowledge.active_cache AS
SELECT
    id, cache_key, source_agent, intent,
    extracted_data, confidence, hit_count,
    created_at, expires_at
FROM bo6_knowledge.agent_cache
WHERE expires_at > NOW()
ORDER BY created_at DESC;

-- ── Fonction de nettoyage automatique (TTL) ───────────────────
CREATE OR REPLACE FUNCTION bo6_knowledge.cleanup_expired()
RETURNS void AS $$
BEGIN
    DELETE FROM bo6_knowledge.agent_cache    WHERE expires_at < NOW();
    DELETE FROM bo6_knowledge.market_trends  WHERE expires_at < NOW();
    DELETE FROM bo6_knowledge.business_rules WHERE valid_until < NOW();
    RAISE NOTICE 'bo6_knowledge: expired entries cleaned';
END;
$$ LANGUAGE plpgsql;

-- ── Commentaires sur les tables ───────────────────────────────
COMMENT ON TABLE bo6_knowledge.agent_cache IS
  'Cache KB central — insights filtrés de BO3/BO4. Jamais de données brutes.';
COMMENT ON TABLE bo6_knowledge.market_trends IS
  'Tendances marché agrégées — BO3 (prix) + BO4 (ROI). TTL 24h.';
COMMENT ON TABLE bo6_knowledge.business_rules IS
  'Règles métier stables extraites des patterns BO3/BO4. TTL 7j.';
COMMENT ON TABLE bo6_knowledge.xai_patterns IS
  'Résumés SHAP lisibles de BO4. Jamais les poids ML bruts.';
COMMENT ON TABLE bo6_knowledge.recommended_zones IS
  'Zones recommandées par BO3. Permet réponses sans appel agent.';
