"""
Sends the processed, grouped payload to the n8n webhook.
"""

import requests


def send_grouped_to_n8n(webhook_url: str, county_id: str, groups: list[dict]) -> None:
    """
    groups: list of {"group_name": str, "source_type": str, "records": [...]}
    Sent as ONE webhook call - n8n loops through 'groups' itself, no repeated
    calls per source.
    """
    payload = {
        "county_id": county_id,
        "groups": groups,
    }
    resp = requests.post(webhook_url, json=payload, timeout=30)
    resp.raise_for_status()
