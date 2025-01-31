import json
from pathlib import Path
import datetime

SCHEDULE_FILE = Path("election_schedule.json")

def save_schedule(data):
    with open(SCHEDULE_FILE, 'w') as f:
        json.dump(data, f, default=str)

def load_schedule():
    try:
        with open(SCHEDULE_FILE) as f:
            data = json.load(f)
            # Convert string dates back to datetime objects
            return {k: datetime.datetime.fromisoformat(v) for k, v in data.items()}
    except FileNotFoundError:
        return {}