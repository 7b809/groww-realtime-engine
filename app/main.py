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
from app.history_client import fetch_historic_signals

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
        # FETCH HISTORY FROM VERCEL API
        # ==========================
        attempts = 0
        history_data = None

        while attempts < 3:
            try:
                history_data = fetch_historic_signals(
                    index=index,
                    year=str(expiry_date.year)[-2:],
                    month=expiry_date.strftime("%b").upper(),
                    strike=strike,
                    option_type=option_type
                )

                if history_data:
                    break

            except Exception as e:
                print(f"⚠ History API attempt {attempts+1} failed:", e)

            attempts += 1
            time.sleep(1)

        if not history_data:
            return JSONResponse(
                {"error": "Failed to fetch historic signals after 3 attempts"},
                status_code=500
            )

        # ==========================
        # CLEAR OLD SIGNALS
        # ==========================
        signals_col.delete_many({"symbol": symbol})

        # ==========================
        # INSERT HISTORICAL SIGNALS
        # ==========================
        for signal in history_data.get("signals", []):
            signals_col.insert_one(signal)

        print("Historical signals inserted:",
              history_data.get("total_signals", 0))

        # ==========================
        # INITIALIZE ENGINE FOR LIVE MODE
        # ==========================
        engine = WaveTrendEngine()

        # Optional: you can skip full history load
        # Or fetch only today's candles for base state
        engine.load_history([])

        active_engines[symbol] = engine
        engine_status[symbol] = "running"

        print(f"Engine initialized for {symbol}")

        # ==========================
        # START LIVE POLLING
        # ==========================
        background_tasks.add_task(start_live, symbol, engine)

        return {
            "status": "Started",
            "symbol": symbol,
            "historical_signals_loaded":
                history_data.get("total_signals", 0)
        }

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