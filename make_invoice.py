#!/usr/bin/env python3
"""
make_invoice.py

Simple CLI to generate an invoice DOCX from the template by providing
client name, price, and optional date (defaults to today).

Example:
  python3 make_invoice.py --name "Acme Corp" --price 199.5 \
    --template "/workspace/NEW-INVOICE-TEMPLATE (1).docx" \
    --out "/workspace/invoice-Acme.docx"

Date format input: YYYY-MM-DD (optional). If missing, uses today's date.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from typing import Iterable


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an invoice DOCX from inputs.")
    parser.add_argument("--name", required=True, help="Client name")
    parser.add_argument("--price", required=True, help="Price/amount (string or number)")
    parser.add_argument("--invoice-no", default=None, help="Optional invoice number")
    parser.add_argument("--date", default=None, help="Invoice date YYYY-MM-DD; defaults to today")
    parser.add_argument("--template", required=True, help="Path to DOCX template")
    parser.add_argument("--out", required=True, help="Output DOCX path")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)

    # Determine date
    if args.date:
        try:
            date_str = dt.date.fromisoformat(args.date).isoformat()
        except ValueError:
            print("Invalid --date. Expected YYYY-MM-DD.", file=sys.stderr)
            return 2
    else:
        date_str = dt.date.today().isoformat()

    # Build data mapping expected by the template
    mapping = {
        "NAME": args.name,
        "PRICE": str(args.price),
        "TOTAL": str(args.price),
        "DATE": date_str,
    }
    if args.invoice_no:
        mapping["INVOICE_NO"] = args.invoice_no

    # Write a temporary JSON and call fill_docx.py
    tmp_json = os.path.abspath("/workspace/_tmp_invoice.json")
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False)

    cmd = [
        sys.executable,
        os.path.abspath("/workspace/fill_docx.py"),
        "--template", os.path.abspath(args.template),
        "--data", tmp_json,
        "--out", os.path.abspath(args.out),
    ]

    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f"Error generating invoice: {e}", file=sys.stderr)
        return e.returncode or 1
    finally:
        try:
            os.remove(tmp_json)
        except OSError:
            pass

    print(f"Invoice written to {os.path.abspath(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

