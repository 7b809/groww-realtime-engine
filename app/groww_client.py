import requests
import time
import pytz
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://groww.in/v1/api/stocks_fo_data/v1/charting_service/delayed/chart"

# ==========================
# EXCHANGE HELPER
# ==========================
def get_exchange(index):
    return "BSE" if index.upper() == "SENSEX" else "NSE"


# ==========================
# TODAY MARKET WINDOW
# ==========================
def generate_day_window():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.datetime.now(ist)

    start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end = now.replace(hour=16, minute=0, second=0, microsecond=0)

    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


# ==========================
# SINGLE FETCH (WITH RETRY)
# ==========================
def fetch_candles(symbol, interval, start_ms, end_ms, retries=3):
    exchange = get_exchange(symbol)
    segment = "FNO"

    url = (
        f"{BASE_URL}/exchange/{exchange}/segment/{segment}/{symbol}"
        f"?endTimeInMillis={end_ms}"
        f"&intervalInMinutes={interval}"
        f"&startTimeInMillis={start_ms}"
    )

    attempt = 0

    while attempt < retries:
        try:
            response = requests.get(url, timeout=30)

            if response.status_code == 200:
                return response.json().get("candles", [])
            else:
                print(f"⚠ HTTP {response.status_code}")

        except Exception as e:
            print(f"⚠ Fetch error: {e}")

        attempt += 1
        time.sleep(0.5)

    print("❌ Failed after retries:", start_ms, end_ms)
    return []


# ==========================
# MULTI-THREADED BATCH FETCH
# ==========================
def fetch_history_in_batches(symbol, interval, start_dt, end_dt):
    batch_days = 7
    tasks = []
    all_candles = []

    # Prepare batch windows
    current_start = start_dt

    while current_start < end_dt:
        current_end = min(
            current_start + datetime.timedelta(days=batch_days),
            end_dt
        )

        tasks.append((current_start, current_end))
        current_start = current_end

    # print(f"📦 Total batches: {len(tasks)}")

    # Batch fetch function
    def fetch_batch(window):
        start, end = window
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        # print(f"Fetching {start.date()} → {end.date()}")

        candles = fetch_candles(symbol, interval, start_ms, end_ms)
        return candles or []

    # ⚠ Limit workers to avoid Groww rate limits
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_batch, w) for w in tasks]

        for future in as_completed(futures):
            try:
                result = future.result()
                all_candles.extend(result)
            except Exception as e:
                print("Batch thread error:", e)

    # ==========================
    # REMOVE DUPLICATES
    # ==========================
    unique = {c[0]: c for c in all_candles}

    sorted_candles = sorted(unique.values(), key=lambda x: x[0])

    # print(f"✅ Total candles fetched: {len(sorted_candles)}")

    return sorted_candles