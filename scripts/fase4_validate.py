# -*- coding: utf-8 -*-
"""CLI S8 — Validasi hasil LLM dari Colab (data/llm_results/*.jsonl) ->
data/legal_rules.jsonl + data/review/review_queue.jsonl + data/validation/validation_report.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.validate import validate_staging_results  # noqa: E402

CHUNKS = ROOT / "data" / "chunks" / "pending" / "all_t2_chunks.jsonl"
LLM_DIR = ROOT / "data" / "llm_results"
OUT_RULES = ROOT / "data" / "legal_rules.jsonl"
OUT_REVIEW = ROOT / "data" / "review" / "review_queue.jsonl"
OUT_REPORT = ROOT / "data" / "validation" / "validation_report.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", nargs="*", help="file JSONL staging tertentu (default: semua di data/llm_results/*.jsonl)")
    args = ap.parse_args()

    chunks_by_id = {}
    for line in CHUNKS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            chunks_by_id[c["chunk_id"]] = c

    files = [Path(p) for p in args.input] if args.input else sorted(LLM_DIR.glob("*.jsonl"))
    results = []
    for fp in files:
        for line in fp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                results.append(json.loads(line))

    if not results:
        print("Belum ada file hasil LLM di data/llm_results/*.jsonl")
        return 0

    legal_rules, review_queue, report = validate_staging_results(results, chunks_by_id)
    OUT_REVIEW.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)

    with OUT_RULES.open("w", encoding="utf-8") as f:
        for r in legal_rules:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with OUT_REVIEW.open("w", encoding="utf-8") as f:
        for q in review_queue:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Validasi S8 selesai:", json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
