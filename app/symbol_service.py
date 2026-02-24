# app/symbol_service.py

import datetime
from app.database import symbol_col
from app.symbol_builder import build_symbol
from app.engine import WaveTrendEngine
from app.history_client import fetch_historic_signals


def initialize_symbol(index, expiry, strike, option_type):

    expiry_date = datetime.datetime.strptime(expiry, "%Y-%m-%d").date()

    symbol = build_symbol(index, expiry_date, strike, option_type)

    # ==========================
    # FETCH HISTORY FROM VERCEL API
    # ==========================
    history_data = fetch_historic_signals(
        index=index,
        year=str(expiry_date.year)[-2:],
        month=expiry_date.strftime("%b").upper(),
        expiry_day=f"{expiry_date.day:02d}",
        strike=strike,
        option_type=option_type
    )

    signals = history_data.get("signals", [])

    # ==========================
    # GET FINAL COUNTS
    # ==========================
    bull_count = 0
    bear_count = 0

    if signals:
        for s in signals:
            if s["type"] == "bullish":
                bull_count = max(bull_count, s["count"])
            elif s["type"] == "bearish":
                bear_count = max(bear_count, s["count"])

    # ==========================
    # INIT ENGINE WITH COUNTS
    # ==========================
    engine = WaveTrendEngine()
    engine.bull_count = bull_count
    engine.bear_count = bear_count

    # ==========================
    # STORE SINGLE DOCUMENT (FULL STRUCTURE)
    # ==========================
    doc = {
        "symbol": symbol,

        # 🔥 CONTRACT METADATA
        "index": index,
        "expiry": expiry,
        "strike": strike,
        "option_type": option_type,

        # 🔥 HISTORY BLOCK
        "history": {
            "total_candles": history_data.get("total_candles"),
            "total_signals": history_data.get("total_signals"),
            "candles": signals,  # Full historical candle data
            "loaded_at": datetime.datetime.utcnow()
        },

        # 🔥 SIGNAL STATE
        "signals": {
            "bull_count": bull_count,
            "bear_count": bear_count,
            "latest_signal": signals[-1] if signals else None
        },

        # 🔥 LIVE STATE
        "live": {
            "status": "running",
            "last_price": None,
            "last_timestamp": None
        }
    }

    symbol_col.replace_one({"symbol": symbol}, doc, upsert=True)

    return symbol, engine