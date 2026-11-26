# -*- coding: utf-8 -*-
"""B4.2 — Bagi 60 kasus ke dua anotator + tandai 15 kasus double-annotation.

Output:
- data/jurisprudence/annotations/assignment_A.csv
- data/jurisprudence/annotations/assignment_B.csv
- data/jurisprudence/annotations/assignment_summary.json

Jalankan:
    python3 scripts/build_cbr_assignment.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]


def _pick(*rels: str) -> Path:
    for r in rels:
        p = ROOT / r
        if p.exists():
            return p
    return ROOT / rels[0]


JURIS = _pick("data/jurisprudence", "knowledge_json/jurisprudence")
ANN_DIR = JURIS / "annotations"
WORKSHEET = ANN_DIR / "worksheet_60.csv"

# Pembagian tema: A = PPh & KUP, B = PPN, kepabeanan, PBB
KLASTER_TO_ANNOTATOR = {
    "pph_badan": "A", "pph_potput": "A", "kup_gugatan": "A",
    "ppn": "B", "kepabeanan_cukai": "B", "pbb": "B",
}
# Jumlah kasus overlap (double-annotation) per klaster; total = 15
OVERLAP_PLAN = {"pph_badan": 3, "pph_potput": 2, "kup_gugatan": 2, "ppn": 3, "kepabeanan_cukai": 2, "pbb": 3}
OVERLAP_POSITIONS = {3: [2, 5, 8], 2: [3, 7]}


def build_assignment(
    rows: List[dict],
    klaster_to_annotator: Dict[str, str] = KLASTER_TO_ANNOTATOR,
    overlap_plan: Dict[str, int] = OVERLAP_PLAN,
) -> dict:
    by_klaster: Dict[str, List[dict]] = {}
    for r in rows:
        by_klaster.setdefault(r["klaster"], []).append(r)

    a_rows: List[dict] = []
    b_rows: List[dict] = []
    overlap_ids: List[str] = []

    for klaster in sorted(by_klaster):
        primary = klaster_to_annotator.get(klaster)
        if primary not in ("A", "B"):
            raise ValueError(f"Klaster tanpa anotator: {klaster}")
        kasus = sorted(by_klaster[klaster], key=lambda x: x["case_id"])
        n_over = int(overlap_plan.get(klaster, 0))
        positions = OVERLAP_POSITIONS.get(n_over, [])
        overlap_ids_klaster = {kasus[i]["case_id"] for i in positions if i < len(kasus)}

        for c in kasus:
            is_overlap = c["case_id"] in overlap_ids_klaster
            if is_overlap:
                overlap_ids.append(c["case_id"])
            base = {
                "case_id": c["case_id"],
                "putusan_nomor": c.get("putusan_nomor"),
                "klaster": klaster,
                "amar_kategori_asal": c.get("amar_kategori_asal"),
                "annotator": primary,
                "peran": "UTAMA",
                "is_overlap": "YA" if is_overlap else "TIDAK",
            }
            target = a_rows if primary == "A" else b_rows
            target.append(base)
            if is_overlap:
                other = "B" if primary == "A" else "A"
                other_target = b_rows if other == "B" else a_rows
                other_target.append({**base, "annotator": other, "peran": "OVERLAP", "is_overlap": "YA"})

    a_rows.sort(key=lambda r: (r["klaster"], r["case_id"]))
    b_rows.sort(key=lambda r: (r["klaster"], r["case_id"]))
    return {
        "A": a_rows,
        "B": b_rows,
        "overlap_ids": sorted(overlap_ids),
        "summary": {
            "total_kasus": len(rows),
            "annotator_A": len(a_rows),
            "annotator_B": len(b_rows),
            "overlap": len(overlap_ids),
            "per_klaster": {k: len(v) for k, v in sorted(by_klaster.items())},
            "estimasi_jam_A": [round(len(a_rows) * 0.33, 1), round(len(a_rows) * 0.67, 1)],
            "estimasi_jam_B": [round(len(b_rows) * 0.33, 1), round(len(b_rows) * 0.67, 1)],
            "target_mingguan_per_orang": 10,
            "minggu_estimasi": round(max(len(a_rows), len(b_rows)) / 10, 1),
        },
    }


def main() -> int:
    with WORKSHEET.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    result = build_assignment(rows)

    ANN_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["case_id", "putusan_nomor", "klaster", "amar_kategori_asal", "annotator", "peran", "is_overlap"]
    for name in ("A", "B"):
        out = ANN_DIR / f"assignment_{name}.csv"
        with out.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows([{k: r.get(k) for k in fields} for r in result[name]])

    summary = result["summary"] | {"overlap_ids": result["overlap_ids"]}
    (ANN_DIR / "assignment_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
