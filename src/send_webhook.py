"""
Sends the processed, ordered payload (persons first, then companies/other)
to the n8n webhook for downstream one-by-one processing.
"""

import requests


def send_to_n8n(
    webhook_url: str,
    county_id: str,
    source_type: str,
    persons: list[dict],
    companies: list[dict],
    raw_records: list[dict] | None = None,
) -> None:
    payload = {
        "county_id": county_id,
        "source_type": source_type,
        "persons": persons,
        "companies_or_other": companies,
        "raw_records": raw_records or [],
    }
    resp = requests.post(webhook_url, json=payload, timeout=30)
    resp.raise_for_status()
