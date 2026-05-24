-- ══════════════════════════════════════════════════════════════════
-- ESTATE MIND — Schéma Supabase
-- Coller dans Supabase → SQL Editor → Run
-- ══════════════════════════════════════════════════════════════════

-- ── Table 1 : listings ─────────────────────────────────────────────
-- Toutes les annonces nettoyées, scor?es et dédupliquées
-- Clé de déduplication : (url, source) — UNIQUE
CREATE TABLE IF NOT EXISTS listings (
    id               BIGSERIAL PRIMARY KEY,

    -- Identification unique de l'annonce
    url              TEXT        NOT NULL,
    source           TEXT        NOT NULL,   -- tayara | mubawab | tecnocasa | remax

    -- Champs principaux (extraits par NLP)
    title            TEXT,
    price            NUMERIC(12,2),
    surface          NUMERIC(8,2),
    rooms            SMALLINT,
    property_type    TEXT,                   -- appartement | villa | maison | terrain | ...
    city             TEXT,
    governorate      TEXT,
    description      TEXT,
    latitude         DOUBLE PRECISION,
    longitude        DOUBLE PRECISION,
    publication_date TIMESTAMPTZ,

    -- Champs calculés par le pipeline BO1
    price_per_m2     NUMERIC(10,2),          -- calculé : price / surface
    trust_score      NUMERIC(5,3),           -- [0-1] fiabilité de l'annonce
    trust_level      TEXT,                   -- Fiable | Moyen | Suspect
    legal_risk_score NUMERIC(5,3),           -- [0-1] risque légal (stub = 0.15)
    legal_risk_level TEXT,                   -- Faible | Moyen | Élevé

    -- Flags NLP (extraits des descriptions)
    has_title_deed   BOOLEAN DEFAULT FALSE,
    has_permit       BOOLEAN DEFAULT FALSE,
    nlp_enriched     BOOLEAN DEFAULT FALSE,

    -- Métadonnées pipeline
    ingested_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    pipeline_version TEXT,
    data_hash        TEXT,                   -- SHA-256 court pour détecter les changements

    -- Contrainte de déduplication atomique
    CONSTRAINT uq_listing UNIQUE (url, source)
);

-- Index pour les requêtes fréquentes du frontend
CREATE INDEX IF NOT EXISTS idx_listings_city           ON listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_governorate    ON listings(governorate);
CREATE INDEX IF NOT EXISTS idx_listings_property_type  ON listings(property_type);
CREATE INDEX IF NOT EXISTS idx_listings_trust_score    ON listings(trust_score DESC);
CREATE INDEX IF NOT EXISTS idx_listings_price          ON listings(price);
CREATE INDEX IF NOT EXISTS idx_listings_ingested_at    ON listings(ingested_at DESC);
CREATE INDEX IF NOT EXISTS idx_listings_source         ON listings(source);


-- ── Table 2 : price_history ────────────────────────────────────────
-- Chaque fois que le prix d'une annonce change, on le logge ici
-- C'est ce qui alimente PriceHistory.tsx avec des données RÉELLES
CREATE TABLE IF NOT EXISTS price_history (
    id          BIGSERIAL PRIMARY KEY,
    listing_url TEXT           NOT NULL,
    source      TEXT           NOT NULL,
    old_price   NUMERIC(12,2),
    new_price   NUMERIC(12,2),
    change_pct  NUMERIC(7,2),             -- variation en %
    changed_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_price_history_url ON price_history(listing_url, source);
CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history(changed_at DESC);


-- ── Table 3 : pipeline_runs ────────────────────────────────────────
-- Trace chaque exécution du pipeline (remplace MLflow pour les runs)
-- Permet de voir l'historique des runs, les métriques, les erreurs
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id               BIGSERIAL PRIMARY KEY,
    run_id           TEXT UNIQUE NOT NULL,
    started_at       TIMESTAMPTZ DEFAULT NOW(),
    finished_at      TIMESTAMPTZ,
    status           TEXT DEFAULT 'running',  -- running | success | failed
    rows_in          INTEGER,                 -- annonces brutes en entrée
    rows_out         INTEGER,                 -- annonces après nettoyage
    rows_inserted    INTEGER DEFAULT 0,       -- nouvelles annonces
    rows_updated     INTEGER DEFAULT 0,       -- annonces mises à jour
    rows_skipped     INTEGER DEFAULT 0,       -- inchangées (ignorées)
    avg_trust_score  NUMERIC(5,3),
    suspect_count    INTEGER,
    sources_used     TEXT[],                  -- liste des sources utilisées
    config           JSONB,                   -- hyperparamètres du run
    error_message    TEXT
);


-- ── Table 4 : portfolios ───────────────────────────────────────────
-- Favoris des utilisateurs (remplace _portfolios: dict en RAM)
-- Persistant entre redémarrages du serveur
CREATE TABLE IF NOT EXISTS portfolios (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT           NOT NULL,      -- identifiant utilisateur (session ou email)
    listing_url TEXT           NOT NULL,
    source      TEXT           NOT NULL,

    -- Snapshot au moment de la sauvegarde
    saved_price NUMERIC(12,2),
    title       TEXT,
    city        TEXT,
    property_type TEXT,
    surface     NUMERIC(8,2),
    trust_score NUMERIC(5,3),

    saved_at    TIMESTAMPTZ DEFAULT NOW(),

    -- Un utilisateur ne peut pas sauvegarder la même annonce deux fois
    CONSTRAINT uq_portfolio UNIQUE (user_id, listing_url, source)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_user ON portfolios(user_id);


-- ── Table 5 : alert_subscriptions ─────────────────────────────────
-- Abonnements aux alertes territoriales par email / webhook
-- Remplace SubscriptionStore (fichier JSON local)
CREATE TABLE IF NOT EXISTS alert_subscriptions (
    id              BIGSERIAL PRIMARY KEY,
    sub_id          TEXT UNIQUE NOT NULL,     -- identifiant court (hex 8 chars)
    email           TEXT        NOT NULL,
    name            TEXT,

    -- Critères de l'alerte
    watch_zones     TEXT[],                   -- gouvernorats surveillés
    watch_cities    TEXT[],                   -- villes surveillées
    budget_max      NUMERIC(12,2),
    surface_min     NUMERIC(8,2),
    property_types  TEXT[],
    trust_min       NUMERIC(5,3) DEFAULT 0.70,
    price_threshold NUMERIC(5,3) DEFAULT 0.08,

    webhook_url     TEXT,
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_email  ON alert_subscriptions(email);
CREATE INDEX IF NOT EXISTS idx_subscriptions_active ON alert_subscriptions(active);


-- ══════════════════════════════════════════════════════════════════
-- Vérification : liste les tables créées
-- ══════════════════════════════════════════════════════════════════
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
