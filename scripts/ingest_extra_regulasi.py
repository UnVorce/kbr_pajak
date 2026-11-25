# -*- coding: utf-8 -*-
"""Ingest 4 PDF pajak baru dari download-pdf/regulasi/ ke korpus kanonik.

- 2024pmkeuangan118.pdf     -> PMK-2024-118 (Pembetulan, Keberatan, Pembatalan)
- 2024pmkeuangan136.pdf     -> PMK-2024-136 (Pajak Minimum Global / Pilar Dua)
- PMK Nomor 2 Tahun 2010.pdf -> PMK-2010-2   (Biaya Promosi; sort=True untuk urutan blok)
- 2025pmkeuangan114.pdf     -> PMK-2025-114 (Bantuan/Sumbangan/Zakat/Hibahan + BPK meta)

Catatan: UU Nomor 27 Tahun 2026.pdf (Pelindungan Ketenagakerjaan) sengaja dilewati
karena bukan regulasi pajak.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fase1_korpus import canon_doc  # noqa: E402
from scripts.ingest_manual import fetch_bpk_meta  # noqa: E402
from src.parse_structure import parse_document  # noqa: E402
from src.textutil import cut_penjelasan, split_pasal  # noqa: E402

REG_DIR = ROOT / "download-pdf" / "regulasi"
DOCS = ROOT / "data" / "documents"
TEXT = ROOT / "data" / "text"

EXTRA = [
    ("2024pmkeuangan118.pdf", "PMK-2024-118", "PMK", 2024, None, False, {
        "judul": ("Peraturan Menteri Keuangan Nomor 118 Tahun 2024 tentang Tata Cara "
                  "Pembetulan, Keberatan, Pengurangan, Penghapusan, dan Pembatalan "
                  "di Bidang Perpajakan"),
        "status_sumber": "Berlaku",
        "source_urls": [{"source": "jdih.kemenkeu.go.id", "url": "https://jdih.kemenkeu.go.id"}],
    }),
    ("2024pmkeuangan136.pdf", "PMK-2024-136", "PMK", 2024, None, False, {
        "judul": ("Peraturan Menteri Keuangan Nomor 136 Tahun 2024 tentang Pengenaan "
                  "Pajak Minimum Global Berdasarkan Kesepakatan Internasional"),
        "status_sumber": "Berlaku",
        "source_urls": [{"source": "jdih.kemenkeu.go.id", "url": "https://jdih.kemenkeu.go.id"}],
    }),
    ("PMK Nomor 2 Tahun 2010.pdf", "PMK-2010-2", "PMK", 2010, None, True, {
        "judul": ("Peraturan Menteri Keuangan Nomor 02/PMK.03/2010 tentang Biaya Promosi "
                  "yang Dapat Dikurangkan dari Penghasilan Bruto"),
        "status_sumber": "Berlaku",
        "source_urls": [{"source": "jdih.kemenkeu.go.id", "url": "https://jdih.kemenkeu.go.id"}],
    }),
    ("2025pmkeuangan114.pdf", "PMK-2025-114", "PMK", 2025,
     "/Details/342503/pmk-no-114-tahun-2025", False, {}),
]


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    TEXT.mkdir(parents=True, exist_ok=True)
    for fname, did, jenis, tahun, bpk_rel, sort_blocks, fb in EXTRA:
        pdf_path = REG_DIR / fname
        if not pdf_path.exists():
            print(f"[HILANG] {pdf_path}")
            continue
        doc = fitz.open(pdf_path)
        pages = [pg.get_text(sort=sort_blocks) for pg in doc]
        n_pages = len(pages)
        avg = (sum(len(p) for p in pages) / n_pages) if n_pages else 0.0
        text = "\n\n".join(pages)
        (TEXT / f"{did}.txt").write_text(text, encoding="utf-8")

        batang, _ = cut_penjelasan(text)
        _, arts, _ = split_pasal(batang)
        parsed = parse_document(did, text)

        meta = fetch_bpk_meta(did, bpk_rel)
        judul = meta.get("judul") or fb.get("judul") or ""
        src_urls = meta.get("source_urls") or fb.get("source_urls") or []
        extra = {
            "status_sumber": meta.get("status_sumber") or fb.get("status_sumber"),
            "source_urls": src_urls,
            "structure": parsed["structure"],
            "preamble": parsed["preamble"],
        }
        for k in ("tanggal_penetapan", "tanggal_pengundangan",
                  "tanggal_berlaku_sumber", "sumber_publikasi", "subjek_sumber"):
            if meta.get(k):
                extra[k] = meta[k]

        rec = canon_doc(
            did, jenis, tahun, judul, arts,
            {"origin": "manual_download", "file": fname, "pages": n_pages},
            extra=extra,
        )
        rec["penjelasan"] = parsed["penjelasan"]
        rec["penjelasan_articles"] = parsed["penjelasan_articles"]
        rec["provisions"] = parsed["provisions"]
        rec["structure"] = parsed["structure"]
        rec["quality"]["ocr_suspect"] = (avg < 60)
        rec["quality"]["zero_pasal"] = (len(parsed["provisions"]) == 0 and len(arts) == 0)
        (DOCS / f"{did}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

        n_pas = sum(1 for p in parsed["provisions"] if p["level"] == "PASAL")
        print(f"[OK] {did:14} {parsed['structure']:12} pasal={n_pas:3} "
              f"prov={len(parsed['provisions']):4} pages={n_pages:3} avg={avg:4.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
