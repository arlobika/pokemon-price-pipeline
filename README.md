# Pokemon Price Pipeline

A data-engineering pipeline that ingests Pokemon TCG card prices from two
independent markets, stores them as an append-only time series in Postgres,
and serves a cross-market spread analysis over them.

This is **not** a price predictor — collectible-price prediction isn't
reliably possible and doesn't hold up well under scrutiny. The point here is
the engineering: reliable ingestion, a defensible schema, and turning a data
source with no history into a growing time series.

## The headline feature

The same card is priced in two currencies by two independent markets —
**TCGplayer (USD)** and **Cardmarket (EUR)**. Both get converted to CAD at
query time, using the FX rate in effect on each price's own date, and the
biggest cross-market gaps get surfaced. Example: a base-set Charizard
recently showed a genuine 117% spread between the two markets once both
were converted to the same currency.

## Architecture

```
TCGdex API ──▶ ingest_prices.py ──▶ Postgres ◀── ingest_fx.py ◀── Frankfurter API
                (normalize both        │
                 provider shapes)      ▼
                                  analytics.py (spread query)
                                        │
                                        ▼
                                  FastAPI (api/main.py)
                                        │
                                        ▼
                                  static frontend (api/static/index.html)
```

- **`src/ingest_prices.py`** — pulls a set's cards from [TCGdex](https://tcgdex.dev)
  (free, no API key, embeds both TCGplayer and Cardmarket pricing per card),
  normalizes the two providers' very different response shapes into one
  common row format, and inserts idempotently.
- **`src/ingest_fx.py`** — pulls USD→CAD and EUR→CAD rates from the
  [Frankfurter API](https://frankfurter.dev) (ECB rates, no API key).
- **`src/analytics.py`** — the spread query: latest snapshot per card/variant,
  a self-join matching TCGplayer to Cardmarket on the same variant, FX
  conversion using each snapshot's own date, filtered to a meaningful CAD
  value so results are a real signal, not currency noise on 2-cent commons.
- **`api/main.py`** — FastAPI serving `/spread` and `/fx`, plus a small
  static frontend at `/`.

## Schema design

Three decisions worth knowing about (see `sql/schema.sql`):

1. **Append-only.** `price_snapshots` is never updated, only inserted into —
   history stays immutable.
2. **`captured_at` vs `source_updated_at`.** When *this pipeline* ran vs.
   when the source API says the price last changed — different things,
   both stored.
3. **Idempotent ingestion.** A `UNIQUE (card_id, source, variant,
   source_updated_at)` constraint plus `INSERT ... ON CONFLICT DO NOTHING`
   means re-running ingestion when the API hasn't refreshed doesn't create
   duplicate rows.

CAD is never stored directly — only USD and EUR as given, plus a
historical `fx_rates` table, so conversion always uses the rate that was
actually in effect on that date instead of corrupting history with today's
rate.

## Running it

```bash
# 1. Start Postgres (schema loads automatically on first init)
docker compose up -d

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env    # defaults already point at the docker-compose db

# 4. Ingest
cd src
python ingest_prices.py
python ingest_fx.py

# 5. Serve
cd ..
# PowerShell:
$env:PYTHONPATH = "src"; python -m uvicorn api.main:app --reload
# bash:
PYTHONPATH=src python -m uvicorn api.main:app --reload
```

Then open `http://127.0.0.1:8000/` for the frontend, or
`http://127.0.0.1:8000/docs` for the interactive API docs.

Which sets get ingested is controlled by `SETS` in `.env` (comma-separated
TCGdex set IDs, e.g. `base1,sv10.5b`).

## Stack

Python, httpx (raw REST calls, not the TCGdex SDK — the HTTP/parsing is
part of what this project is meant to demonstrate), PostgreSQL, psycopg
with plain SQL (no ORM), FastAPI.
