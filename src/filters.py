"""
Filters parsed records by minimum excess-fund amount (when asked) and splits
them into 'person' vs 'company/other' owner records.
"""

import re

COMPANY_KEYWORDS = [
    "LLC", "L.L.C", "INC", "INC.", "CORP", "CORPORATION", "CO.", "COMPANY",
    "LTD", "LP", "LLP", "PC", "P.C", "TRUST", "TRUSTEE", "ESTATE", "BANK",
    "GROUP", "HOLDINGS", "PARTNERS", "PROPERTIES", "INVESTMENTS", "ENTERPRISES",
    "CONSTRUCTION", "SERVICES", "SOLUTIONS", "FOUNDATION", "ASSOCIATES",
    "FIRM", "LAW OFFICE", "AUTO", "BROKERS", "PORTFOLIO", "DEV & CONST",
    "DEPARTMENT OF", "MORTGAGE", "FUND", "CAPITAL", "REALTY", "MANAGEMENT"
]


def is_company(name: str) -> bool:
    if not name:
        return False
    upper = name.upper()
    return any(kw in upper for kw in COMPANY_KEYWORDS)


def parse_amount(raw: str) -> float:
    if not raw:
        return 0.0
    cleaned = re.sub(r"[^0-9.]", "", raw)
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def split_records(
    records: list[dict],
    name_field: str,
    amount_field: str | None = None,
    min_amount: float | None = None,
) -> tuple[list[dict], list[dict]]:
    """Return (persons, others). If amount_field + min_amount are both given,
    rows below min_amount are dropped first; otherwise every record is kept
    and simply grouped into person vs company/LLC/other."""
    persons, others = [], []

    for row in records:
        if amount_field:
            amt = parse_amount(row.get(amount_field, ""))
            row["_amount"] = amt
            if min_amount is not None and amt < min_amount:
                continue

        name = row.get(name_field, "")

        if is_company(name):
            others.append(row)
        else:
            persons.append(row)

    return persons, others
