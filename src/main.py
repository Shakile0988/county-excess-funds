"""
Entry point run by GitHub Actions (triggered by n8n via repository_dispatch,
or by the monthly cron schedule).

For each source (tax sale listing, excess funds list, unclaimed refunds):
  1. Locate the current PDF link on the county site.
  2. Skip it if its content hash was already processed before (dedupe).
  3. Parse the PDF table.
  4. Filter by min excess amount + split person vs company (skipped for the
     upcoming tax-sale listing, which has no dollar amount yet).
  5. Send the result to n8n, persons first then companies/other.
  6. Record the new hash in state/seen_files.json.
"""

import json
import os
import sys

from scraper import find_all_target_links, download_file
from parser import parse_pdf_table
from filters import split_records
from send_webhook import send_to_n8n

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "state", "seen_files.json")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

# Per-source field names used to find the "owner" name column and the
# dollar amount column inside each PDF's table.
SOURCE_FIELD_MAP = {
    "excess_funds_list": {"name_field": "ORIGINAL OWNER", "amount_field": "EXCESS FUNDS"},
    "unclaimed_refunds": {"name_field": "PAYEE", "amount_field": "AMOUNT"},
}


def load_state() -> dict:
    with open(STATE_PATH, "r") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def run(config_path: str, webhook_url: str) -> None:
    with open(config_path, "r") as f:
        config = json.load(f)

    county_id = config["county_id"]
    state = load_state()
    state.setdefault(county_id, {"tax_sale_listing": [], "excess_funds_list": [], "unclaimed_refunds": []})

    links = find_all_target_links(config)

    for source_type, url in links.items():
        if not url:
            print(f"[skip] no link found for {source_type}")
            continue

        local_path, file_hash = download_file(url, DOWNLOAD_DIR)

        if file_hash in state[county_id][source_type]:
            print(f"[skip] {source_type} already processed (hash matches)")
            continue

        records = parse_pdf_table(local_path)
        if not records:
            print(f"[skip] {source_type} downloaded but no table found (likely 'coming soon')")
            # Still remember the hash so we don't re-download an unchanged empty file
            state[county_id][source_type].append(file_hash)
            continue

        if source_type in SOURCE_FIELD_MAP:
            fields = SOURCE_FIELD_MAP[source_type]
            persons, companies = split_records(
                records,
                fields["name_field"],
                fields["amount_field"],
                config["min_excess_amount"],
            )
            send_to_n8n(webhook_url, county_id, source_type, persons, companies)
            print(f"[sent] {source_type}: {len(persons)} persons, {len(companies)} companies")
        else:
            # tax_sale_listing: upcoming sale, no $ amount filter yet, send raw
            send_to_n8n(webhook_url, county_id, source_type, persons=[], companies=[], raw_records=records)
            print(f"[sent] {source_type}: {len(records)} raw upcoming listings")

        state[county_id][source_type].append(file_hash)

    save_state(state)


if __name__ == "__main__":
    cfg_path = os.path.join(BASE_DIR, "config", "hall_county.json")
    webhook = os.environ.get("N8N_WEBHOOK_URL")
    if not webhook:
        print("N8N_WEBHOOK_URL env var missing", file=sys.stderr)
        sys.exit(1)
    run(cfg_path, webhook)
