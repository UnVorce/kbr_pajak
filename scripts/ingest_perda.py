# -*- coding: utf-8 -*-
"""Konversi 524 PDF Perda PDRD (download-pdf/perda/) menjadi korpus JSON (Opsi 1).

- 493+ PDF teks digital langsung di-parse (parse_structure.parse_document) dan
  disimpan ke data/perda/<PERDA-DAERAH-TAHUN-NOMOR>.json.
- PDF hasil scan (avg_chars < 60 atau >80% halaman kosong) tetap didaftarkan di
  data/perda_manifest.json dengan status NEEDS_OCR & quality.ocr_suspect=True.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fase1_korpus import canon_doc  # noqa: E402
from src.parse_structure import parse_document  # noqa: E402
from src.textutil import cut_penjelasan, split_pasal  # noqa: E402

PERDA_PDF_DIR = ROOT / "download-pdf" / "perda"
OUT_DIR = ROOT / "data" / "perda"
MANIFEST = ROOT / "data" / "perda_manifest.json"


def make_perda_id(slug: str, tahun: int, bpk_id: str, used: set[str]) -> str:
    """Bangun document_id unik berbasis wilayah dari slug BPK."""
    m = re.match(
        r"^(perda(?:sus|si)?)-(?:(.+?)-)?no-([a-z0-9]+)-tahun-(\d{4})",
        (slug or "").lower(),
    )
    if m:
        kind = m.group(1).upper()
        region = (m.group(2) or f"DAERAH-{bpk_id}").upper()
        no = m.group(3).lstrip("0") or m.group(3)
        yr = m.group(4)
        cand = re.sub(r"[^A-Z0-9-]+", "-", f"{kind}-{region}-{yr}-{no}").strip("-")
    else:
        cand = f"PERDA-{tahun}-{bpk_id}"
    if cand in used:
        cand = f"{cand}-BPK{bpk_id}"
    used.add(cand)
    return cand


def main() -> int:
    idx = json.loads((PERDA_PDF_DIR / "index.json").read_text(encoding="utf-8"))
    downloaded = idx.get("downloaded", {})
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    used_ids: set[str] = set()
    manifest_items = []
    status_counts: Counter = Counter()
    year_counts: Counter = Counter()

    for bpk_id, info in sorted(downloaded.items(), key=lambda kv: (kv[1]["tahun"], int(kv[0]))):
        pdf_path = PERDA_PDF_DIR / info["rel_path"]
        if not pdf_path.exists():
            continue
        doc_id = make_perda_id(info.get("slug", ""), info["tahun"], bpk_id, used_ids)

        doc = fitz.open(pdf_path)
        pages = [pg.get_text() for pg in doc]
        n_pages = len(pages)
        lens = [len(p.strip()) for p in pages]
        avg = (sum(lens) / n_pages) if n_pages else 0.0
        empty_ratio = (sum(1 for x in lens if x < 40) / n_pages) if n_pages else 1.0

        is_full_scan = (avg < 60 or empty_ratio > 0.8)
        is_partial = (not is_full_scan) and (empty_ratio > 0.25)

        if is_full_scan:
            ocr_status = "NEEDS_OCR"
            rec = canon_doc(
                doc_id, "PERDA", info["tahun"], info["judul"], [],
                {"origin": "fetched_bpk_perda", "bpk_id": bpk_id, "pages": n_pages},
                extra={
                    "status_sumber": info.get("status_sumber"),
                    "tanggal_penetapan": info.get("tanggal_penetapan"),
                    "tanggal_pengundangan": info.get("tanggal_pengundangan"),
                    "subjek_sumber": info.get("subjek_sumber"),
                    "source_urls": [
                        {"source": "peraturan.bpk.go.id", "url": info.get("detail_url")},
                        {"source": "peraturan.bpk.go.id", "url": info.get("pdf_url"), "type": "pdf"},
                    ],
                    "structure": "SCAN_NEEDS_OCR",
                    "provisions": [],
                    "preamble": "",
                    "penjelasan": "",
                    "penjelasan_articles": [],
                },
            )
            rec["quality"]["ocr_suspect"] = True
            rec["quality"]["ocr_status"] = ocr_status
            n_pasal = 0
        else:
            text = "\n\n".join(pages)
            batang, _ = cut_penjelasan(text)
            _, arts, _ = split_pasal(batang)
            parsed = parse_document(doc_id, text)
            ocr_status = "PARTIAL_SCAN" if is_partial else "DIGITAL_OK"
            rec = canon_doc(
                doc_id, "PERDA", info["tahun"], info["judul"], arts,
                {"origin": "fetched_bpk_perda", "bpk_id": bpk_id, "pages": n_pages},
                extra={
                    "status_sumber": info.get("status_sumber"),
                    "tanggal_penetapan": info.get("tanggal_penetapan"),
                    "tanggal_pengundangan": info.get("tanggal_pengundangan"),
                    "subjek_sumber": info.get("subjek_sumber"),
                    "source_urls": [
                        {"source": "peraturan.bpk.go.id", "url": info.get("detail_url")},
                        {"source": "peraturan.bpk.go.id", "url": info.get("pdf_url"), "type": "pdf"},
                    ],
                    "structure": parsed["structure"],
                    "preamble": parsed["preamble"],
                },
            )
            rec["penjelasan"] = parsed["penjelasan"]
            rec["penjelasan_articles"] = parsed["penjelasan_articles"]
            rec["provisions"] = parsed["provisions"]
            rec["structure"] = parsed["structure"]
            rec["quality"]["ocr_suspect"] = is_partial
            rec["quality"]["ocr_status"] = ocr_status
            rec["quality"]["zero_pasal"] = (len(parsed["provisions"]) == 0 and len(arts) == 0)
            n_pasal = sum(1 for p in parsed["provisions"] if p["level"] == "PASAL")

        (OUT_DIR / f"{doc_id}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        status_counts[ocr_status] += 1
        year_counts[info["tahun"]] += 1
        manifest_items.append({
            "document_id": doc_id,
            "bpk_id": bpk_id,
            "tahun": info["tahun"],
            "judul": info["judul"],
            "status_sumber": info.get("status_sumber"),
            "ocr_status": ocr_status,
            "structure": rec["structure"],
            "provisions_pasal_count": n_pasal,
            "articles_count": len(rec["articles"]),
            "pages": n_pages,
            "path": f"knowledge_json/perda/{doc_id}.json",
            "detail_url": info.get("detail_url"),
        })

    manifest = {
        "total_perda": len(manifest_items),
        "by_ocr_status": dict(sorted(status_counts.items())),
        "by_tahun": dict(sorted(year_counts.items())),
        "skipped_revoked_count": len(idx.get("skipped_revoked", {})),
        "failed_download_count": len(idx.get("failed", {})),
        "documents": manifest_items,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Perda JSON selesai: total={len(manifest_items)} | status={manifest['by_ocr_status']} | tahun={manifest['by_tahun']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
