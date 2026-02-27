from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import logging
import os
import sys

from services.symbol_service import build_symbol
from services.groww_fetcher import fetch_last_30_days, fetch_latest_candle
from wavetrend_processor import process_wavetrend

# 🔥 Ensure Windows console supports UTF-8 (safe)
sys.stdout.reconfigure(encoding="utf-8")

# 🔥 Enable / Disable console logs here
PRINT_LOGS = True

# ==============================
# LOGGING SETUP
# ==============================

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

symbol_loggers = {}  # symbol -> logger


def get_symbol_logger(symbol: str):
    if symbol in symbol_loggers:
        return symbol_loggers[symbol]

    logger = logging.getLogger(symbol)
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers
    if not logger.handlers:
        file_handler = logging.FileHandler(
            f"{LOG_DIR}/{symbol}.log",
            encoding="utf-8"  # 🔥 IMPORTANT FIX FOR WINDOWS
        )

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )

        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    symbol_loggers[symbol] = logger
    return logger


def log(logger, *args):
    message = " ".join(map(str, args))

    if PRINT_LOGS:
        print(message)

    if logger:
        logger.info(message)


# ==============================
# SESSION STORE
# ==============================

active_sessions = {}  # symbol -> session state


async def wavetrend_socket(websocket: WebSocket):
    await websocket.accept()

    # Temporary logger (before symbol known)
    temp_logger = logging.getLogger("global")
    log(temp_logger, "🔌 WebSocket accepted")

    try:
        # ==============================
        # RECEIVE INITIAL CONFIG
        # ==============================
        config = await websocket.receive_json()
        log(temp_logger, "📥 Received config:", config)

        symbol, exchange = build_symbol(
            index_name=config["index_name"],
            year=config.get("year"),
            month=config.get("month"),
            expiry_day=config.get("expiry_day"),
            strike=config.get("strike"),
            option_type=config.get("option_type"),
            hard_fetch=True
        )

        target = config.get("target")

        # Create symbol-specific logger
        logger = get_symbol_logger(symbol)

        log(logger, "🎯 Built symbol:", symbol)

        # ==============================
        # STEP 1: FETCH 30 DAY HISTORY
        # ==============================
        candles, _ = await fetch_last_30_days(symbol, exchange)
        log(logger, f"📊 Fetched {len(candles)} candles")

        signals = process_wavetrend(
            symbol,
            candles,
            reverse_trade=False,
            target=target
        )

        log(logger, f"📈 Computed {len(signals)} historical signals")

        # Store session state
        active_sessions[symbol] = {
            "candles": candles,
            "last_timestamp": candles[-1][0] if candles else None,
            "last_signal_count": len(signals)
        }

        # Send full history first
        await websocket.send_json({
            "type": "history",
            "symbol": symbol,
            "total_signals": len(signals),
            "signals": signals
        })

        log(logger, "✅ History sent to client")

        # ==============================
        # STEP 2: LIVE LOOP
        # ==============================
        while True:

            await asyncio.sleep(2)

            latest = await fetch_latest_candle(symbol, exchange)

            if not latest:
                log(logger, "⏳ No latest candle yet")
                continue

            log(logger, "🕒 Latest candle:", latest)

            latest_timestamp = latest[0]
            session = active_sessions[symbol]

            # Skip if no new candle
            if latest_timestamp == session["last_timestamp"]:
                log(logger, "⛔ Same timestamp, skipping")
                continue

            log(logger, "🆕 New candle detected")

            # Append new candle
            session["candles"].append(latest)
            session["last_timestamp"] = latest_timestamp

            # Optional: memory safety
            session["candles"] = session["candles"][-2000:]

            # Recalculate WaveTrend
            new_signals = process_wavetrend(
                symbol,
                session["candles"],
                reverse_trade=False,
                target=target
            )

            log(logger, "🔁 Recalculated signals:", len(new_signals))

            if not new_signals:
                log(logger, "⚠️ No signals returned")
                continue

            latest_signal = new_signals[-1]
            session["last_signal_count"] = len(new_signals)

            res_obj = {
                "type": "live_update",
                "symbol": symbol,
                "latest_candle": latest,
                "signal": latest_signal
            }

            log(logger, "📤 Sending live_update:", res_obj)

            await websocket.send_json(res_obj)

    except WebSocketDisconnect:
        log(logger if 'logger' in locals() else temp_logger,
            "❌ WebSocket disconnected")

        if 'symbol' in locals() and symbol in active_sessions:
            del active_sessions[symbol]
            log(logger, "🧹 Session cleared for:", symbol)

        # Clean logger handlers
        if 'symbol' in locals() and symbol in symbol_loggers:
            logger_obj = symbol_loggers[symbol]
            handlers = logger_obj.handlers[:]
            for handler in handlers:
                handler.close()
                logger_obj.removeHandler(handler)

            del symbol_loggers[symbol]

    except Exception as e:
        log(logger if 'logger' in locals() else temp_logger,
            "🔥 Unexpected Error:", str(e))