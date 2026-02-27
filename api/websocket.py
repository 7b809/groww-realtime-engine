from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import logging
import os
import sys
import json,time

from services.symbol_service import build_symbol
from services.groww_fetcher import fetch_last_30_days
from services.index_fetcher import fetch_index_data
from wavetrend_processor import process_wavetrend
from services.live_feed_manager import LiveFeedManager
from dhanhq import marketfeed

# 🔥 Ensure Windows console supports UTF-8
sys.stdout.reconfigure(encoding="utf-8")

PRINT_LOGS = True

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

symbol_loggers = {}
active_sessions = {}

# 🔥 Load Dhan token once
with open("dhan_token.json", "r") as f:
    dhan_token = json.load(f)

live_manager = LiveFeedManager(
    dhan_token["dhanClientId"],
    dhan_token["accessToken"]
)


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
        # OPTION MODE
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

            # 🔥 Require security_id from frontend
            security_id = config.get("security_id")

            instruments = [
                (marketfeed.NSE_FNO, str(security_id), marketfeed.Full)
            ]

            if mode == "option":
                live_manager.subscribe(marketfeed.NSE_FNO, security_id)
            else:
                live_manager.subscribe(marketfeed.NSE, security_id)
                
    
        # =========================================
        # INDEX MODE
        # =========================================
        elif mode == "index":

            index_name = config["index_name"].upper()

            candles, _, symbol, exchange = await fetch_index_data(index_name)

            logger = get_symbol_logger(symbol)
            log(logger, "🎯 Built index symbol:", symbol)

            security_id = config.get("security_id")

            instruments = [
                (marketfeed.NSE, str(security_id), marketfeed.Full)
            ]

            # live_manager.start(instruments)
            # live_manager.register_symbol(security_id)

        else:
            await websocket.send_json({"error": "Invalid mode"})
            return

        # =========================================
        # PROCESS HISTORY (UNCHANGED)
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
        # 🔥 NEW LIVE LOOP (Dhan Realtime)
        # =========================================
        while True:

            await asyncio.sleep(1)

            sec_id, closed_candle = live_manager.process_tick()

            if not closed_candle:
                continue

            log(logger, "🕯 Live candle closed:", closed_candle)

            session = active_sessions[symbol]

            # Convert to existing candle format
            session["candles"].append([
                int(time.time() * 1000),
                closed_candle["open"],
                closed_candle["high"],
                closed_candle["low"],
                closed_candle["close"],
                closed_candle["volume"]
            ])

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

            if latest_signal["count"] == last_sent_count:
                continue

            last_sent_count = latest_signal["count"]

            log(
                logger,
                "🚀 NEW SIGNAL:",
                latest_signal["type"],
                "| Count:",
                latest_signal["count"]
            )

            await websocket.send_json({
                "type": "live_update",
                "symbol": symbol,
                "signal": latest_signal,
                "latest_candle": [
                    int(time.time()),   # seconds
                    closed_candle["open"],
                    closed_candle["high"],
                    closed_candle["low"],
                    closed_candle["close"],
                    closed_candle["volume"]
                ]
            })            

    except WebSocketDisconnect:

        log(temp_logger, "❌ WebSocket disconnected")

        if 'symbol' in locals() and symbol in active_sessions:
            del active_sessions[symbol]

    except Exception as e:
        log(temp_logger, "🔥 Unexpected Error:", str(e))