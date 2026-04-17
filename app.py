from flask import Flask, request, jsonify, render_template
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import os

# ✅ IMPORT OPTION CHAIN FETCHER
from main import fetch_option_chain


# -------------------------------
# LOAD ENV
# -------------------------------
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "trading_db")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

alerts_col = db["alerts"]
trades_col = db["trades"]

# -------------------------------
app = Flask(__name__)

capital = 10000
current_position = None
entry_price = None
current_strike = None   # ✅ NEW (safe add)
trades = []

# -------------------------------
# STRIKE LOGIC
# -------------------------------
def get_strike(price, signal_type):
    base = int(price // 50) * 50

    if signal_type == "buyCE":
        return base
    elif signal_type == "buyPE":
        return base + 50

    return base


# -------------------------------
# GET OPTION PRICE FROM DATA
# -------------------------------
def get_option_price(data, strike, signal_type):
    for s in data["strikes"]:
        if s["strike"] == strike:
            return s["ce_price"] if signal_type == "buyCE" else s["pe_price"]
    return None


# -------------------------------
# PARSE ALERT
# -------------------------------
def parse_alert(msg):
    data = {}

    try:
        parts = msg.split(" ", 1)
        data["Signal"] = parts[0]

        rest = parts[1]

        import re

        time_match = re.search(r"Time=([0-9\-: ]+)", rest)
        price_match = re.search(r"Price=([0-9\.]+)", rest)
        type_match = re.search(r"Type=([a-zA-Z]+)", rest)

        if time_match:
            data["Time"] = time_match.group(1)

        if price_match:
            data["Price"] = price_match.group(1)

        if type_match:
            data["Type"] = type_match.group(1)

    except Exception as e:
        data["error"] = str(e)

    return data


# -------------------------------
# EXECUTE TRADE (UNCHANGED LOGIC)
# -------------------------------
def execute_trade(signal_type, price, strike=None):
    global capital, current_position, entry_price, current_strike, trades

    action_log = ""
    new_position = "CE" if signal_type == "buyCE" else "PE"

    # ENTRY
    if current_position is None:
        current_position = new_position
        entry_price = price
        current_strike = strike   # ✅ NEW (safe add)

        action_log = f"Entered {new_position} at {price}"

    # HOLD
    elif current_position == new_position:
        action_log = f"HOLD {new_position}"

    # EXIT + REVERSE
    else:
        pnl = price - entry_price if current_position == "CE" else entry_price - price
        capital += pnl

        trade_data = {
            "type": current_position,
            "strike": current_strike,   # ✅ NEW (safe add)
            "entry": entry_price,
            "exit": price,
            "pnl": pnl,
            "time": datetime.utcnow()
        }

        trades.append(trade_data)
        trades_col.insert_one(trade_data)

        action_log = f"EXIT {current_position} at {price} | PnL: {pnl:.2f}"

        current_position = new_position
        entry_price = price
        current_strike = strike   # ✅ NEW

        action_log += f" → ENTER {new_position} at {price}"

    return action_log


# -------------------------------
# WEBHOOK
# -------------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if not data or "message" not in data:
        return jsonify({"error": "Invalid data"}), 400

    msg = data["message"]
    parsed = parse_alert(msg)

    signal_type = parsed.get("Type")
    spot_price = float(parsed.get("Price", 0))

    # -----------------------------------
    # STRIKE CALCULATION
    # -----------------------------------
    strike = get_strike(spot_price, signal_type)

    # -----------------------------------
    # FETCH OPTION CHAIN
    # -----------------------------------
    option_data = fetch_option_chain()

    if not option_data:
        return jsonify({"error": "Option chain fetch failed"}), 500

    # -----------------------------------
    # GET OPTION PREMIUM
    # -----------------------------------
    option_price = get_option_price(option_data, strike, signal_type)

    if option_price is None or option_price == 0:
        return jsonify({"error": "Invalid strike or illiquid option"}), 500

    print(f"🎯 Trade -> {signal_type} | Spot: {spot_price} | Strike: {strike} | Option Price: {option_price}")

    # -----------------------------------
    # SAVE ALERT
    # -----------------------------------
    alert_doc = {
        "raw_message": msg,
        "parsed": parsed,
        "spot_price": spot_price,
        "strike": strike,
        "option_price": option_price,
        "time": datetime.utcnow()
    }
    alerts_col.insert_one(alert_doc)

    # -----------------------------------
    # EXECUTE TRADE
    # -----------------------------------
    result = execute_trade(signal_type, option_price, strike)

    return jsonify({
        "status": "success",
        "action": result,
        "capital": capital,
        "current_position": current_position,
        "strike": strike,
        "option_price": option_price
    })


# -------------------------------
# UI ROUTE
# -------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        capital=round(capital, 2),
        position=current_position,
        entry=entry_price,
        strike=current_strike,   # ✅ NEW
        trades=trades[::-1]
    )


# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)