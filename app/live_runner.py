import time,os
from datetime import datetime
from app.registry import active_engines, engine_status
from app.groww_client import fetch_candles, generate_today_window
from app.database import symbol_col

# ==========================
# CONFIG FLAGS
# ==========================
PRINT_LOGS = os.getenv("PRINT_LOGS", "False").lower() == "True"  # 🔥 Turn logs ON/OFF here
POLL_INTERVAL = 3       # seconds (instead of hardcoded 60)

def log(message):
    if PRINT_LOGS:
        print(message)


def start_live(symbol):

    engine = active_engines[symbol]
    last_ts = None

    log(f"[LIVE] Started engine for {symbol}")

    while True:

        if symbol not in active_engines:
            log(f"[LIVE] Engine removed for {symbol}")
            break

        if engine_status[symbol] == "paused":
            log(f"[LIVE] Engine paused for {symbol}")
            time.sleep(5)
            continue

        start_ms, end_ms = generate_today_window()

        log(f"[LIVE] Fetching candles for {symbol}")

        candles = fetch_candles(symbol, 1, start_ms, end_ms)

        if not candles:
            log(f"[LIVE] No candles received")
            time.sleep(POLL_INTERVAL)
            continue

        latest = candles[-1]

        if last_ts == latest[0]:
            log(f"[LIVE] No new candle")
            time.sleep(POLL_INTERVAL)
            continue

        last_ts = latest[0]

        log(
            f"[LIVE] New Candle → "
            f"Time: {datetime.fromtimestamp(latest[0])} | "
            f"Close: {latest[4]}"
        )

        signal = engine.update(latest)

        if signal:

            log(
                f"[SIGNAL] {signal['type'].upper()} "
                f"#{signal['count']} @ {signal['price']}"
            )

            symbol_col.update_one(
                {"symbol": symbol},
                {
                    "$set": {
                        "signals.latest_signal": signal,
                        "live.last_price": signal["price"],
                        "live.last_timestamp": signal["timestamp"]
                    },
                    "$inc": {
                        f"signals.{signal['type']}_count": 1
                    }
                }
            )

        time.sleep(POLL_INTERVAL)