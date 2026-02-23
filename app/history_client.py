import os
import requests


def fetch_historic_signals(index, year, month, strike, option_type):

    base_url = os.getenv("HISTORIC_DATA_URL")

    url = f"{base_url}/api/history"

    params = {
        "index_name": index,
        "year": year,
        "month": month,
        "strike": strike,
        "option_type": option_type
    }

    response = requests.get(url, params=params, timeout=60)

    if response.status_code != 200:
        raise Exception("Failed to fetch history API")

    return response.json()