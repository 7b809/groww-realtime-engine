from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse

from app.expiry_utils import get_next_expiries
from app.symbol_builder import build_symbol
from app.live_runner import start_live
from app.wavetrend_engine import WaveTrendEngine
from app.groww_client import fetch_history_in_batches
from app.database import signals_col
from app.engine_registry import active_engines, engine_status

import datetime
import pytz
import time

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# # ==========================
# # GLOBAL ENGINE STORAGE
# # ==========================
# active_engines = {}     # symbol -> WaveTrendEngine
# engine_status = {}      # symbol -> running/paused


# ==========================
# HOME PAGE
# ==========================
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    expiries = get_next_expiries("NIFTY")
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "expiries": expiries}
    )


# ==========================
# START ENGINE
# ==========================
@app.post("/start")
def start_engine(
    background_tasks: BackgroundTasks,
    index: str = Form(...),
    strike: str = Form(...),
    option_type: str = Form(...),
    expiry: str = Form(...)
):
    try:
        expiry_date = datetime.datetime.strptime(expiry, "%Y-%m-%d").date()
        symbol = build_symbol(index, expiry_date, strike, option_type)

        if symbol in active_engines:
            return JSONResponse({
                "status": "Already Running",
                "symbol": symbol
            })

        # ==========================
        # LOAD 1 MONTH HISTORY
        # ==========================
        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.datetime.now(ist)
        past = now - datetime.timedelta(days=30)

        start_ms = int(past.timestamp() * 1000)
        end_ms = int(now.timestamp() * 1000)

        candles = None
        attempts = 0

        while attempts < 3:
            try:
                candles = fetch_history_in_batches(
                    symbol,
                    1,
                    past,
                    now
                )
                if candles:
                    break
            except Exception as e:
                print(f"⚠ Fetch attempt {attempts+1} failed:", e)

            attempts += 1
            time.sleep(1)

        if not candles:
            return JSONResponse(
                {"error": "Failed to fetch history after 3 attempts"},
                status_code=500
            )

        # ==========================
        # INITIALIZE ENGINE
        # ==========================
        engine = WaveTrendEngine()
        engine.load_history(candles)

        # print("History candles loaded:", len(candles))
        # print(candles[-5:])

        # ==========================
        # CLEAR OLD SIGNALS (IMPORTANT)
        # ==========================
        signals_col.delete_many({"symbol": symbol})

        # ==========================
        # GENERATE HISTORICAL SIGNALS
        # ==========================
        engine.generate_historical_signals(
            symbol,
            lambda data: signals_col.insert_one(data)
        )

        print("Historical signals generated")

        # ==========================
        # REGISTER ENGINE
        # ==========================
        active_engines[symbol] = engine
        engine_status[symbol] = "running"

        print(f"Engine initialized for {symbol}")

        # ==========================
        # START LIVE POLLING
        # ==========================
        background_tasks.add_task(start_live, symbol, engine)

        return {"status": "Started", "symbol": symbol}

    except Exception as e:
        print("❌ Start engine error:", e)
        return JSONResponse(
            {"error": str(e)},
            status_code=500
        )


# ==========================
# PAUSE ENGINE
# ==========================
@app.post("/pause/{symbol}")
def pause_engine(symbol: str):
    try:
        if symbol in engine_status:
            engine_status[symbol] = "paused"
            return {"status": "paused"}

        return {"error": "symbol not found"}

    except Exception as e:
        return {"error": str(e)}


# ==========================
# DELETE ENGINE
# ==========================
@app.delete("/delete/{symbol}")
def delete_engine(symbol: str):
    try:
        if symbol in active_engines:

            del active_engines[symbol]
            del engine_status[symbol]

            signals_col.delete_many({"symbol": symbol})

            return {"status": "deleted"}

        return {"error": "not found"}

    except Exception as e:
        return {"error": str(e)}


# ==========================
# GET ENGINE STATUS
# ==========================
@app.get("/engines")
def get_engines():
    try:
        data = []

        for symbol in active_engines:

            total = signals_col.count_documents({"symbol": symbol})
            bull = signals_col.count_documents(
                {"symbol": symbol, "type": "bullish"}
            )
            bear = signals_col.count_documents(
                {"symbol": symbol, "type": "bearish"}
            )

            data.append({
                "symbol": symbol,
                "status": engine_status.get(symbol, "unknown"),
                "total": total,
                "bull": bull,
                "bear": bear
            })

        return data

    except Exception as e:
        return {"error": str(e)}