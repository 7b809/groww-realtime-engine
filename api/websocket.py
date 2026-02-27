from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import logging
import os
import sys

from services.symbol_service import build_symbol
from services.groww_fetcher import fetch_last_30_days, fetch_latest_candle
from services.index_fetcher import fetch_index_data, fetch_latest_index_candle
from wavetrend_processor import process_wavetrend

# 🔥 Ensure Windows console supports UTF-8
sys.stdout.reconfigure(encoding="utf-8")

PRINT_LOGS = False

# ==============================
# LOGGING SETUP
# ==============================

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

symbol_loggers = {}
active_sessions = {}


def get_symbol_logger(symbol: str):
    if symbol in symbol_loggers:
        return symbol_loggers[symbol]

    logger = logging.getLogger(symbol)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        file_handler = logging.FileHandler(
            f"{LOG_DIR}/{symbol}.log",
            encoding="utf-8"
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
# MAIN WEBSOCKET
# ==============================

async def wavetrend_socket(websocket: WebSocket):

    await websocket.accept()
    temp_logger = logging.getLogger("global")
    log(temp_logger, "🔌 WebSocket accepted")

    try:
        config = await websocket.receive_json()
        log(temp_logger, "📥 Received config:", config)

        mode = config.get("mode", "option")
        target = config.get("target")

        # =========================================
        # OPTION MODE (UNCHANGED LOGIC)
        # =========================================
        if mode == "option":

            symbol, exchange = build_symbol(
                index_name=config["index_name"],
                year=config.get("year"),
                month=config.get("month"),
                expiry_day=config.get("expiry_day"),
                strike=config.get("strike"),
                option_type=config.get("option_type"),
                hard_fetch=True
            )

            logger = get_symbol_logger(symbol)
            log(logger, "🎯 Built option symbol:", symbol)

            candles, _ = await fetch_last_30_days(symbol, exchange)

        # =========================================
        # INDEX MODE (NEW)
        # =========================================
        elif mode == "index":

            index_name = config["index_name"].upper()

            candles, _, symbol, exchange = await fetch_index_data(index_name)

            logger = get_symbol_logger(symbol)
            log(logger, "🎯 Built index symbol:", symbol)

        else:
            await websocket.send_json({"error": "Invalid mode"})
            return

        # =========================================
        # PROCESS HISTORY
        # =========================================
        log(logger, f"📊 Fetched {len(candles)} candles")

        signals = process_wavetrend(
            symbol,
            candles,
            reverse_trade=False,
            target=target
        )

        active_sessions[symbol] = {
            "candles": candles,
            "last_timestamp": candles[-1][0] if candles else None
        }

        await websocket.send_json({
            "type": "history",
            "symbol": symbol,
            "total_signals": len(signals),
            "signals": signals
        })
        last_sent_count = signals[-1]["count"] if signals else None
        log(logger, "✅ History sent")

        # =========================================
        # LIVE LOOP
        # =========================================
        while True:

            await asyncio.sleep(2)

            if mode == "option":
                latest = await fetch_latest_candle(symbol, exchange)
            else:
                latest = await fetch_latest_index_candle(config["index_name"])

            if not latest:
                continue

            latest_timestamp = latest[0]
            session = active_sessions[symbol]

            if latest_timestamp == session["last_timestamp"]:
                continue

            session["candles"].append(latest)
            session["last_timestamp"] = latest_timestamp
            session["candles"] = session["candles"][-2000:]

            new_signals = process_wavetrend(
                symbol,
                session["candles"],
                reverse_trade=False,
                target=target
            )

            if not new_signals:
                continue

            latest_signal = new_signals[-1]

            # 🚀 SEND ONLY IF NEW COUNT
            if latest_signal["count"] == last_sent_count:
                continue

            last_sent_count = latest_signal["count"]

            res_obj = {
                "type": "live_update",
                "symbol": symbol,
                "latest_candle": latest,
                "signal": latest_signal
            }

            await websocket.send_json(res_obj)



    except WebSocketDisconnect:

        log(temp_logger, "❌ WebSocket disconnected")

        if 'symbol' in locals() and symbol in active_sessions:
            del active_sessions[symbol]

        if 'symbol' in locals() and symbol in symbol_loggers:
            logger_obj = symbol_loggers[symbol]
            handlers = logger_obj.handlers[:]
            for handler in handlers:
                handler.close()
                logger_obj.removeHandler(handler)
            del symbol_loggers[symbol]

    except Exception as e:
        log(temp_logger, "🔥 Unexpected Error:", str(e))