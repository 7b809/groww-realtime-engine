import os
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "trading"
COLLECTION_NAME = "auth"

# -----------------------------------
# CONNECT (singleton style)
# -----------------------------------
_client = None
_collection = None

def get_collection():
    global _client, _collection

    if _collection is None:
        if not MONGO_URI:
            raise ValueError("❌ MONGO_URI not found in .env")

        _client = MongoClient(MONGO_URI)
        db = _client[DB_NAME]
        _collection = db[COLLECTION_NAME]

        print("✅ MongoDB connected")

    return _collection


# -----------------------------------
# SAVE TOKEN TO MONGO
# -----------------------------------
def save_token_to_mongo(data: dict):
    try:
        collection = get_collection()

        collection.update_one(
            {"_id": "dhan_token"},
            {"$set": data},
            upsert=True
        )

        print("✅ Token saved to MongoDB")

    except Exception as e:
        print(f"❌ Mongo save error: {e}")


# -----------------------------------
# FETCH TOKEN FROM MONGO
# -----------------------------------
def fetch_token_from_mongo():
    try:
        collection = get_collection()

        data = collection.find_one({"_id": "dhan_token"})

        if not data:
            print("❌ No token found in MongoDB")
            return None

        data.pop("_id", None)  # remove internal id

        return data

    except Exception as e:
        print(f"❌ Mongo fetch error: {e}")
        return None


# -----------------------------------
# DELETE TOKEN FROM MONGO
# -----------------------------------
def delete_token_from_mongo():
    try:
        collection = get_collection()

        collection.delete_one({"_id": "dhan_token"})
        print("🗑️ Token deleted from MongoDB")

    except Exception as e:
        print(f"❌ Mongo delete error: {e}")


# -----------------------------------
# LOAD DHAN CREDENTIALS (CORE FUNCTION)
# -----------------------------------
def load_dhan_credentials():
    data = fetch_token_from_mongo()

    if not data:
        print("❌ No token data found")
        return None

    dhan_client_id = data.get("dhanClientId")
    access_token = data.get("accessToken")
    expiry_time = data.get("expiryTime")

    # ✅ Validate required fields
    if not dhan_client_id or not access_token or not expiry_time:
        print("❌ Missing required token fields")
        return None

    # ✅ Convert expiry string → datetime
    try:
        if not expiry_time.endswith("Z"):
            expiry_time = expiry_time + "Z"

        expiry_dt = datetime.fromisoformat(expiry_time.replace("Z", "+00:00"))

    except Exception:
        print("❌ Invalid expiry format")
        return None

    return {
        "client_id": dhan_client_id,
        "access_token": access_token,
        "expiry": expiry_dt
    }


# -----------------------------------
# LOAD ONLY VALID TOKEN (BEST PRACTICE)
# -----------------------------------
def load_valid_dhan_credentials():
    creds = load_dhan_credentials()

    if not creds:
        return None


    if datetime.now(timezone.utc) >= creds["expiry"]:
        print("❌ Token expired")
        return None

    return creds


# # -----------------------------------
# # QUICK TEST (optional)
# # -----------------------------------
# if __name__ == "__main__":

#     print("\n🔹 Fetching credentials...\n")

#     creds = load_valid_dhan_credentials()

#     if not creds:
#         print("⚠️ No valid token found. Please authenticate again.")
#     else:
#         print("✅ Credentials Loaded Successfully")
#         print(f"Client ID: {creds['client_id'][:3]}...")
#         print(f"Access Token: {creds['access_token'][:10]}...")  # partial for safety
#         print(f"Expiry: {creds['expiry']}")