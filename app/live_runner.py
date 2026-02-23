import time
import datetime
import pytz

from app.groww_client import fetch_candles, generate_day_window
from app.database import save_signal
from app.engine_registry import active_engines, engine_status


def start_live(symbol, engine):

    print(f"🚀 Live engine started for {symbol}")

    last_processed_timestamp = None

    ist = pytz.timezone("Asia/Kolkata")

    while True:

        try:
            # ==========================
            # STOP IF ENGINE DELETED
            # ==========================
            if symbol not in active_engines:
                print(f"🛑 Engine removed for {symbol}. Stopping live loop.")
                break

            # ==========================
            # PAUSE SUPPORT
            # ==========================
            if engine_status.get(symbol) == "paused":
                time.sleep(5)
                continue

            # ==========================
            # MARKET HOURS CHECK (9-16 IST)
            # ==========================
            now = datetime.datetime.now(ist)

            if now.hour < 9 or now.hour >= 16:
                time.sleep(30)
                continue

            # ==========================
            # FETCH TODAY DATA
            # ==========================
            start_ms, end_ms = generate_day_window()

            candles = None
            attempts = 0

            while attempts < 3:
                try:
                    candles = fetch_candles(symbol, 1, start_ms, end_ms)
                    if candles:
                        break
                except Exception as e:
                    print(f"⚠ Live fetch attempt {attempts+1} failed:", e)

                attempts += 1
                time.sleep(1)

            if not candles:
                time.sleep(30)
                continue

            latest = candles[-1]

            # ==========================
            # PREVENT DUPLICATE CANDLE PROCESSING
            # ==========================
            if last_processed_timestamp == latest[0]:
                time.sleep(10)
                continue

            last_processed_timestamp = latest[0]

            # ==========================
            # UPDATE WAVETREND ENGINE
            # ==========================
            signal = engine.update(latest)

            if signal:
                save_signal({
                    "symbol": symbol,
                    "type": signal["type"],
                    "count": signal["count"],
                    "price": signal["price"],
                    "timestamp": signal["timestamp"]
                })

                print(f"📢 New {signal['type']} signal for {symbol}")

            # ==========================
            # WAIT FOR NEXT MINUTE
            # ==========================
            time.sleep(60)

        except Exception as e:
            print(f"❌ Live engine error for {symbol}:", e)
            time.sleep(5)