"""
Parses tabular data out of the downloaded PDFs into a list of dict rows.
Assumes the header row appears on page 1 and subsequent pages continue the
same columns without repeating the header (typical for these county PDFs).
"""

import pdfplumber


def parse_pdf_table(filepath: str) -> list[dict]:
    rows: list[dict] = []
    header: list[str] | None = None

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue

            if header is None:
                header = [ (c or "").strip() for c in table[0] ]
                data_rows = table[1:]
            else:
                # Skip a repeated header if this page happens to include one
                first_row_upper = [ (c or "").strip().upper() for c in table[0] ]
                if first_row_upper == [h.upper() for h in header]:
                    data_rows = table[1:]
                else:
                    data_rows = table

            for r in data_rows:
                if not any(cell and cell.strip() for cell in r):
                    continue
                row_dict = { header[i]: (r[i] or "").strip() for i in range(min(len(header), len(r))) }
                rows.append(row_dict)

    return rows
