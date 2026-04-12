"""
MPSJ Auto-Updater
Checks the Parliament API for new Register publications,
downloads new data, and runs compute_summary.py.

Can be run manually or via GitHub Actions.

Usage:
    python scripts/update_data.py
"""

import json
import os
import sys
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError


# --- Configuration ---
API_BASE = "https://interests-api.parliament.uk/api/v1"
DATA_DIR = Path("data/2024-present")
STATE_FILE = Path("data/last_register.json")
REF_FILE = Path("mp_reference.csv")
SESSION_START = "2024-07-17"
OUTPUT_SUMMARY = Path("mp_session_summary.csv")


def api_get(endpoint):
    """Make a GET request to the Parliament API and return parsed JSON."""
    url = f"{API_BASE}/{endpoint}"
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except URLError as e:
        print(f"ERROR: Failed to reach Parliament API: {e}")
        sys.exit(1)


def get_latest_register():
    """Fetch the most recent Commons register publication from the API."""
    data = api_get("Registers?House=1&take=1")
    items = data.get("items", [])
    if not items:
        print("ERROR: No register publications found in API response.")
        sys.exit(1)
    latest = items[0]
    return {
        "id": latest["id"],
        "published_date": latest["publishedDate"],
    }


def load_state():
    """Load the last-processed register info from state file."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return None


def save_state(register_info):
    """Save the current register info to state file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "register_id": register_info["id"],
        "published_date": register_info["published_date"],
        "updated_at": datetime.now(timezone.utc).isoformat() + "Z",
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    print(f"State saved: register {state['register_id']} ({state['published_date']})")


def download_csv_zip(register_id, dest_dir):
    """Download the CSV zip for a register and extract to dest_dir."""
    url = f"{API_BASE}/Interests/csv?registerId={register_id}"
    print(f"Downloading CSV zip from: {url}")

    req = Request(url)
    zip_path = dest_dir / "register.zip"
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        with urlopen(req, timeout=120) as resp:
            data = resp.read()
    except URLError as e:
        print(f"ERROR: Failed to download CSV zip: {e}")
        sys.exit(1)

    with open(zip_path, "wb") as f:
        f.write(data)
    print(f"Downloaded {len(data):,} bytes")

    # Extract
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
        extracted = zf.namelist()
    print(f"Extracted {len(extracted)} files to {dest_dir}")

    # Clean up zip
    zip_path.unlink()

    return extracted


def run_compute_summary():
    """Run compute_summary.py to regenerate the summary and detail CSVs."""
    cmd = [
        sys.executable, "compute_summary.py",
        "--data-dir", str(DATA_DIR),
        "--ref", str(REF_FILE),
        "--session-start", SESSION_START,
        "--output", str(OUTPUT_SUMMARY),
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print(f"ERROR: compute_summary.py exited with code {result.returncode}")
        sys.exit(1)

    print("compute_summary.py completed successfully.")


def main():
    print("=" * 60)
    print(f"MPSJ Auto-Updater — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    # 1. Check the API for the latest register
    print("\nChecking Parliament API for latest register...")
    latest = get_latest_register()
    print(f"Latest register: ID {latest['id']}, published {latest['published_date']}")

    # 2. Compare against what we last processed
    state = load_state()
    if state and state.get("register_id") == latest["id"]:
        print(f"\nNo new data — register {latest['id']} already processed.")
        print("Nothing to do. Exiting.")
        return False  # Signal: no update

    if state:
        print(f"\nNew register found! Previous: {state['register_id']} ({state['published_date']})")
    else:
        print("\nNo previous state found — first run.")

    # 3. Download and extract
    # Use the published date as the subfolder name (yymmdd)
    pub_date = datetime.strptime(latest["published_date"], "%Y-%m-%d")
    subfolder = pub_date.strftime("%y%m%d")
    dest_dir = DATA_DIR / subfolder
    print(f"\nDownloading register {latest['id']} to {dest_dir}...")
    download_csv_zip(latest["id"], dest_dir)

    # 4. Run compute_summary.py
    print("\nRecomputing summary...")
    run_compute_summary()

    # 5. Save state
    save_state(latest)

    print("\n" + "=" * 60)
    print("Update complete!")
    print("=" * 60)
    return True  # Signal: update happened


if __name__ == "__main__":
    updated = main()
    # Exit code 0 means success; we use a file flag for GitHub Actions
    if updated:
        # Write a flag file so the workflow knows to commit
        Path(".data_updated").touch()
