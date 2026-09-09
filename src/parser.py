"""
Parses tabular data out of the downloaded PDFs into a list of dict rows.

IMPORTANT: on these county PDFs, the printed column header (e.g. "TAX SALE
DATE | BUYER | ... | EXCESS FUNDS") is NOT part of what pdfplumber's
extract_table() returns as row 0 - every row extract_table() gives back is
already a real data row. So the header must be supplied explicitly per
source type (see config "columns") instead of being guessed from the first
extracted row. Guessing from row 1 silently turns a real property record
into fake column names and makes every amount/name lookup fail.
"""

import pdfplumber


def parse_pdf_table(filepath: str, columns: list[str]) -> list[dict]:
    rows: list[dict] = []

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue

            for r in table:
                if not any(cell and cell.strip() for cell in r):
                    continue
                # Skip any stray title/header row that might slip in
                # (e.g. "HALL COUNTY TAX COMMISSIONER - TAX SALE EXCESS FUNDS")
                joined = " ".join((c or "") for c in r).upper()
                if "TAX COMMISSIONER" in joined and "EXCESS FUNDS" in joined:
                    continue

                row_dict = {
                    columns[i]: (r[i] or "").strip()
                    for i in range(min(len(columns), len(r)))
                }
                rows.append(row_dict)

    return rows
