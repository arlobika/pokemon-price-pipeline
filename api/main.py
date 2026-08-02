import os
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from pydantic import BaseModel
from db import get_conn
from analytics import current_fx_rates, top_spreads
from datetime import date
app = FastAPI()

class SpreadRow(BaseModel):
    card_id: str
    name: str
    image_url: str
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

class FXRate(BaseModel):
    base_currency: str
    quote_currency: str
    rate: float
    rate_date: date

@app.get("/fx", response_model=list[FXRate])
def get_fx():
    with get_conn() as conn, conn.cursor() as cur:
        return current_fx_rates(cur)

app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")

