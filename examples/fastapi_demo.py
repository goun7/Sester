from fastapi import FastAPI

from sester.ledger import Ledger
from sester.middleware import SesterMeter

SECRET = "sester-fastapi-demo-secret"
PRICE = 0.05
DAILY_QUOTA = 0.25

ledger = Ledger(
    "sester-fastapi-demo.sqlite3",
    secret=SECRET,
)

app = FastAPI(
    title="Sester FastAPI example",
    description="Minimal FastAPI application protected by SesterMeter.",
)

app.add_middleware(
    SesterMeter,
    ledger=ledger,
    price=PRICE,
    daily_quota=DAILY_QUOTA,
    secret=SECRET,
)


@app.get("/weather")
def weather():
    return {
        "city": "istanbul",
        "temperature": 24,
    }
