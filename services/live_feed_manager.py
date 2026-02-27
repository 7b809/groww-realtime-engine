# services/live_feed_manager.py

from dhanhq import marketfeed
import threading
import asyncio
import pytz


class LiveFeedManager:

    def __init__(self, client_id, access_token):
        self.client_id = client_id
        self.access_token = access_token

        self.feed = None
        self.thread = None
        self.loop = None
        self.started = False

        self.symbol_states = {}
        self.subscribed_symbols = set()

        self.lock = threading.Lock()
        self.ready_event = threading.Event()

        self.ist = pytz.timezone("Asia/Kolkata")

    # -----------------------------------
    # Dedicated Dhan event loop thread
    # -----------------------------------
    def _run_feed_loop(self):

        # Create isolated event loop (separate from FastAPI)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.feed = marketfeed.DhanFeed(
            self.client_id,
            self.access_token,
            [],
            "v2"
        )

        # Mark feed ready (fix race condition)
        self.ready_event.set()

        # Connect and start websocket loop
        self.loop.run_until_complete(self.feed.connect())
        self.loop.run_forever()

    # -----------------------------------
    # Start feed ONLY ONCE
    # -----------------------------------
    def _start_once(self):

        if self.started:
            return

        self.thread = threading.Thread(
            target=self._run_feed_loop,
            daemon=True
        )
        self.thread.start()

        self.started = True

    # -----------------------------------
    # Subscribe symbol safely
    # -----------------------------------
    def subscribe(self, exchange_segment, security_id):

        with self.lock:

            self._start_once()

            # Wait until feed initialized
            self.ready_event.wait()

            if security_id in self.subscribed_symbols:
                return

            instruments = [
                (exchange_segment, str(security_id), marketfeed.Full)
            ]

            # Thread-safe scheduling (NOT coroutine)
            self.loop.call_soon_threadsafe(
                self.feed.subscribe_symbols,
                instruments
            )

            self.subscribed_symbols.add(security_id)

            # Initialize state for this symbol
            self.symbol_states[security_id] = {
                "current_minute": None,
                "candle": None,
                "closed_candle": None
            }

    # -----------------------------------
    # Optional unsubscribe
    # -----------------------------------
    def unsubscribe(self, exchange_segment, security_id):

        with self.lock:

            if security_id not in self.subscribed_symbols:
                return

            instruments = [
                (exchange_segment, str(security_id), marketfeed.Full)
            ]

            self.loop.call_soon_threadsafe(
                self.feed.unsubscribe_symbols,
                instruments
            )

            self.subscribed_symbols.remove(security_id)

            if security_id in self.symbol_states:
                del self.symbol_states[security_id]

    # -----------------------------------
    # Process incoming ticks
    # -----------------------------------
    def process_tick(self):

        if not self.feed:
            return None, None

        data = self.feed.get_data()

        if not data or not isinstance(data, dict):
            return None, None

        if data.get("type") != "Full Data":
            return None, None

        security_id = data["security_id"]

        if security_id not in self.symbol_states:
            return None, None

        ltp = float(data["LTP"])
        volume = int(data["volume"])
        ltt = data["LTT"]  # format HH:MM:SS

        state = self.symbol_states[security_id]

        minute_key = ltt[:5]  # HH:MM

        # -----------------------------------
        # If new minute → close previous candle
        # -----------------------------------
        if state["current_minute"] and minute_key != state["current_minute"]:

            closed = state["candle"]

            # Start new candle
            state["candle"] = {
                "timestamp": ltt,
                "open": ltp,
                "high": ltp,
                "low": ltp,
                "close": ltp,
                "volume": volume
            }

            state["current_minute"] = minute_key

            return security_id, closed

        # -----------------------------------
        # First candle initialization
        # -----------------------------------
        if state["current_minute"] is None:

            state["current_minute"] = minute_key
            state["candle"] = {
                "timestamp": ltt,
                "open": ltp,
                "high": ltp,
                "low": ltp,
                "close": ltp,
                "volume": volume
            }

            return None, None

        # -----------------------------------
        # Update existing candle
        # -----------------------------------
        candle = state["candle"]
        candle["high"] = max(candle["high"], ltp)
        candle["low"] = min(candle["low"], ltp)
        candle["close"] = ltp
        candle["volume"] = volume

        return None, None