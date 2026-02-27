# services/groww_fetcher.py

import asyncio
import httpx
from datetime import datetime, timedelta
import pytz
from typing import List
from data_convert import generate_7day_batches

MAX_CONCURRENT_REQUESTS = 3
REQUEST_TIMEOUT = 20
RETRY_COUNT = 2


# ==========================================================
# INTERNAL SHARED FETCH FUNCTION (NEW - SAFE ADDITION)
# ==========================================================
async def _fetch_range(symbol: str, exchange: str, start_ms: int, end_ms: int):

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }

    url = (
        f"https://groww.in/v1/api/stocks_fo_data/v1/charting_service/"
        f"delayed/chart/exchange/{exchange}/segment/FNO/{symbol}"
        f"?endTimeInMillis={end_ms}"
        f"&intervalInMinutes=1"
        f"&startTimeInMillis={start_ms}"
    )

    async with httpx.AsyncClient(headers=headers) as client:
        try:
            response = await client.get(url, timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                data = response.json()
                candles = data.get("candles", [])

                # remove duplicates + sort
                candles = list(set(tuple(c) for c in candles))
                candles.sort(key=lambda x: x[0])

                return candles

        except Exception:
            return []

    return []


# ==========================================================
# EXISTING FUNCTION (UNCHANGED)
# ==========================================================
async def fetch_batch(client, semaphore, url):

    async with semaphore:
        for attempt in range(RETRY_COUNT):
            try:
                response = await client.get(url, timeout=REQUEST_TIMEOUT)

                if response.status_code == 200:
                    data = response.json()
                    return data.get("candles", [])

            except Exception:
                if attempt == RETRY_COUNT - 1:
                    return []

        return []


# ==========================================================
# EXISTING FUNCTION (UNCHANGED)
# ==========================================================
async def fetch_last_30_days(symbol: str, exchange: str):

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    past = now - timedelta(days=30)

    batches = generate_7day_batches(
        past.strftime("%d-%m-%Y"),
        now.strftime("%d-%m-%Y")
    )

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    all_candles = []

    async with httpx.AsyncClient(headers=headers) as client:

        tasks = []

        for start_ms, end_ms in batches:
            url = (
                f"https://groww.in/v1/api/stocks_fo_data/v1/charting_service/"
                f"delayed/chart/exchange/{exchange}/segment/FNO/{symbol}"
                f"?endTimeInMillis={end_ms}"
                f"&intervalInMinutes=1"
                f"&startTimeInMillis={start_ms}"
            )

            tasks.append(fetch_batch(client, semaphore, url))

        results = await asyncio.gather(*tasks)

    for candles in results:
        if candles:
            all_candles.extend(candles)

    # Remove duplicates + sort
    all_candles = list(set(tuple(c) for c in all_candles))
    all_candles.sort(key=lambda x: x[0])

    return all_candles, len(batches)


# ==========================================================
# NEW: FETCH LAST 24 HOURS
# ==========================================================
async def fetch_last_24hrs(symbol: str, exchange: str):
    """
    Fetch only last 24 hours of 1-min candles
    Does NOT affect existing logic
    """

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    end_time = int(now.timestamp() * 1000)
    start_time = int((now - timedelta(hours=24)).timestamp() * 1000)

    candles = await _fetch_range(
        symbol=symbol,
        exchange=exchange,
        start_ms=start_time,
        end_ms=end_time
    )

    return candles, 1


# ==========================================================
# NEW: FETCH ONLY LATEST CANDLE
# ==========================================================
async def fetch_latest_candle(symbol: str, exchange: str):

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    end_time = int(now.timestamp() * 1000)
    start_time = int((now - timedelta(minutes=10)).timestamp() * 1000)

    candles = await _fetch_range(
        symbol=symbol,
        exchange=exchange,
        start_ms=start_time,
        end_ms=end_time
    )

    if not candles:
        return None

    # Just return latest candle
    return candles[-1]