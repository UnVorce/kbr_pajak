# -*- coding: utf-8 -*-
"""Fase 3B (Jalur 1) — Crawl otomatis 47 regulasi tambahan dari JDIH BPK.

Pengaman:
- Resumable: melewati dokumen yang sudah ada JSON & TXT-nya.
- Anti salah dokumen: wajib lolos verifikasi page_document_id(meta) == doc_id.
- Ekstraksi PDF sadar-2-kolom (extract_pdf_text(..., col_aware=True)) + S4 parse.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fase1_korpus import (BPK, JENIS_LABEL, OUT_TMP,  # noqa: E402
                                  bpk_search, canon_doc, http_get, split_id)
from scripts.ingest_manual import extract_pdf_text  # noqa: E402
from src.crawl import BpkDetailParser, page_document_id, parse_date_id  # noqa: E402
from src.parse_structure import parse_document  # noqa: E402
from src.textutil import cut_penjelasan, split_pasal  # noqa: E402

DOCS = ROOT / "data" / "documents"
TEXT = ROOT / "data" / "text"
LOG = ROOT / "data" / "fase3b_crawl_log.json"

# (doc_id, must_contain_hint)
TARGETS = [
    ("PMK-2015-141", "23"),
    ("PMK-2023-72", "Penyusutan"),
    ("PMK-2015-169", "Modal"),
    ("PMK-2009-105", "Piutang"),
    ("PMK-2010-57", "Piutang"),
    ("PMK-2015-207", "Piutang"),
    ("PMK-2015-90", "Mewah"),
    ("PMK-2019-92", "Mewah"),
    ("PMK-2019-35", "Bentuk Usaha Tetap"),
    ("PMK-2022-69", "Finansial"),
    ("PP-2008-51", "Konstruksi"),
    ("PP-2009-40", "Konstruksi"),
    ("PP-2022-9", "Konstruksi"),
    ("PP-2021-91", "Obligasi"),
    ("PP-2009-15", "Koperasi"),
    ("PP-1994-41", "Saham"),
    ("PP-1997-14", "Saham"),
    ("PP-2000-132", "Undian"),
    ("UU-2002-14", "Pengadilan Pajak"),
    ("PMK-2014-111", "Konsultan"),
    ("PMK-2022-175", "Konsultan"),
    ("PMK-2022-71", "Jasa Kena Pajak"),
    ("PP-2019-73", "Kendaraan"),
    ("PP-2021-74", "Kendaraan"),
    ("PMK-2021-96", "Mewah"),
    ("PMK-2023-15", "Mewah"),
    ("PP-2020-61", "Mewah"),
    ("PMK-2023-143", "Rokok"),
    ("PP-2021-40", "Kawasan Ekonomi"),
    ("PMK-2020-237", "Kawasan Ekonomi"),
    ("PMK-2021-33", "Kawasan Ekonomi"),
    ("PP-2021-41", "Kawasan Perdagangan"),
    ("UU-2000-36", "Kawasan Perdagangan"),
    ("PP-2025-25", "Kawasan Perdagangan"),
    ("PP-2026-23", "Kawasan Perdagangan"),
    ("PP-2010-79", "Minyak"),
    ("PP-2017-27", "Minyak"),
    ("PP-2017-53", "Minyak"),
    ("PP-2021-93", "Minyak"),
    ("PP-2022-15", "Batubara"),
    ("PP-2025-18", "Batubara"),
    ("UU-1995-10", "Kepabeanan"),
    ("UU-2006-17", "Kepabeanan"),
    ("UU-1995-11", "Cukai"),
    ("UU-2007-39", "Cukai"),
    ("PP-2008-28", "Kepabeanan"),
    ("PP-2019-39", "Kepabeanan"),
    ("PP-2009-32", "Penimbunan"),
    ("PP-2015-85", "Penimbunan"),
]


def find_verified_page(doc_id: str, hint: str) -> tuple[str, dict] | None:
    jenis, tahun, nomor = split_id(doc_id)
    label = JENIS_LABEL[jenis]
    hits = bpk_search(label, nomor, tahun, must_contain=hint) or bpk_search(label, nomor, tahun)
    seen = set()
    for href, _ in hits[:8]:
        if href in seen:
            continue
        seen.add(href)
        url = BPK + href
        try:
            page = BpkDetailParser().parse(http_get(url).text, url)
        except Exception:
            continue
        meta = page["meta"]
        pid, _, _ = page_document_id(meta)
        if pid == doc_id:
            return url, page
        # Fallback pencocokan judul eksplisit (mis. nomor PMK ber-kode 02/PMK...)
        tit = meta.get("Judul") or ""
        if (re.search(rf"(?i)nomor\s+0?{int(nomor)}\b", tit)
                and str(tahun) in tit
                and hint.lower() in tit.lower()):
            return url, page
    return None


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    TEXT.mkdir(parents=True, exist_ok=True)
    OUT_TMP.mkdir(parents=True, exist_ok=True)

    log = {"fetched": [], "skipped": [], "failed": []}
    for doc_id, hint in TARGETS:
        doc_path = DOCS / f"{doc_id}.json"
        txt_path = TEXT / f"{doc_id}.txt"
        if doc_path.exists() and txt_path.exists():
            print(f"[LEWATI] {doc_id} (sudah ada)")
            log["skipped"].append(doc_id)
            continue

        found = find_verified_page(doc_id, hint)
        if not found:
            print(f"[GAGAL-CARI] {doc_id} ({hint})")
            log["failed"].append({"document_id": doc_id, "reason": "tidak ditemukan di BPK"})
            continue

        url, page = found
        meta = page["meta"]
        judul = meta.get("Judul") or ""
        dl = next((a for a in page["pdf_links"] if a.startswith("/Download/")),
                  next((a for a in page["pdf_links"] if a.startswith("/Read/")), None))
        if not dl:
            print(f"[NO-PDF] {doc_id} <- {url}")
            log["failed"].append({"document_id": doc_id, "reason": "tidak ada tautan PDF", "url": url})
            continue

        pdf_path = OUT_TMP / f"{doc_id}.pdf"
        if not pdf_path.exists():
            pdf_path.write_bytes(http_get(BPK + dl).content)

        text_col, n_pages, avg = extract_pdf_text(pdf_path, col_aware=True)
        text_plain, _, _ = extract_pdf_text(pdf_path, col_aware=False)
        p_col = parse_document(doc_id, text_col)
        p_plain = parse_document(doc_id, text_plain)
        n_col = sum(1 for p in p_col["provisions"] if p["level"] == "PASAL")
        n_plain = sum(1 for p in p_plain["provisions"] if p["level"] == "PASAL")
        if (p_col["structure"] == "UNKNOWN" and p_plain["structure"] != "UNKNOWN") or n_plain >= n_col:
            text, parsed = text_plain, p_plain
        else:
            text, parsed = text_col, p_col
        txt_path.write_text(text, encoding="utf-8")

        batang, _ = cut_penjelasan(text)
        _, arts, _ = split_pasal(batang)

        jenis, tahun, _ = split_id(doc_id)
        extra = {
            "status_sumber": meta.get("Status"),
            "tanggal_penetapan": parse_date_id(meta.get("Tanggal Penetapan")),
            "tanggal_pengundangan": parse_date_id(meta.get("Tanggal Pengundangan")),
            "tanggal_berlaku_sumber": parse_date_id(meta.get("Tanggal Berlaku")),
            "sumber_publikasi": meta.get("Sumber"),
            "subjek_sumber": meta.get("Subjek"),
            "source_urls": [
                {"source": "peraturan.bpk.go.id", "url": url},
                {"source": "peraturan.bpk.go.id", "url": BPK + dl, "type": "pdf"},
            ],
            "structure": parsed["structure"],
            "preamble": parsed["preamble"],
        }
        rec = canon_doc(
            doc_id, jenis, tahun, judul, arts,
            {"origin": "fetched_bpk_3b", "url": url, "pages": n_pages},
            extra=extra,
        )
        rec["penjelasan"] = parsed["penjelasan"]
        rec["penjelasan_articles"] = parsed["penjelasan_articles"]
        rec["provisions"] = parsed["provisions"]
        rec["structure"] = parsed["structure"]
        rec["quality"]["ocr_suspect"] = (avg < 60)
        rec["quality"]["zero_pasal"] = (len(parsed["provisions"]) == 0 and len(arts) == 0)
        doc_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

        n_pas = sum(1 for p in parsed["provisions"] if p["level"] == "PASAL")
        print(f"[OK] {doc_id:15} {parsed['structure']:14} pasal={n_pas:3} "
              f"prov={len(parsed['provisions']):4} pages={n_pages:3} status={meta.get('Status')}")
        log["fetched"].append({"document_id": doc_id, "url": url, "pasal": n_pas,
                               "structure": parsed["structure"], "status_sumber": meta.get("Status")})

    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSelesai: fetched={len(log['fetched'])} skipped={len(log['skipped'])} failed={len(log['failed'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
