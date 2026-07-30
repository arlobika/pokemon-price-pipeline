
SPREAD_QUERY ="""
WITH latest AS (
    SELECT DISTINCT ON (card_id, source, variant)
        card_id, source, variant, market_price, currency, source_updated_at
    FROM price_snapshots
    WHERE market_price > 0
    ORDER BY card_id, source, variant, source_updated_at DESC
),
spread AS (
    SELECT
        t.card_id,
        t.variant,
        t.market_price AS tcg_price,
        t.currency AS tcg_currency,
        c.market_price AS cm_price,
        c.currency AS cm_currency,
        ROUND(t.market_price * fx_t.rate, 2) AS tcg_cad,
        ROUND(c.market_price * fx_c.rate, 2) AS cm_cad,
        CASE WHEN t.market_price * fx_t.rate < c.market_price * fx_c.rate
            THEN 'tcgplayer' ELSE 'cardmarket' END AS cheaper_market,
        ROUND(
            ABS(t.market_price * fx_t.rate - c.market_price * fx_c.rate)
            / LEAST(t.market_price * fx_t.rate, c.market_price * fx_c.rate) * 100,
            1
        ) AS spread_pct
    FROM latest t
    JOIN latest c
        ON t.card_id = c.card_id
        AND t.variant = c.variant
        AND t.source = 'tcgplayer'
        AND c.source = 'cardmarket'
    JOIN fx_rates fx_t
        ON fx_t.base_currency = t.currency
        AND fx_t.quote_currency = 'CAD'
        AND fx_t.rate_date = t.source_updated_at
    JOIN fx_rates fx_c
        ON fx_c.base_currency = c.currency
        AND fx_c.quote_currency = 'CAD'
        AND fx_c.rate_date = c.source_updated_at
)
SELECT * FROM spread
WHERE GREATEST(tcg_cad, cm_cad) > 5
ORDER BY spread_pct DESC

"""

def top_spreads(cur, limit: int = 20) -> list[dict]:
    cur.execute(SPREAD_QUERY + "LIMIT %s", (limit,))
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]