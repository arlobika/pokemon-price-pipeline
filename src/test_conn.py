# test_conn.py
from db import get_conn

with get_conn() as c, c.cursor() as cur:
    cur.execute("select count(*) from cards")
    print(cur.fetchone())