# -*- coding: utf-8 -*-
"""CLI review manusia prioritas tinggi (Gate G4):
  python3 scripts/fase4_review.py export   -> data/review/priority_review.csv
  python3 scripts/fase4_review.py apply    -> terapkan keputusan ke data/legal_rules.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.review import apply_review_csv, export_priority_review_csv  # noqa: E402

CHUNKS = ROOT / "data" / "chunks" / "pending" / "all_t2_chunks.jsonl"
REV_QUEUE = ROOT / "data" / "review" / "review_queue.jsonl"
LEGAL_RULES = ROOT / "data" / "legal_rules.jsonl"
OUT_CSV = ROOT / "data" / "review" / "priority_review.csv"
APPLY_REPORT = ROOT / "data" / "review" / "review_apply_report.json"


def _load_chunks() -> dict:
    out = {}
    for line in CHUNKS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            out[c["chunk_id"]] = c
    return out


def _load_jsonl(path: Path) -> list:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["export", "apply"])
    ap.add_argument("--csv", default=str(OUT_CSV))
    args = ap.parse_args()

    chunks_by_id = _load_chunks()
    csv_path = Path(args.csv)

    if args.cmd == "export":
        rev_items = _load_jsonl(REV_QUEUE)
        rep = export_priority_review_csv(rev_items, chunks_by_id, csv_path)
        print("Ekspor priority review CSV selesai:", json.dumps(rep, ensure_ascii=False))
        return 0

    rules = _load_jsonl(LEGAL_RULES)
    new_rules, rep = apply_review_csv(csv_path, rules, chunks_by_id)
    with LEGAL_RULES.open("w", encoding="utf-8") as f:
        for r in new_rules:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    APPLY_REPORT.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Apply review selesai:", json.dumps(rep, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
