import json
import requests
from datetime import datetime, timezone

# ✅ import your loader
from get_keys import load_valid_dhan_credentials


# -----------------------------------
# EXTRACT ONLY CE/PE PRICES
# -----------------------------------
def extract_prices(option_chain_data):
    result = {
        "last_price": option_chain_data["data"]["last_price"],
        "strikes": []
    }

    oc = option_chain_data["data"]["oc"]

    for strike, values in oc.items():
        ce = values.get("ce", {})
        pe = values.get("pe", {})

        ce_price = ce.get("last_price", 0)
        pe_price = pe.get("last_price", 0)

        # ✅ Skip useless strikes
        if ce_price == 0 and pe_price == 0:
            continue

        result["strikes"].append({
            "strike": float(strike),
            "ce_price": ce_price,
            "pe_price": pe_price
        })

    return result


# -----------------------------------
# FETCH OPTION CHAIN (IMPORTANT)
# -----------------------------------
def fetch_option_chain():
    creds = load_valid_dhan_credentials()

    if not creds:
        print("❌ No valid credentials")
        return None

    CLIENT_ID = creds["client_id"]
    ACCESS_TOKEN = creds["access_token"]

    url = "https://api.dhan.co/v2/optionchain"

    headers = {
        "Content-Type": "application/json",
        "access-token": ACCESS_TOKEN,
        "client-id": CLIENT_ID
    }

    payload = {
        "UnderlyingScrip": 13,     # NIFTY
        "UnderlyingSeg": "IDX_I",
        "Expiry": "2026-04-21"     # ⚠️ ensure valid expiry
    }

    print("⏳ Fetching Option Chain...")

    try:
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            print(response.text)
            return None

        data = response.json()

        if data.get("status") != "success":
            print("❌ API returned error")
            print(data)
            return None

        print("✅ Option Chain fetched")

        # -----------------------------------
        # FILTER DATA
        # -----------------------------------
        filtered_data = extract_prices(data)

        # -----------------------------------
        # SAVE CLEAN DATA
        # -----------------------------------
        try:
            with open("output.json", "w") as f:
                json.dump(filtered_data, f, indent=4)
            print("💾 Filtered data saved to output.json")
        except Exception as e:
            print(f"⚠️ File save error: {e}")

        # -----------------------------------
        # OPTIONAL: FIND ATM
        # -----------------------------------
        if filtered_data["strikes"]:
            last_price = filtered_data["last_price"]

            atm = min(
                filtered_data["strikes"],
                key=lambda x: abs(x["strike"] - last_price)
            )

            print("\n🎯 ATM Strike:")
            print(atm)

        # ✅ IMPORTANT → RETURN DATA (used in app.py)
        return filtered_data

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


# # -----------------------------------
# # MAIN (standalone run)
# # -----------------------------------
# if __name__ == "__main__":
#     print("\n🔹 Starting Option Chain Fetch...\n")

#     data = fetch_option_chain()

#     if data:
#         print("\n✅ Done")
#     else:
#         print("\n❌ Failed to fetch data")