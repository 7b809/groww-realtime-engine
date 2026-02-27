from dhanhq import marketfeed
import json
import asyncio
import threading
import time
import os

# ============================
# WINDOWS EVENT LOOP FIX
# ============================

def setup_event_loop():
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


# ============================
# LOGGING
# ============================

PRINT_LOGS = True

def log(msg):
    if PRINT_LOGS:
        print(f"[LOG {time.strftime('%H:%M:%S')}] {msg}")


# ============================
# LOAD TOKEN
# ============================

def load_token(file_name="dhan_token.json"):
    log("Loading token file...")
    with open(file_name, "r", encoding="utf-8") as f:
        data = json.load(f)
    log("Token loaded successfully.")
    return data["dhanClientId"], data["accessToken"]


# ============================
# CREATE FEED
# ============================

def create_feed(client_id, access_token, instruments, version="v2"):
    log("Initializing DhanFeed...")
    return marketfeed.DhanFeed(client_id, access_token, instruments, version)


# ============================
# START FEED THREAD
# ============================

def start_feed(feed):
    log("Starting feed thread...")
    thread = threading.Thread(target=feed.run_forever, daemon=True)
    thread.start()
    return thread


# ============================
# LIVE DATA LOOP
# ============================

def consume_feed(feed):

    log("Consuming live feed data...")

    while True:

        response = feed.get_data()

        if response and isinstance(response, dict):

            os.system('cls' if os.name == 'nt' else 'clear')

            print("📈 LIVE OPTION DATA")
            print("=" * 70)

            print(f"Type        : {response.get('type')}")
            print(f"Security ID : {response.get('security_id')}")
            print(f"LTP         : {response.get('LTP')}")
            print(f"Volume      : {response.get('volume')}")
            print(f"OI          : {response.get('OI')}")
            print("-" * 70)

        time.sleep(0.2)


# ============================
# SUBSCRIBE SYMBOLS
# ============================

def subscribe_symbols(feed, instruments):
    log(f"Subscribing: {instruments}")
    feed.subscribe_symbols(instruments)


# ============================
# UNSUBSCRIBE SYMBOLS
# ============================

def unsubscribe_symbols(feed, instruments):
    log(f"Unsubscribing: {instruments}")
    feed.unsubscribe_symbols(instruments)


# ============================
# DISCONNECT
# ============================

def disconnect_feed(feed):
    log("Disconnecting feed...")
    try:
        feed.disconnect()
    except:
        pass


# ============================
# MAIN EXECUTION
# ============================

def main():

    setup_event_loop()

    client_id, access_token = load_token()

    instruments = [
        (marketfeed.NSE_FNO, "54909", marketfeed.Full),
        (marketfeed.NSE_FNO, "54910", marketfeed.Full),
    ]

    feed = create_feed(client_id, access_token, instruments)

    start_feed(feed)

    try:
        consume_feed(feed)

    except KeyboardInterrupt:
        log("Keyboard interrupt received.")
        disconnect_feed(feed)


# if __name__ == "__main__":
#     main()