import httpx
from db import get_conn


FX_BASE = "https://api.frankfurter.dev/v1"

def fetch_rate(base: str, quote:str) -> dict:
    r = httpx.get(f"{FX_BASE}/latest", params={"base": base, "symbols": quote}, timeout=15)
    r.raise_for_status()
    return r.json()          # {'amount':1.0, 'base':'USD', 'date':'2026-07-29', 'rates':{'CAD': 1.4105}}

def main() -> None:
    with get_conn() as conn, conn.cursor() as cur:
        for base in ("USD", "EUR"):
            data = fetch_rate(base, "CAD")
            cur.execute(
                """
                INSERT INTO fx_rates (base_currency, quote_currency, rate, rate_date)
                VALUES (%(base)s, %(quote)s, %(rate)s, %(rate_date)s)
                ON CONFLICT (base_currency, quote_currency, rate_date) DO NOTHING
                """,
                {
                    "base": data["base"],
                    "quote": "CAD",
                    "rate": data["rates"]["CAD"],
                    "rate_date": data["date"]
                },
            )

            conn.commit()

if __name__ == "__main__":
    main()