from flask import Flask, request, jsonify, render_template
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
import os

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
trades = []

# -------------------------------
def parse_alert(msg):
    data = {}

    try:
        # Split first word (signal name)
        parts = msg.split(" ", 1)
        data["Signal"] = parts[0]

        rest = parts[1]

        # Extract fields safely
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
def execute_trade(signal_type, price):
    global capital, current_position, entry_price, trades

    action_log = ""
    new_position = "CE" if signal_type == "buyCE" else "PE"

    # ENTRY
    if current_position is None:
        current_position = new_position
        entry_price = price

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
            "entry": entry_price,
            "exit": price,
            "pnl": pnl,
            "time": datetime.utcnow()
        }

        trades.append(trade_data)
        trades_col.insert_one(trade_data)   # 🔥 SAVE TRADE

        action_log = f"EXIT {current_position} at {price} | PnL: {pnl:.2f}"

        current_position = new_position
        entry_price = price
        action_log += f" → ENTER {new_position} at {price}"

    return action_log


# -------------------------------
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if not data or "message" not in data:
        return jsonify({"error": "Invalid data"}), 400

    msg = data["message"]
    parsed = parse_alert(msg)

    signal_type = parsed.get("Type")
    price = float(parsed.get("Price", 0))

    # 🔥 SAVE ALERT
    alert_doc = {
        "raw_message": msg,
        "parsed": parsed,
        "time": datetime.utcnow()
    }
    alerts_col.insert_one(alert_doc)

    result = execute_trade(signal_type, price)

    return jsonify({
        "status": "success",
        "action": result,
        "capital": capital,
        "current_position": current_position
    })


# -------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        capital=round(capital, 2),
        position=current_position,
        entry=entry_price,
        trades=trades[::-1]
    )


# -------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)