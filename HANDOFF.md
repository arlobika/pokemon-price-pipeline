# Pokemon Price Pipeline — Project Handoff

Context doc for picking up this project in a new tool (e.g. Claude Code).
Read this first, then read the repo. The code is the source of truth for
*what exists*; this doc is the source of truth for *why*.

## What this is

A Pokemon TCG market-price **data pipeline**. It ingests card prices on a
schedule, stores them in Postgres, and serves analytics over them. It is a
data-engineering portfolio project meant to be defensible in interviews.

It is **not** a price predictor. Predicting collectible prices is not
reliably possible and invites skepticism in interviews. The value here is
the engineering: reliable ingestion, clean schema, and turning a source
that has no history into a growing time series that you built.

## Why TCGdex as the data source

- TCGplayer closed its own developer API to new applicants, so calling it
  directly is not an option.
- TCGdex is free, needs **no API key**, and embeds pricing from **both**
  TCGplayer (USD) and Cardmarket (EUR) in each card response. Two markets
  in one record is what makes the cross-market feature possible.
- Base URL: `https://api.tcgdex.net/v2/en`
- Pricing is embedded in the full card object (`/cards/{id}`), not the
  lighter set/search briefs. So the flow is: get a set -> list card IDs ->
  fetch each full card -> read `pricing`.

## The headline feature

Cross-market spread: the same card is priced in USD (TCGplayer) and EUR
(Cardmarket). Convert both to CAD and surface the gap. This needs no
prediction and makes a concrete demo ("this card is X% cheaper in Europe
right now").

## CAD handling (important design choice)

Do not store CAD prices. Store USD and EUR as given, plus an `fx_rates`
table, and convert to CAD **at query time using the FX rate from the
snapshot's own date**. Converting with today's rate would corrupt history
whenever exchange rates move. Storing the rate used is the defensible move.
Free no-key FX option to try: the Frankfurter API (ECB rates), covers
USD/EUR/CAD.

## Schema (see sql/schema.sql)

- `cards` — dimension, one row per card (static metadata).
- `price_snapshots` — append-only fact table, the time series. One row per
  (card, source, variant, snapshot).
- `fx_rates` — FX rates by date, for CAD conversion.

Three design decisions to be able to explain:
1. **Append-only.** Never update a snapshot, always insert. History is
   immutable.
2. **`captured_at` vs `source_updated_at`.** When *your* job ran vs when the
   API says the price last changed. Different things, both stored.
3. **Idempotent ingestion.** `UNIQUE (card_id, source, variant,
   source_updated_at)` + `INSERT ... ON CONFLICT DO NOTHING`, so re-running
   when the API has not refreshed does not create duplicates.

## Provider shapes (the normalize() problem)

The two providers come back in *different shapes*. Normalizing them into one
uniform row is the core learning task.

- **TCGplayer**: nested per variant. `pricing.tcgplayer.{normal|reverse|holo}`
  each with `lowPrice/midPrice/highPrice/marketPrice/directLowPrice`.
  Unit USD. Timestamp at `pricing.tcgplayer.updated`.
- **Cardmarket**: flat. `pricing.cardmarket.{avg,low,trend,...}` with the
  holo variant in suffixed keys like `trend-holo`. Unit EUR. Timestamp at
  `pricing.cardmarket.updated`.

Canonical comparable chosen for the spread: TCGplayer `marketPrice` vs
Cardmarket `trend`, compared variant-to-variant where both exist.

Guards: either provider may be **absent** if the card is not listed there —
check for the key before reading. Store the raw pricing blob in the `raw`
JSONB column so no data is lost to modeling decisions.

## Stack

Python + httpx (raw REST, not the TCGdex SDK, on purpose — the HTTP/parsing
is the part worth being able to defend), PostgreSQL in Docker, psycopg with
plain SQL (no ORM in v1), FastAPI for the serving layer later.

## Build order and current status

1. [DONE] `docker-compose.yml`, `.env.example`, `sql/schema.sql`. Postgres
   up, three tables + index created on init.
2. [IN PROGRESS] `config.py`, `db.py`. Confirm Python connects
   (`select count(*) from cards` should return `(0,)`).
3. [NEXT — the first real code, to be written by hand] `ingest_prices.py`:
   fetch a small set, `normalize()` the two providers into snapshot rows,
   insert with ON CONFLICT DO NOTHING.
4. `ingest_fx.py` + `analytics.py`: pull USD->CAD and EUR->CAD rates, write
   the spread query joining snapshots to the FX rate on matching date.
5. `api/main.py`: FastAPI, one `/spread` endpoint returning biggest gaps.

Later layers (optional): GitHub Actions cron to run ingestion daily and
build history; deploy; an honest forecast measured against a naive baseline
once enough history exists.

## Guardrail on help

The point of this project is to be defensible in interviews, so the author
should write the parts that get asked about — especially `normalize()`, the
analytics query, and the API. Scaffolding and boilerplate are fair to hand
over; the core logic is not.

## v1 scope

One small card set, snapshotted once a day. Keep it small until the full
loop (ingest -> store -> serve) works end to end.
