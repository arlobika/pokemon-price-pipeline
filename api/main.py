from fastapi import FastAPI
from pydantic import BaseModel
from db import get_conn
from analytics import top_spreads

app = FastAPI()

class SpreadRow(BaseModel):
    card_id: str
    variant: str
    tcg_price: float
    tcg_currency: str
    cm_price: float
    cm_currency: str
    tcg_cad: float
    cm_cad: float
    cheaper_market: str
    spread_pct: float

@app.get("/spread", response_model=list[SpreadRow])
def get_spread(limit: int = 20):
    with get_conn() as conn, conn.cursor() as cur:
        return top_spreads(cur, limit=limit)