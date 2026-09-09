"""
Scraper module.
Given a county config, visits the relevant pages, locates the target PDF
links (tax sale listing, excess funds list, unclaimed refunds list),
and downloads any file whose content hash has not been seen before.
"""

import hashlib
import os
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ExcessFundsBot/1.0)"
}


def fetch_html(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def find_link_by_keywords(soup: BeautifulSoup, base_url: str, keywords: list) -> str | None:
    """Return the first href (absolute) whose visible text OR filename matches any keyword."""
    keywords_upper = [k.upper() for k in keywords]
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.lower().endswith((".pdf", ".xls", ".xlsx")):
            continue
        text = a.get_text(strip=True).upper()
        filename = href.split("/")[-1].upper()
        combined = text + " " + filename
        if any(k in combined for k in keywords_upper):
            return urljoin(base_url, href)
    return None


def find_all_target_links(config: dict) -> dict:
    """Visit tax_sale and excess_funds pages, return dict of source_type -> pdf_url (or None)."""
    base_url = config["base_url"]
    links = {}

    tax_sale_soup = fetch_html(config["pages"]["tax_sale"])
    links["tax_sale_listing"] = find_link_by_keywords(
        tax_sale_soup, base_url, config["link_keywords"]["tax_sale_listing"]
    )

    excess_soup = fetch_html(config["pages"]["excess_funds"])
    links["excess_funds_list"] = find_link_by_keywords(
        excess_soup, base_url, config["link_keywords"]["excess_funds_list"]
    )
    # unclaimed refunds link usually lives in the site-wide footer, present on this page too
    links["unclaimed_refunds"] = find_link_by_keywords(
        excess_soup, base_url, config["link_keywords"]["unclaimed_refunds"]
    )

    return links


def download_file(url: str, dest_dir: str) -> tuple[str, str]:
    """Download file, return (local_path, sha256_hash)."""
    os.makedirs(dest_dir, exist_ok=True)
    filename = re.sub(r"[^A-Za-z0-9_.-]", "_", url.split("/")[-1]) or "download.pdf"
    local_path = os.path.join(dest_dir, filename)

    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()

    with open(local_path, "wb") as f:
        f.write(resp.content)

    file_hash = hashlib.sha256(resp.content).hexdigest()
    return local_path, file_hash
