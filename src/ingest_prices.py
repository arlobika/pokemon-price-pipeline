import time
import httpx
from config import SETS
from db import get_conn
from psycopg.types.json import Json

BASE = "https://api.tcgdex.net/v2/en"

def fetch_set(set_id: str) -> dict:
    r = httpx.get(f"{BASE}/sets/{set_id}", timeout=30)
    r.raise_for_status()
    return r.json()          # has 'cards': list of briefs with 'id'

def fetch_card(card_id: str) -> dict:
    r = httpx.get(f"{BASE}/cards/{card_id}", timeout=30)
    r.raise_for_status()
    return r.json()          # full card, 'pricing' present only if listed

def normalize(card: dict) -> list[dict]:
    # TODO: the real work.
    # p = card.get("pricing", {})
    # tcgplayer: p['tcgplayer'][variant]['marketPrice'], unit USD,
    #   variant in {normal, reverse, holo}, updated at p['tcgplayer']['updated']
    # cardmarket: FLAT. base -> p['cardmarket']['trend'],
    #   holo -> p['cardmarket']['trend-holo'], unit EUR,
    #   updated at p['cardmarket']['updated']
    # Guard: either provider key may be absent.
    # Emit one dict per (source, variant) you decide to keep.

    tcg_variant_map = {
        "normal": "normal",
        "reverse-holofoil": "reverse",
        "holofoil": "holofoil"
    }
    cardmarket_variant_map = {
        "trend": "normal",
        "trend-holo": "holofoil"
    }


    card_id = card["id"]
    pricing = card.get("pricing", {})
    tcg = pricing.get("tcgplayer", {})
    cardmarket = pricing.get("cardmarket", {})
    rows = []

    variants = card.get("variants", {})
    has_normal = variants.get("normal", False)
    has_reverse = variants.get("reverse", False)
    has_holo = variants.get("holo", False)


    if has_normal:
        cm_unsuffixed_variant = "normal"
    elif has_holo:
        cm_unsuffixed_variant = "holofoil"
    else:
        cm_unsuffixed_variant = None #nothing reliable to label it
    
    cm_suffixed_variant = "reverse" if has_reverse else None


    if tcg:
        updated = tcg.get("updated") 
        if updated:
            updated = updated.split("T")[0]  # truncate to date if present
        for tcg_key, canonical_variant in tcg_variant_map.items():
            variant_data = tcg.get(tcg_key) #dict or none
            if variant_data is None:
                continue

            price = variant_data.get("marketPrice")
            if price is None:
                continue


            rows.append({
                "card_id": card_id,
                "source": "tcgplayer",
                "variant": canonical_variant,
                "market_price": price,
                "currency": "USD",
                "source_updated_at": updated,
                "raw": variant_data
            })

    if cardmarket:

        updated = cardmarket.get("updated")
        if updated:
            updated = updated.split("T")[0]  # truncate to date if present
        for cardmarket_key, canonical_variant in [("trend", cm_unsuffixed_variant), ("trend-holo", cm_suffixed_variant)]:
            if canonical_variant is None:
                continue
            
            price = cardmarket.get(cardmarket_key)
            if price is None:
                continue

            rows.append({
                "card_id": card_id,
                "source": "cardmarket",
                "variant": canonical_variant,
                "market_price": price,
                "currency": "EUR",
                "source_updated_at": updated,
                "raw": cardmarket
            })
    return rows


def upsert_card(cur, card: dict):
    cur.execute(
        """
        INSERT INTO cards (card_id, name, set_id, set_name, number,rarity, image_url)
        VALUES (%(card_id)s, %(name)s, %(set_id)s, %(set_name)s, %(number)s, %(rarity)s, %(image_url)s)
        ON CONFLICT (card_id) DO NOTHING
        """,
        {
            "card_id": card["id"],
            "name": card["name"],
            "set_id": card["set"]["id"],
            "set_name": card["set"]["name"],
            "number": card["localId"],
            "rarity": card.get("rarity", ""),
            "image_url": card.get("image"),
        },
    )

def main() -> None:
    with get_conn() as conn, conn.cursor() as cur:
        for set_id in SETS:
            for brief in fetch_set(set_id)["cards"]:
                card = fetch_card(brief["id"])
                upsert_card(cur, card)
                for row in normalize(card):
                  # TODO: INSERT INTO price_snapshots ... ON CONFLICT DO NOTHING
                    cur.execute(
                        """
                        INSERT INTO price_snapshots (card_id, source, variant, market_price, currency, source_updated_at, raw)
                        VALUES (%(card_id)s, %(source)s, %(variant)s, %(market_price)s, %(currency)s, %(source_updated_at)s, %(raw)s)
                        ON CONFLICT (card_id, source, variant, source_updated_at) DO NOTHING
                        """,
                        {**row, "raw": Json(row["raw"])}
                    )
                    time.sleep(0.1)   # no key is not a license to hammer them
        conn.commit()

if __name__ == "__main__":
    main()