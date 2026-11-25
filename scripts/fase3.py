# -*- coding: utf-8 -*-
"""Fase 3 — S6 gap detector + putaran crawl (gate G3: kutipan terminal).

Alur:
1. S6 awal: kumpulkan kutipan dari seluruh dokumen, cocokkan dengan registry.
2. Putaran crawl: ambil dokumen yang masih UNRESOLVED dan in-scope (daftar
   eksplisit di FETCH), parse strukturnya.
3. S6 ulang: status baru; sisa UNRESOLVED harus nol (atau tercatat di
   gaps_attempts.json sebagai NOT_FOUND_AT_SOURCE).
4. Tulis data/citations.jsonl, data/gaps.json, data/unresolved_citations.json,
   data/gaps_attempts.json.
5. Konsolidasi ulang rantai di config/consolidation.yaml (teks terbaru).

Pemakaian:
    python3 scripts/fase3.py            # crawl + konsolidasi
    python3 scripts/fase3.py --skip-fetch
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from scripts.fase1_korpus import fetch_new  # noqa: E402
from src.consolidate import consolidate  # noqa: E402
from src.gaps import (collect, load_registry, priority,  # noqa: E402
                      relations_from_titles, write_outputs)
from src.parse_structure import parse_document  # noqa: E402

DOCS = ROOT / "data" / "documents"
TEXT = ROOT / "data" / "text"
CONS = ROOT / "data" / "consolidated"
ATTEMPTS = ROOT / "data" / "gaps_attempts.json"
CONFIG = ROOT / "config" / "consolidation.yaml"

# Dokumen UNRESOLVED yang diambil pada putaran crawl Fase 3.
# (document_id, URL detail BPK relatif, catatan)
FETCH = [
    ("PERPU-2008-5", "/Details/53229/perpu-no-5-tahun-2008",
     "teks Perubahan Keempat KUP (UU 16/2009 hanya penetapan)"),
    ("PMK-2025-11", "/Details/313574/pmk-no-11-tahun-2025",
     "perubahan pertama PMK 81/2024 (PPN inti)"),
    ("PP-2010-94", "/Details/5119/pp-no-94-tahun-2010",
     "penghitungan PPh Kena Pajak & pelunasan PPh tahun berjalan"),
    ("PP-2019-45", "/Details/110284/pp-no-45-tahun-2019",
     "perubahan PP 94/2010"),
    ("PP-2015-18", "/Details/5582/pp-no-18-tahun-2015",
     "fasilitas PPh penanaman modal bidang usaha tertentu"),
    ("PP-2016-9", "/Details/5730/pp-no-9-tahun-2016",
     "perubahan PP 18/2015"),
    ("PP-2000-20", "/Details/53196/pp-no-20-tahun-2000",
     "perlakuan perpajakan KAPET"),
    ("PP-2000-147", "/Details/54032/pp-no-147-tahun-2000",
     "perubahan PP 20/2000"),
    ("PP-2022-50", "/Details/232952/pp-no-50-tahun-2022",
     "tata cara pelaksanaan hak & pemenuhan kewajiban perpajakan"),
    ("PP-2015-40", "/Details/5608/pp-no-40-tahun-2015",
     "PPN air bersih dibebaskan"),
    ("PP-2015-81", "/Details/5659/pp-no-81-tahun-2015",
     "PPN/PPnBM barang strategis dibebaskan"),
    ("PMK-2020-96", "/Details/143651/pmk-no-96pmk0102020",
     "perubahan PMK 11/PMK.010/2020 (fasilitas PPh)"),
    # Putaran 2: kutipan baru yang muncul dari dokumen putaran 1
    ("PMK-2024-131", "/Details/311485/pmk-no-131-tahun-2024",
     "perlakuan PPN impor/penyerahan BKP & JKP (nilai lain 11/12)"),
    ("PMK-2023-48", "/Details/248649/pmk-no-48-tahun-2023",
     "PPh/PPN emas perhiasan & emas batangan (diubah PMK 11/2025)"),
    ("PMK-2023-41", "/Details/247419/pmk-no-41-tahun-2023",
     "PPN penyerahan agunan yang diambil alih kreditur"),
    ("PMK-2024-79", "/Details/306437/pmk-no-79-tahun-2024",
     "perlakuan perpajakan dalam Kerja Sama Operasi (KSO)"),
    ("PP-2021-9", "/Details/161839/pp-no-9-tahun-2021",
     "perlakuan perpajakan kemudahan berusaha (mengubah PP 94/2010)"),
]

# Gap yang tidak ditemukan di pencarian BPK (tindak lanjut manual di jdih.kemenkeu.go.id).
MANUAL_GAPS: dict = {
    "PMK-2008-253": {
        "reason": "PMK 253/PMK.03/2008 (PPh 22 barang sangat mewah) tidak ditemukan di BPK; perlu unduh manual di jdih.kemenkeu.go.id.",
        "attempts": [{"source": "peraturan.bpk.go.id", "query": "PMK 253 2008", "result": "tidak terindeks"}],
    },
}


def load_docs() -> list:
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(DOCS.glob("*.json"))]


def run_s6(tag: str) -> tuple:
    docs = load_docs()
    reg = load_registry(DOCS)
    attempts = {}
    if ATTEMPTS.exists():
        attempts = json.loads(ATTEMPTS.read_text(encoding="utf-8")).get("documents", {})
    citations, agg = collect(docs, reg, attempts)
    status = Counter(a["status"] for a in agg.values())
    print(f"\n== S6 {tag} ==")
    print(f"  dokumen: {len(docs)} | kutipan: {len(citations)} | "
          f"dokumen dikutip: {len(agg)}")
    print("  status: " + ", ".join(f"{k}={v}" for k, v in sorted(status.items())))
    unres = [a for a in agg.values() if a["status"] == "UNRESOLVED"]
    unres.sort(key=priority, reverse=True)
    if unres:
        print(f"  UNRESOLVED ({len(unres)}):")
        for a in unres[:20]:
            print(f"    - {a['document_id']:18} occ={a['occurrences']:3} "
                  f"by={a['citation_count']} [{','.join(a['roles'])}]")
    return citations, agg, docs, reg


def crawl() -> list:
    """Ambil dokumen FETCH yang belum ada; kembalikan id yang baru diambil."""
    records: list = []
    new_ids = []
    for doc_id, url, note in FETCH:
        if (DOCS / f"{doc_id}.json").exists() and (TEXT / f"{doc_id}.txt").exists():
            print(f"  [SUDAH ADA] {doc_id} — lewati")
            continue
        fetch_new(doc_id, url, note, "Pemerintah", records)
        if (DOCS / f"{doc_id}.json").exists() and (TEXT / f"{doc_id}.txt").exists():
            new_ids.append(doc_id)
    return new_ids


def parse_new(ids: list) -> None:
    for doc_id in ids:
        path = DOCS / f"{doc_id}.json"
        txt = TEXT / f"{doc_id}.txt"
        if not path.exists() or not txt.exists():
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        r = parse_document(doc_id, txt.read_text(encoding="utf-8", errors="replace"))
        d["preamble"] = r["preamble"]
        d["penjelasan"] = r["penjelasan"]
        d["penjelasan_articles"] = r["penjelasan_articles"]
        d["provisions"] = r["provisions"]
        d["structure"] = r["structure"]
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        n = sum(1 for p in r["provisions"] if p["level"] == "PASAL")
        print(f"  [PARSE] {doc_id}: {r['structure']} | {n} pasal | "
              f"{len(r['provisions'])} provisions")


def write_attempts() -> None:
    data = {"documents": {}, "manual_gaps": MANUAL_GAPS}
    if ATTEMPTS.exists():
        data["documents"] = json.loads(ATTEMPTS.read_text(encoding="utf-8")).get(
            "documents", {})
    # Dokumen yang tetap tidak ada setelah crawl = tidak ditemukan di sumber.
    for doc_id, info in MANUAL_GAPS.items():
        if not (DOCS / f"{doc_id}.json").exists():
            data["documents"][doc_id] = info
        else:
            data["documents"].pop(doc_id, None)
    for doc_id, url, note in FETCH:
        if not (DOCS / f"{doc_id}.json").exists():
            data["documents"][doc_id] = {
                "reason": f"tidak ditemukan / gagal diambil: {note}",
                "attempts": [{"source": "peraturan.bpk.go.id", "url": url,
                              "result": "gagal"}],
            }
    ATTEMPTS.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")


def run_consolidation() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    CONS.mkdir(parents=True, exist_ok=True)
    print("\n== Konsolidasi ulang ==")
    for target, chain in cfg.get("chains", {}).items():
        if not (DOCS / f"{target}.json").exists():
            print(f"  [LEWATI] {target}: dokumen target tidak ada")
            continue
        res = consolidate(target, chain or [], DOCS, CONS, TEXT)
        print(f"  {target:16} applied={res['applied_count']:3} "
              f"unparsed={res['unparsed_count']:3} "
              f"pasal={len(res['provisions'])}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-fetch", action="store_true",
                    help="jangan crawl; hanya S6 + konsolidasi")
    args = ap.parse_args()

    run_s6("awal")

    if not args.skip_fetch:
        print("\n== Putaran crawl ==")
        new_ids = crawl()
        if new_ids:
            print("\n== Parse dokumen baru ==")
            parse_new(new_ids)

    write_attempts()
    citations, agg, docs, reg = run_s6("akhir")

    rels = relations_from_titles(docs, reg)
    write_outputs(citations, agg, rels, ROOT / "data")
    print(f"\n  relasi judul: {len(rels)}")
    print("  output: data/citations.jsonl, data/gaps.json, "
          "data/unresolved_citations.json, data/gaps_attempts.json")

    run_consolidation()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
