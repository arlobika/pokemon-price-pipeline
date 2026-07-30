-- dimension: one row per card, mostly static
CREATE TABLE IF NOT EXISTS cards (
    card_id        TEXT PRIMARY KEY,          -- pokemontcg.io id, e.g. 'base1-4'
    name           TEXT NOT NULL,
    set_id         TEXT NOT NULL,
    set_name       TEXT,
    number         TEXT,
    rarity         TEXT,
    image_url      TEXT,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- fact: append-only price time series, the heart of the project
CREATE TABLE IF NOT EXISTS price_snapshots (
    id                 BIGSERIAL PRIMARY KEY,
    card_id            TEXT NOT NULL REFERENCES cards(card_id),
    source             TEXT NOT NULL,         -- 'tcgplayer' | 'cardmarket'
    variant            TEXT NOT NULL,         -- 'normal', 'holofoil', 'reverseHolofoil'
    currency           TEXT NOT NULL,         -- 'USD' | 'EUR'
    market_price       NUMERIC(12,2),
    source_updated_at  DATE,                  -- freshness the API reports
    captured_at        TIMESTAMPTZ NOT NULL DEFAULT now(),  -- when YOUR job ran
    raw                JSONB,                 -- full price blob, cheap insurance
    UNIQUE (card_id, source, variant, source_updated_at)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_card_time
    ON price_snapshots (card_id, captured_at);

-- FX rates, so CAD (or any) conversion stays historically accurate
CREATE TABLE IF NOT EXISTS fx_rates (
    id              BIGSERIAL PRIMARY KEY,
    base_currency   TEXT NOT NULL,            -- 'USD' | 'EUR'
    quote_currency  TEXT NOT NULL,            -- 'CAD'
    rate            NUMERIC(12,6) NOT NULL,
    rate_date       DATE NOT NULL,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (base_currency, quote_currency, rate_date)
);