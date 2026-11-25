# -*- coding: utf-8 -*-
"""Tahap 4B — Bangkitkan chunks T2_RULE + draf gold_standard (36 contoh lintas domain)."""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.chunking import build_all_chunks  # noqa: E402

SCOPE = ROOT / "data" / "scope_manifest.jsonl"
DOCS = ROOT / "data" / "documents"
CONS = ROOT / "data" / "consolidated"
PERDA = ROOT / "data" / "perda"
CHUNKS_DIR = ROOT / "data" / "chunks" / "pending"
MANIFEST = ROOT / "data" / "chunks" / "chunk_manifest.json"
GOLD_JSONL = ROOT / "data" / "gold_standard_template.jsonl"
GOLD_CSV = ROOT / "data" / "gold_standard_review.csv"

GOLD_PICKS = [
    # A2_PPH_BADAN: tarif PPh badan & WP OP, tax holiday, penyusutan, DER, promosi, Pilar Dua
    ("UU-1983-7", "17"), ("UU-1983-7", "6"), ("UU-1983-7", "18"),
    ("PP-2022-55", "56"), ("PMK-2020-130", "3"), ("PMK-2019-128", "2"),
    ("PMK-2023-72", "3"), ("PMK-2015-169", "2"), ("PMK-2024-136", "4"),
    # B_PPN: tarif 11%/12%, PKP 4.8M, dibebaskan, nilai lain 11/12, PPnBM
    ("UU-1983-8", "7"), ("UU-1983-8", "16B"), ("PMK-2010-68", "1"),
    ("PMK-2024-131", "2"), ("PP-2022-49", "4"), ("PP-2019-73", "4"),
    # C_PBB_HKPD & PERDA_PDRD
    ("UU-1985-12", "5"), ("UU-2022-1", "41"), ("PP-2023-35", "3"),
    ("PERDA-PROV-DKI-JAKARTA-2024-1", "7"), ("PERDA-KOTA-SURABAYA-2023-7", "10"),
    # D_ADMIN_SANKSI: NPWP, SPT, sanksi, pembetulan/keberatan, pemeriksaan, penagihan, PPSP, Pengadilan Pajak
    ("UU-1983-6", "7"), ("UU-1983-6", "8"), ("UU-1983-6", "13"),
    ("PP-2022-50", "4"), ("PMK-2024-118", "3"), ("PMK-2025-15", "4"),
    ("PMK-2026-28", "3"), ("UU-1997-19", "8"), ("UU-2002-14", "35"),
    # PPH_OP_POTPUT, PPH_FINAL_SEKTOR, FASILITAS_SEKTOR, KEPABEANAN_CUKAI
    ("PMK-2015-141", "1"), ("PP-2023-58", "2"), ("PMK-2025-112", "3"),
    ("PP-2008-51", "3"), ("PP-2021-91", "2"), ("PMK-2020-237", "3"),
    ("UU-1995-10", "10"), ("UU-1995-11", "4"),
]


def main() -> int:
    rows = [json.loads(l) for l in SCOPE.read_text(encoding="utf-8").splitlines() if l.strip()]
    chunks = build_all_chunks(rows, DOCS, CONS, PERDA)

    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    by_dom: dict[str, list[dict]] = defaultdict(list)
    for ch in chunks:
        by_dom[ch["domain"]].append(ch)

    for dom, dchunks in sorted(by_dom.items()):
        p = CHUNKS_DIR / f"{dom}.jsonl"
        with p.open("w", encoding="utf-8") as f:
            for c in dchunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

    all_p = CHUNKS_DIR / "all_t2_chunks.jsonl"
    with all_p.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    table_chunks = [c for c in chunks if (c.get("context") or {}).get("is_table")]
    TABLE_P = CHUNKS_DIR / "tables_for_review.jsonl"
    with TABLE_P.open("w", encoding="utf-8") as f:
        for c in table_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    total_chars = sum(c["char_len"] for c in chunks)
    est_tokens_in = total_chars // 3  # ~3 chars/token bahasa Indonesia
    manifest = {
        "total_chunks": len(chunks),
        "total_chars": total_chars,
        "est_input_tokens": est_tokens_in,
        "by_domain": {k: len(v) for k, v in sorted(by_dom.items())},
        "avg_chunk_chars": round(total_chars / len(chunks), 1) if chunks else 0,
        "table_chunks": len(table_chunks),
        "files": {k: f"data/chunks/pending/{k}.jsonl" for k in sorted(by_dom)},
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Pilih 36 contoh gold standard (ambil chunk pertama yang cocok tiap (doc_id, pasal))
    gold = []
    by_doc_pasal = defaultdict(list)
    for c in chunks:
        p_num = c["context"]["pasal_induk"].replace("Pasal ", "")
        by_doc_pasal[(c["document_id"], p_num)].append(c)

    for did, pno in GOLD_PICKS:
        cands = by_doc_pasal.get((did, pno))
        if cands:
            gold.append(cands[0])

    with GOLD_JSONL.open("w", encoding="utf-8") as f:
        for c in gold:
            f.write(json.dumps({
                "chunk_id": c["chunk_id"],
                "domain": c["domain"],
                "document_id": c["document_id"],
                "source_locator": c["source_locator"],
                "context": c.get("context") or {},
                "text": c["text"],
                "expected_rules": [],  # diisi / diverifikasi manusia
            }, ensure_ascii=False) + "\n")

    with GOLD_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chunk_id", "domain", "document_id", "source_locator",
                    "is_table", "text", "rule_type", "rate_or_value", "condition",
                    "obligation_or_sanction", "exception", "deadline",
                    "source_quote", "verified_by_human"])
        for c in gold:
            w.writerow([c["chunk_id"], c["domain"], c["document_id"],
                        c["source_locator"], (c.get("context") or {}).get("is_table", False),
                        c["text"], "", "", "", "", "", "", "", "PENDING"])

    print(f"[CHUNKS] total={len(chunks)} | est_input_tokens={est_tokens_in:,} | avg_chars={manifest['avg_chunk_chars']}")
    print("  by_domain:", manifest["by_domain"])
    print(f"[GOLD] template={len(gold)} chunk -> {GOLD_JSONL.name} & {GOLD_CSV.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
