import json
import os

DATA_FILE = 'data/seen_bundles.json'

def clean_database():
    if not os.path.exists(DATA_FILE):
        print("❌ File not found.")
        return

    with open(DATA_FILE, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("❌ JSON is corrupt.")
            return

    print(f"Original count: {len(data)}")

    # Clean the IDs
    cleaned_set = set()
    for item in data:
        # Strip query parameters (everything after ?)
        clean_id = item.split('?')[0]
        cleaned_set.add(clean_id)

    print(f"Cleaned count:  {len(cleaned_set)}")

    # Save back to file
    with open(DATA_FILE, 'w') as f:
        json.dump(list(cleaned_set), f)
        
    print("✅ Database successfully cleaned!")

if __name__ == "__main__":
    clean_database()