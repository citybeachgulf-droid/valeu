#!/usr/bin/env python3
"""
fill_docx.py

Purpose:
- Replace simple placeholders like {NAME}, {PRICE}, {TOTAL}, {DATE}, etc. inside a DOCX template
  by reading a JSON file and producing a new DOCX file.

Notes:
- This implementation performs string replacement directly on XML parts within the DOCX archive
  (word/document.xml, headers, footers). This approach handles placeholders even if they are
  inside text boxes/shapes that python-docx cannot easily access.
- Placeholders are assumed NOT to be split across XML runs. In your templates, placeholders
  appear as contiguous strings like "{NAME}" inside the same run, which this script supports.

Usage examples:
  Single file:
    python3 fill_docx.py --template "NEW-INVOICE-TEMPLATE (1).docx" \
                         --data sample_invoice.json \
                         --out out-invoice.docx

  Batch (JSON array):
    python3 fill_docx.py --template template.docx \
                         --data batch.json \
                         --out-dir ./outputs --name-field INVOICE_NO

JSON format:
- Single record (object): { "NAME": "Acme", "PRICE": 100, ... }
- Batch (array of objects): [ { ... }, { ... } ]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import zipfile
from typing import Dict, Any, Iterable


XML_TARGETS = (
    "word/document.xml",
    # include common header/footer parts if present
    # We'll also process any part under word/ that endswith .xml (safe and generic)
)


def replace_placeholders_in_xml_bytes(xml_bytes: bytes, mapping: Dict[str, Any]) -> bytes:
    try:
        text = xml_bytes.decode("utf-8")
    except UnicodeDecodeError:
        # Fallback to latin-1 just in case
        text = xml_bytes.decode("latin-1")

    for key, value in mapping.items():
        placeholder = "{" + str(key) + "}"
        replacement = str(value)
        if placeholder in text:
            text = text.replace(placeholder, replacement)

    return text.encode("utf-8")


def fill_one(template_path: str, out_path: str, mapping: Dict[str, Any]) -> None:
    with zipfile.ZipFile(template_path, "r") as zin:
        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)

                if info.filename.startswith("word/") and info.filename.lower().endswith(".xml"):
                    data = replace_placeholders_in_xml_bytes(data, mapping)

                # Preserve original arcname
                zout.writestr(info, data)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fill DOCX placeholders using JSON data.")
    parser.add_argument("--template", required=True, help="Path to the DOCX template file")
    parser.add_argument("--data", required=True, help="Path to JSON file (object or array of objects)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", help="Output DOCX path (for single record)")
    group.add_argument("--out-dir", help="Output directory (for batch records)")
    parser.add_argument(
        "--name-field",
        default=None,
        help="Optional field name to use in filenames for batch mode. If missing, use index.")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)

    template_path = os.path.abspath(args.template)
    data_path = os.path.abspath(args.data)

    if not os.path.exists(template_path):
        print(f"Template not found: {template_path}", file=sys.stderr)
        return 2
    if not os.path.exists(data_path):
        print(f"Data file not found: {data_path}", file=sys.stderr)
        return 2

    with open(data_path, "r", encoding="utf-8") as f:
        try:
            payload = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}", file=sys.stderr)
            return 2

    if args.out:
        # Single mode
        if not isinstance(payload, dict):
            print("For --out, JSON must be an object (single record). Use --out-dir for arrays.", file=sys.stderr)
            return 2
        out_path = os.path.abspath(args.out)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        fill_one(template_path, out_path, payload)
        print(f"Wrote {out_path}")
        return 0

    # Batch mode
    if not isinstance(payload, list):
        print("For --out-dir, JSON must be an array of objects.", file=sys.stderr)
        return 2

    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    count = 0
    for idx, record in enumerate(payload, start=1):
        if not isinstance(record, dict):
            print(f"Skipping item #{idx}: not an object", file=sys.stderr)
            continue

        if args.name_field and args.name_field in record:
            name_value = str(record[args.name_field]).strip().replace(os.sep, "-")
            if not name_value:
                name_value = str(idx)
            filename = f"output-{name_value}.docx"
        else:
            filename = f"output-{idx}.docx"

        out_path = os.path.join(out_dir, filename)
        fill_one(template_path, out_path, record)
        print(f"Wrote {out_path}")
        count += 1

    print(f"Done. Generated {count} file(s) in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

