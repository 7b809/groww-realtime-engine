import requests
import datetime
import pytz
import time

BASE_URL = "https://groww.in/v1/api/stocks_fo_data/v1/charting_service/delayed/chart"

def get_exchange(symbol):
    return "BSE" if "SENSEX" in symbol else "NSE"

def fetch_candles(symbol, interval, start_ms, end_ms):

    url = (
        f"{BASE_URL}/exchange/{get_exchange(symbol)}/segment/FNO/{symbol}"
        f"?endTimeInMillis={end_ms}"
        f"&intervalInMinutes={interval}"
        f"&startTimeInMillis={start_ms}"
    )

    for _ in range(3):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                return r.json().get("candles", [])
        except:
            pass
        time.sleep(1)

    return []

def generate_month_window():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.datetime.now(ist)

    start = now - datetime.timedelta(days=30)
    return int(start.timestamp()*1000), int(now.timestamp()*1000)

def generate_today_window():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.datetime.now(ist)

    start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    return int(start.timestamp()*1000), int(now.timestamp()*1000)