import logging
import os
import yaml
import json
import shutil
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

logger = logging.getLogger(__name__)

# === Custom YAML String Handling ===
class FoldedStr(str):
    pass

def folded_str_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='>')

yaml.add_representer(FoldedStr, folded_str_representer)


# === Configuration ===
YAML_FILE = "../_data/events.yml"
BACKUP_DIR = "../_data/"
CREDENTIALS_FILE = "service_creds.json"
SPREADSHEET_NAME = "Fall 2025 DAP Lab Seminar"
SHEET_NAME = "website"
UNIQUE_KEY = "title"


# === Authenticate & Load Google Sheet ===
def load_events_from_google_sheet():
    creds_json = os.environ["GOOGLE_SHEET_CREDENTIALS"]
    creds_dict = json.loads(creds_json)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_NAME)
    records = sheet.get_all_records()
    logger.info(f"Loaded {len(records)} records from Google Sheet: {SPREADSHEET_NAME} - {SHEET_NAME}")
    return records


# === Load Existing YAML Events ===
def load_yaml_events():
    if not os.path.exists(YAML_FILE):
        logger.error(f"YAML file not found: {YAML_FILE}.")
        raise FileNotFoundError(f"YAML file not found: {YAML_FILE}")
    with open(YAML_FILE, "r") as f:
        data = yaml.safe_load(f)
        logger.info(f"Loaded {len(data)} events from YAML file: {YAML_FILE}")
        return data or []

# === Save backup ===
def save_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_path = os.path.join(BACKUP_DIR, f"events.yml.bak")
    shutil.copy(YAML_FILE, backup_path)
    logger.info(f"Backup saved to {backup_path}")

# === Save updated YAML ===
def save_yaml_events(events):
    with open(YAML_FILE, "w") as f:
        yaml.dump(events, f, sort_keys=False, allow_unicode=True)
    logger.info(f"YAML updated: {YAML_FILE}")

# === Merge Events ===
def clean_events_data(events):
    converted = []
    for event in events:
        event_copy = dict(event)

        # Always use block style for 'description'
        if 'description' in event_copy:
            event_copy['description'] = FoldedStr(event_copy['description'])

        # Remove optional empty fields
        if not event_copy.get('link'):
            event_copy.pop('link', None)
        if not event_copy.get('who'):
            event_copy.pop('who', None)

        converted.append(event_copy)
    return converted

def merge_events(existing_events, sheet_events):
    merged = {e[UNIQUE_KEY]: e for e in existing_events}
    for e in sheet_events:
        merged[e[UNIQUE_KEY]] = e
    return list(merged.values())

def events_changed(old, new):
    old_sorted = sorted(old, key=lambda e: str(e))
    new_sorted = sorted(new, key=lambda e: str(e))
    return old_sorted != new_sorted

# === Main Sync Logic ===
def main():
    logger.info("Loading data from Google Sheet...")
    sheet_events = load_events_from_google_sheet()

    logger.info("Loading data from Existing YAML...")
    yaml_events = load_yaml_events()

    logger.info("Merging events...")
    merged_events = merge_events(yaml_events, sheet_events)
    merged_events = clean_events_data(merged_events)

    if events_changed(yaml_events, merged_events):
        logger.info("New updates detected. Saving backup and writing YAML...")
        save_backup()
        save_yaml_events(merged_events)
    else:
        logger.info("No updates detected. Nothing changed.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    main()
