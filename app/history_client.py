# app/history_client.py

import requests,os

BASE_URL = os.environ.get("HISTORIC_DATA_URL")

def fetch_historic_signals(index, year, month, expiry_day, strike, option_type):
    url = f"{BASE_URL}/api/history"

    params = {
    "index_name": index,
    "year": year,
    "month": month,
    "expiry_day": expiry_day,
    "strike": strike,
    "option_type": option_type
}
    r = requests.get(url, params=params, timeout=60)

    if r.status_code != 200:
        raise Exception("History API failed")

    return r.json()