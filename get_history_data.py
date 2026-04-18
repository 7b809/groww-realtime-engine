# get_history_data.py

from datetime import datetime, timedelta
from dhanhq import dhanhq
from get_keys import load_valid_dhan_credentials
import time
import os
import json


# -------------------------------------------------
# DEFAULT INDEX CONFIG (BUILT-IN SUPPORT)
# -------------------------------------------------
DEFAULT_INSTRUMENTS = {
    "nifty": {
        "security_id": "13",
        "exchange": "IDX_I",
        "instrument": "INDEX"
    },
    "sensex": {
        "security_id": "51",
        "exchange": "IDX_I",
        "instrument": "INDEX"
    },
    "giftnifty": {
        "security_id": "5024",
        "exchange": "NSE_FNO",
        "instrument": "FUTURE"
    }
}


# -------------------------------------------------
# CREATE CLIENT
# -------------------------------------------------
def get_client():
    try:
        creds = load_valid_dhan_credentials()

        if not creds:
            raise Exception("❌ No valid token available")

        return dhanhq(
            client_id=creds["client_id"],
            access_token=creds["access_token"]
        )

    except Exception as e:
        raise Exception(f"❌ Client init failed: {e}")


# -------------------------------------------------
# RESOLVE INPUT
# -------------------------------------------------
def resolve_input(symbol=None, security_id=None, exchange=None, instrument=None):

    if symbol:
        key = symbol.lower()

        if key in DEFAULT_INSTRUMENTS:
            return DEFAULT_INSTRUMENTS[key]

        raise Exception(f"❌ Unknown symbol: {symbol}")

    if security_id and exchange and instrument:
        return {
            "security_id": security_id,
            "exchange": exchange,
            "instrument": instrument
        }

    raise Exception("❌ Provide either symbol OR full config")


# -------------------------------------------------
# CONVERT DHAN FORMAT → ROW FORMAT
# -------------------------------------------------
def convert_to_rows(batch):
    rows = []

    try:
        if not isinstance(batch, dict):
            return rows

        # ✅ FIX: support both formats
        times = batch.get("start_Time") or batch.get("timestamp") or []

        opens = batch.get("open", [])
        highs = batch.get("high", [])
        lows = batch.get("low", [])
        closes = batch.get("close", [])
        volumes = batch.get("volume", [])

        for i in range(len(times)):

            time_val = times[i]

            # ✅ Convert UNIX timestamp → ISO string (if needed)
            if isinstance(time_val, (int, float)):
                time_val = datetime.utcfromtimestamp(time_val).isoformat()

            rows.append({
                "time": time_val,
                "open": opens[i] if i < len(opens) else None,
                "high": highs[i] if i < len(highs) else None,
                "low": lows[i] if i < len(lows) else None,
                "close": closes[i] if i < len(closes) else None,
                "volume": volumes[i] if i < len(volumes) else None,
            })

    except Exception as e:
        print(f"❌ Conversion error: {e}")

    return rows


# -------------------------------------------------
# SAVE TO FILE
# -------------------------------------------------
def save_to_file(data, filename="output.json"):
    try:
        folder = "temp"
        os.makedirs(folder, exist_ok=True)

        path = os.path.join(folder, filename)

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        print(f"💾 Data saved to {path}")

    except Exception as e:
        print(f"❌ File save error: {e}")


# -------------------------------------------------
# FETCH INTRADAY (MAIN FUNCTION)
# -------------------------------------------------
def fetch_intraday_data(
    symbol: str = None,
    security_id: str = None,
    exchange: str = None,
    instrument: str = None,
    days: int = 5,
    interval: int = 5,
    save_flag: bool = False
):

    try:
        config = resolve_input(symbol, security_id, exchange, instrument)

        security_id = config["security_id"]
        exchange = config["exchange"]
        instrument = config["instrument"]

        client = get_client()

        # ⚠️ (kept your logic same — only safer version)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        all_batches = []
        final_rows = []

        current_start = start_date

        print(f"\n📊 Fetching {days} days intraday data...\n")
        print(f"Instrument → {security_id} | {exchange} | {instrument}\n")

        while current_start < end_date:

            current_end = current_start + timedelta(days=5)

            if current_end > end_date:
                current_end = end_date

            from_str = current_start.strftime("%Y-%m-%d")
            to_str = current_end.strftime("%Y-%m-%d")

            print(f"➡️ Fetching: {from_str} → {to_str}")

            try:
                res = client.intraday_minute_data(
                    security_id=security_id,
                    exchange_segment=exchange,
                    instrument_type=instrument,
                    from_date=from_str,
                    to_date=to_str,
                    interval=interval
                )

                if res.get("status") == "success":
                    batch = res.get("data", {})

                    all_batches.append(batch)

                    rows = convert_to_rows(batch)
                    final_rows.extend(rows)

                    print(f"✅ Fetched {len(rows)} candles")

                else:
                    print(f"❌ API Error: {res.get('remarks')}")

            except Exception as e:
                print(f"❌ API call error: {e}")

            time.sleep(0.5)

            current_start = current_end + timedelta(days=1)

        # -------------------------------------------------
        # REMOVE DUPLICATES
        # -------------------------------------------------
        unique = {}
        for row in final_rows:
            ts = row.get("time")
            if ts:
                unique[ts] = row

        final_data = list(unique.values())

        print(f"\n✅ Total unique candles: {len(final_data)}\n")

        # -------------------------------------------------
        # SAVE IF REQUIRED
        # -------------------------------------------------
        if save_flag:
            save_to_file(final_data)

        return final_data

    except Exception as e:
        print(f"❌ Main function error: {e}")
        return []