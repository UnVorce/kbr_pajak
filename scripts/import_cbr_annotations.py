# -*- coding: utf-8 -*-
"""B4.1 — Impor anotasi CBR yang sudah divalidasi ke bentuk kanonik + rebuild indeks.

    python3 scripts/import_cbr_annotations.py --allow-partial
    python3 scripts/import_cbr_annotations.py --strict     # wajib 60/60

Input : data/jurisprudence/annotations/worksheet_60.csv
Output: data/jurisprudence/annotations/annotations_v1.json
        backend/cbr_index.json (rebuild, menyertakan field anotasi)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]

def _pick(*rels: str) -> Path:
    for r in rels:
        p = ROOT / r
        if p.exists():
            return p
    return ROOT / rels[0]


if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_risk_cbr import build_cbr_index  # noqa: E402
from scripts.validate_cbr_annotations import _read, _split, load_taxonomy, validate_rows  # noqa: E402

CSV = _pick("data/jurisprudence", "knowledge_json/jurisprudence") / "annotations" / "worksheet_60.csv"
OUT = _pick("data/jurisprudence", "knowledge_json/jurisprudence") / "annotations" / "annotations_v1.json"
INDEX = ROOT / "backend" / "cbr_index.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="Impor anotasi CBR")
    ap.add_argument("--csv", default=str(CSV))
    ap.add_argument("--allow-partial", action="store_true", help="izinkan impor walau belum 60/60")
    ap.add_argument("--strict", action="store_true", help="wajib 60/60 lengkap")
    args = ap.parse_args()

    rows = _read(Path(args.csv))
    errors, summary = validate_rows(rows, load_taxonomy())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors:
        for e in errors[:10]:
            print(f"  [ERROR] {e['case_id']}: {e['error']}")
        print("Impor dibatalkan: ada error validasi.")
        return 1
    if args.strict and summary["pending"] > 0:
        print(f"Impor dibatalkan: masih {summary['pending']} baris pending (mode strict).")
        return 1
    if not args.allow_partial and summary["pending"] > 0:
        print("Impor dibatalkan: gunakan --allow-partial untuk impor sebagian.")
        return 1

    annotations = {}
    for row in rows:
        if not any((row.get(k) or "").strip() for k in ("jenis_koreksi", "rasio_decidendi")):
            continue
        cid = row["case_id"].strip()
        annotations[cid] = {
            "case_id": cid,
            "klaster": row.get("klaster"),
            "amar_kategori": row.get("amar_kategori_asal"),
            "jenis_koreksi": _split(row.get("jenis_koreksi") or ""),
            "fakta_kunci": _split(row.get("fakta_kunci") or ""),
            "rasio_decidendi": (row.get("rasio_decidendi") or "").strip(),
            "argumen_menang": (row.get("argumen_menang") or "").strip(),
            "bukti_penentu": _split(row.get("bukti_penentu") or ""),
            "rezim_hukum": (row.get("rezim_hukum") or "").strip(),
            "annotator": (row.get("annotator") or "").strip(),
            "reviewer": (row.get("reviewer") or "").strip(),
            "catatan": (row.get("catatan") or "").strip(),
        }

    payload = {
        "version": "1.0",
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "total": len(annotations),
        "annotations": annotations,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    index = build_cbr_index()
    INDEX.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(f"Anotasi tersimpan: {OUT} ({len(annotations)} kasus)")
    print(f"Indeks CBR dibangun ulang: {INDEX} (annotated={index['annotated_cases']}, total={index['total']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
