import json
from datetime import datetime
from pathlib import Path

# Create logs folder automatically
BASE_DIR = Path("logs")
BASE_DIR.mkdir(exist_ok=True)

LOG_FILE = BASE_DIR / "engine_logs.txt"
LIVE_FILE = BASE_DIR / "live_updates.json"


def write_log(*args):
    message = " ".join(str(a) for a in args)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    final_msg = f"[{timestamp}] {message}"

    # Print to console
    print(final_msg)

    # Append to text file
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(final_msg + "\n")


def save_live_update(data: dict):
    """
    Append live update to JSON file
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    record = {
        "saved_at": timestamp,
        "data": data
    }

    # Append mode JSON (line by line JSON)
    with open(LIVE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")