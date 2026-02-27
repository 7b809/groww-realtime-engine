import requests
import json,os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

dhan_client_id = os.getenv("DHAN_CLIENT_ID")
pin = os.getenv("DHAN_PIN")
    
# ==============================
# CONFIG
# ==============================
GENERATE_TOKEN_URL = "https://auth.dhan.co/app/generateAccessToken"
PROFILE_URL = "https://api.dhan.co/v2/profile"
TOKEN_FILE = "dhan_token.json"


# ==============================
# 1️⃣ Generate Access Token
# ==============================
def generate_access_token(dhan_client_id: str, pin: str, totp: str) -> dict:
    """
    Generate access token using client ID, pin and totp.
    """

    params = {
        "dhanClientId": dhan_client_id,
        "pin": pin,
        "totp": totp
    }

    try:
        response = requests.post(GENERATE_TOKEN_URL, params=params)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print("❌ Error generating access token:", e)
        return None


# ==============================
# 2️⃣ Validate Token
# ==============================
def validate_token(access_token: str) -> bool:
    """
    Validate token using profile API
    """

    headers = {
        "access-token": access_token
    }

    try:
        response = requests.get(PROFILE_URL, headers=headers)
        if response.status_code == 200:
            print("✅ Token is valid.")
            return True
        else:
            print("❌ Token validation failed:", response.text)
            return False

    except requests.exceptions.RequestException as e:
        print("❌ Error validating token:", e)
        return False


# ==============================
# 3️⃣ Save Token to JSON
# ==============================
def save_token(data: dict):
    """
    Save token response to JSON file
    """

    token_data = {
        "dhanClientId": data.get("dhanClientId"),
        "accessToken": data.get("accessToken"),
        "expiryTime": data.get("expiryTime"),
        "savedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=4)

    print("💾 Token saved to", TOKEN_FILE)


# ==============================
# 4️⃣ Main Flow Function
# ==============================
def login_and_store_token():
    """
    Complete flow:
    - Take inputs
    - Generate token
    - Validate
    - Save
    """


    totp = input("Enter TOTP Code: ").strip()

    print("\n🔐 Generating Access Token...")

    token_response = generate_access_token(dhan_client_id, pin, totp)

    if not token_response or "accessToken" not in token_response:
        print("❌ Failed to generate token.")
        return

    access_token = token_response["accessToken"]

    print("🔎 Validating Token...")

    if validate_token(access_token):
        save_token(token_response)
    else:
        print("❌ Token is invalid. Not saving.")


# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    login_and_store_token()