from fastapi import FastAPI, BackgroundTasks
from app.symbol_service import initialize_symbol
from app.registry import active_engines, engine_status
from app.live_runner import start_live
from app.database import symbol_col

import threading

app = FastAPI()

# =====================================================
# 🔁 AUTO RESUME ENGINES ON STARTUP
# =====================================================
@app.on_event("startup")
def auto_resume_engines():

    print("🔄 Checking saved symbols for auto-resume...")

    saved_symbols = list(symbol_col.find({}))

    if not saved_symbols:
        print("✅ No saved symbols found.")
        return

    for doc in saved_symbols:

        try:
            symbol = doc.get("symbol")
            index = doc.get("index")
            expiry = doc.get("expiry")
            strike = doc.get("strike")
            option_type = doc.get("option_type")

            if not all([symbol, index, expiry, strike, option_type]):
                print(f"⚠ Skipping invalid document for {symbol}")
                continue

            print(f"♻ Resuming {symbol}")

            # Recreate engine
            _, engine = initialize_symbol(index, expiry, strike, option_type)

            active_engines[symbol] = engine
            engine_status[symbol] = "running"

            # Start live in background thread
            threading.Thread(
                target=start_live,
                args=(symbol,),
                daemon=True
            ).start()

        except Exception as e:
            print(f"❌ Failed to resume {doc.get('symbol')}: {e}")

    print("🚀 Auto-resume complete.")


# =====================================================
# INIT SYMBOL
# =====================================================
@app.post("/init")
def init_symbol(index: str, expiry: str, strike: str, option_type: str):

    symbol, engine = initialize_symbol(index, expiry, strike, option_type)

    active_engines[symbol] = engine
    engine_status[symbol] = "running"

    return {"status": "initialized", "symbol": symbol}


# =====================================================
# START LIVE
# =====================================================
@app.post("/start/{symbol}")
def start(symbol: str, bg: BackgroundTasks):

    if symbol not in active_engines:
        return {"error": "symbol not initialized"}

    bg.add_task(start_live, symbol)

    return {"status": "live_started"}


# =====================================================
# PAUSE
# =====================================================
@app.post("/pause/{symbol}")
def pause(symbol: str):

    if symbol not in engine_status:
        return {"error": "symbol not found"}

    engine_status[symbol] = "paused"

    return {"status": "paused"}


# =====================================================
# DELETE
# =====================================================
@app.delete("/delete/{symbol}")
def delete(symbol: str):

    active_engines.pop(symbol, None)
    engine_status.pop(symbol, None)

    # Optional: remove from Mongo as well
    symbol_col.delete_one({"symbol": symbol})

    return {"status": "deleted"}