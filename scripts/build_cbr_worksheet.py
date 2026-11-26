# -*- coding: utf-8 -*-
"""B4.1 — Bangun worksheet anotasi CBR 60 kasus (10 per klaster, stratifikasi amar).

Output:
- `data/jurisprudence/annotations/worksheet_60.csv` (siap diisi Pilar 3)
- `data/jurisprudence/annotations/worksheet_60_meta.json`

Jalankan:
    python3 scripts/build_cbr_worksheet.py
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
OUT_DIR = JURIS / "annotations"
TAXONOMY = ROOT / "config" / "cbr_taxonomy.json"

PER_KLASTER = 10
# Kuota amar per klaster; kekurangan diisi dari sisa kasus.
QUOTA = {"TOLAK": 3, "KABUL_SEBAGIAN": 3, "KABUL_SELURUHNYA": 4}

COLUMNS = [
    "case_id", "putusan_nomor", "klaster", "jenis_pajak", "tahun_pajak", "amar_kategori_asal",
    "pokok_sengketa", "pertimbangan_majelis",
    "jenis_koreksi", "fakta_kunci", "rasio_decidendi", "argumen_menang", "bukti_penentu",
    "rezim_hukum", "quotes_json", "catatan", "annotator", "reviewer",
]


def _norm(s: str) -> str:
    return " ".join((s or "").split())


def select_cases(cases: List[dict], per_klaster: int = PER_KLASTER) -> List[dict]:
    by_klaster: Dict[str, List[dict]] = {}
    for c in cases:
        by_klaster.setdefault(c.get("klaster") or "lain", []).append(c)

    selected: List[dict] = []
    for klaster in sorted(by_klaster):
        bucket = sorted(by_klaster[klaster], key=lambda c: c.get("case_id") or "")
        by_amar: Dict[str, List[dict]] = {}
        for c in bucket:
            by_amar.setdefault(c.get("amar_kategori") or "LAINNYA", []).append(c)

        taken: List[dict] = []
        taken_ids = set()
        for amar, quota in QUOTA.items():
            for c in by_amar.get(amar, [])[:quota]:
                taken.append(c)
                taken_ids.add(c["case_id"])
        for c in bucket:
            if len(taken) >= per_klaster:
                break
            if c["case_id"] not in taken_ids:
                taken.append(c)
                taken_ids.add(c["case_id"])
        selected.extend(taken[:per_klaster])
    return selected


def main() -> int:
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(JURIS.glob("*.json"))]
    tax = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    selected = select_cases(cases)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / "worksheet_60.csv"
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for c in selected:
            w.writerow({
                "case_id": c.get("case_id"),
                "putusan_nomor": c.get("putusan_nomor"),
                "klaster": c.get("klaster"),
                "jenis_pajak": c.get("jenis_pajak"),
                "tahun_pajak": c.get("tahun_pajak"),
                "amar_kategori_asal": c.get("amar_kategori"),
                "pokok_sengketa": _norm(c.get("pokok_sengketa")),
                "pertimbangan_majelis": _norm(c.get("pertimbangan_majelis")),
                "jenis_koreksi": "", "fakta_kunci": "", "rasio_decidendi": "",
                "argumen_menang": "", "bukti_penentu": "", "rezim_hukum": "",
                "quotes_json": "", "catatan": "", "annotator": "", "reviewer": "",
            })

    by_klaster: Dict[str, int] = {}
    by_amar: Dict[str, int] = {}
    for c in selected:
        by_klaster[c.get("klaster")] = by_klaster.get(c.get("klaster"), 0) + 1
        by_amar[c.get("amar_kategori")] = by_amar.get(c.get("amar_kategori"), 0) + 1

    meta = {
        "total": len(selected),
        "per_klaster": by_klaster,
        "per_amar": by_amar,
        "taxonomy_version": tax.get("version"),
        "worksheet": str(out_csv.relative_to(ROOT)),
    }
    (OUT_DIR / "worksheet_60_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
