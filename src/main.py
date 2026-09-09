"""
Entry point run by GitHub Actions (triggered by n8n via repository_dispatch,
or by the monthly cron schedule).

Flow (per the county site):
  1. Visit the site, check Tax Sale for a new file -> if present, store it.
  2. Check Excess Funds for a new file -> if present, store it.
  3. Check Unclaimed Refunds for a new file -> if present, store it.
  4. For each source that had a file:
       - Tax Sale / Excess Funds: keep only leads >= $10,000, drop the rest.
       - Unclaimed Refunds: no dollar filter, just split directly.
       - Split what's left into Persons vs Others (LLC/company/Inc/etc).
  5. Build 6 labeled groups (2 per source: "<Source> - Persons" /
     "<Source> - Others"), and send them ALL to n8n in ONE webhook call -
     not once per source.
  6. Record each processed file's hash so it isn't re-sent next run.
"""

import json
import os
import sys

from scraper import find_all_target_links, download_file
from parser import parse_pdf_table
from filters import split_records
from send_webhook import send_grouped_to_n8n

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "state", "seen_files.json")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

ALL_SOURCES = ["tax_sale_listing", "excess_funds_list", "unclaimed_refunds"]


def load_state() -> dict:
    with open(STATE_PATH, "r") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def run(config_path: str, webhook_url: str, check_history: bool) -> None:
    with open(config_path, "r") as f:
        config = json.load(f)

    county_id = config["county_id"]
    state = load_state()
    state.setdefault(county_id, {s: [] for s in ALL_SOURCES})

    links = find_all_target_links(config)
    groups: list[dict] = []

    for source_type in ALL_SOURCES:
        url = links.get(source_type)
        if not url:
            print(f"[skip] no link found for {source_type}")
            continue

        local_path, file_hash = download_file(url, DOWNLOAD_DIR)

        if check_history and file_hash in state[county_id][source_type]:
            print(f"[skip] {source_type} already processed (hash matches)")
            continue
        elif not check_history and file_hash in state[county_id][source_type]:
            print(f"[force] {source_type} hash matches but history check is off, reprocessing")

        columns = config["columns"][source_type]
        records = parse_pdf_table(local_path, columns)
        if not records:
            print(f"[skip] {source_type} downloaded but no table found (likely 'coming soon')")
            if file_hash not in state[county_id][source_type]:
                state[county_id][source_type].append(file_hash)
            continue

        field_cfg = config["fields"][source_type]
        min_amount = config["min_excess_amount"] if field_cfg["filter_min_amount"] else None
        persons, others = split_records(
            records,
            field_cfg["name_field"],
            field_cfg.get("amount_field"),
            min_amount,
        )

        label = config["group_labels"][source_type]
        groups.append({"group_name": f"{label} - Persons", "source_type": source_type, "records": persons})
        groups.append({"group_name": f"{label} - Others", "source_type": source_type, "records": others})
        print(f"[processed] {source_type}: {len(persons)} persons, {len(others)} others "
              f"(filter applied: {field_cfg['filter_min_amount']})")

        if file_hash not in state[county_id][source_type]:
            state[county_id][source_type].append(file_hash)

    if groups:
        send_grouped_to_n8n(webhook_url, county_id, groups)
        print(f"[sent] one combined webhook call with {len(groups)} groups")
    else:
        print("[info] nothing new to send this run")

    save_state(state)


if __name__ == "__main__":
    cfg_path = os.path.join(BASE_DIR, "config", "hall_county.json")
    webhook = os.environ.get("N8N_WEBHOOK_URL")
    if not webhook:
        print("N8N_WEBHOOK_URL env var missing", file=sys.stderr)
        sys.exit(1)
    check_history = os.environ.get("CHECK_HISTORY", "true").strip().lower() != "false"
    run(cfg_path, webhook, check_history)
