import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load .env only in local environment
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "groww_engine")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "signals")

if not MONGO_URI:
    raise ValueError("MONGO_URI not set in environment variables")

# Create Mongo Client
client = MongoClient(MONGO_URI)

db = client[MONGO_DB_NAME]
signals_col = db[MONGO_COLLECTION]


def save_signal(data):
    signals_col.insert_one(data)