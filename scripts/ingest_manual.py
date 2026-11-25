# -*- coding: utf-8 -*-
"""Ingest 12 PDF hasil unduhan manual di download-manual/ ke korpus kanonik.

- Ekstraksi teks PyMuPDF (mode 2-kolom khusus PMK-2024-79).
- Enrichment metadata dari halaman Detail BPK (dengan verifikasi document_id)
  atau metadata manual untuk dokumen non-BPK (PMK-2024-69, PER-DJP-2025-11).
- Parsing struktur S4 (parse_structure.parse_document) dan simpan ke
  data/text/<id>.txt serta data/documents/<id>.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fase1_korpus import BPK, canon_doc, http_get  # noqa: E402
from src.crawl import BpkDetailParser, page_document_id, parse_date_id  # noqa: E402
from src.parse_structure import parse_document  # noqa: E402
from src.textutil import cut_penjelasan, split_pasal  # noqa: E402

MANUAL_DIR = ROOT / "download-manual"
DOCS = ROOT / "data" / "documents"
TEXT = ROOT / "data" / "text"

# (filename, document_id, jenis, tahun, bpk_rel_url_or_None, fallback_meta)
ITEMS = [
    ("128_PMK.010_2019Per.pdf", "PMK-2019-128", "PMK", 2019,
     "/Details/128156/pmk-no-128pmk0102019", {}),
    ("186~PMK.03~2019Per.pdf", "PMK-2019-186", "PMK", 2019,
     "/Details/128302/pmk-no-186pmk032019", {}),
    ("234~PMK.03~2022Per.pdf", "PMK-2022-234", "PMK", 2022,
     "/Details/238808/pmk-no-234pmk032022", {}),
    ("2023pmkeuangan061.pdf", "PMK-2023-61", "PMK", 2023,
     "/Details/254091/pmk-no-61-tahun-2023", {}),
    ("2024pmkeuangan069.pdf", "PMK-2024-69", "PMK", 2024, None, {
        "judul": ("Peraturan Menteri Keuangan Nomor 69 Tahun 2024 tentang "
                  "Perubahan atas Peraturan Menteri Keuangan Nomor 130/PMK.010/2020 "
                  "tentang Pemberian Fasilitas Pengurangan Pajak Penghasilan Badan"),
        "status_sumber": "Berlaku",
        "source_urls": [{"source": "jdih.kemenkeu.go.id",
                         "url": "https://jdih.kemenkeu.go.id"}],
    }),
    ("2024pmkeuangan079.pdf", "PMK-2024-79", "PMK", 2024,
     "/Details/306437/pmk-no-79-tahun-2024", {"col_aware": True}),
    ("2026pmkeuangan028.pdf", "PMK-2026-28", "PMK", 2026,
     "/Details/348562/pmk-no-28-tahun-2026", {}),
    ("PER-11_PJ_2025_0.pdf", "PER-DJP-2025-11", "PER-DJP", 2025, None, {
        "judul": ("Peraturan Direktur Jenderal Pajak Nomor PER-11/PJ/2025 tentang "
                  "Ketentuan Pelaporan Pajak Penghasilan, Pajak Pertambahan Nilai, "
                  "Pajak Penjualan atas Barang Mewah, dan Bea Meterai dalam Rangka "
                  "Pelaksanaan Sistem Inti Administrasi Perpajakan"),
        "status_sumber": "Berlaku",
        "source_urls": [{"source": "pajak.go.id",
                         "url": "https://www.pajak.go.id"}],
    }),
    ("Perpres Nomor 40 Tahun 2018.pdf", "PERPRES-2018-40", "PERPRES", 2018,
     "/Details/77914/perpres-no-40-tahun-2018", {}),
    ("Perpu No 1 Tahun 2017.pdf", "PERPU-2017-1", "PERPU", 2017,
     "/Details/53275/perpu-no-1-tahun-2017", {}),
    ("UU Nomor 19 Tahun 1997.pdf", "UU-1997-19", "UU", 1997,
     "/Details/46002/uu-no-19-tahun-1997", {}),
    ("UU 19_2000.pdf", "UU-2000-19", "UU", 2000,
     "/Details/44984/uu-no-19-tahun-2000", {}),
]


def extract_pdf_text(pdf_path: Path, col_aware: bool = False) -> tuple[str, int, float]:
    doc = fitz.open(pdf_path)
    pages = []
    for pg in doc:
        if not col_aware:
            pages.append(pg.get_text())
            continue
        w, h = pg.rect.width, pg.rect.height
        blocks = [b for b in pg.get_text("blocks") if b[6] == 0 and b[4].strip()]
        left = [b for b in blocks if b[2] < w * 0.52]
        right = [b for b in blocks if b[0] > w * 0.48]
        if len(left) >= 2 and len(right) >= 2:
            wide = [b for b in blocks if b[0] < w * 0.35 and b[2] > w * 0.65]
            top_w = sorted([b for b in wide if b[1] < h * 0.25], key=lambda b: b[1])
            bot_w = sorted([b for b in wide if b[1] >= h * 0.25], key=lambda b: b[1])
            left_s = sorted([b for b in left if b not in wide], key=lambda b: (b[1], b[0]))
            right_s = sorted([b for b in right if b not in wide], key=lambda b: (b[1], b[0]))
            pages.append("\n".join(b[4].strip() for b in (top_w + left_s + right_s + bot_w)))
        else:
            pages.append(pg.get_text())
    n = len(pages)
    avg = (sum(len(p) for p in pages) / n) if n else 0.0
    return "\n\n".join(pages), n, avg


def fetch_bpk_meta(doc_id: str, rel_url: Optional[str]) -> dict:
    if not rel_url:
        return {}
    url = BPK + rel_url
    page = BpkDetailParser().parse(http_get(url).text, url)
    meta = page["meta"]
    page_id, _, _ = page_document_id(meta)
    if page_id and page_id != doc_id:
        raise RuntimeError(f"Konflik BPK {doc_id} vs {page_id} di {url}")
    urls = [{"source": "peraturan.bpk.go.id", "url": url}]
    dl = next((a for a in page["pdf_links"] if a.startswith("/Download/")), None)
    if dl:
        urls.append({"source": "peraturan.bpk.go.id", "url": BPK + dl, "type": "pdf"})
    return {
        "judul": meta.get("Judul") or "",
        "status_sumber": meta.get("Status"),
        "tanggal_penetapan": parse_date_id(meta.get("Tanggal Penetapan")),
        "tanggal_pengundangan": parse_date_id(meta.get("Tanggal Pengundangan")),
        "tanggal_berlaku_sumber": parse_date_id(meta.get("Tanggal Berlaku")),
        "sumber_publikasi": meta.get("Sumber"),
        "subjek_sumber": meta.get("Subjek"),
        "source_urls": urls,
    }


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    TEXT.mkdir(parents=True, exist_ok=True)
    for fname, did, jenis, tahun, bpk_rel, fb in ITEMS:
        pdf_path = MANUAL_DIR / fname
        if not pdf_path.exists():
            print(f"[HILANG] {pdf_path}")
            continue
        col_aware = bool(fb.get("col_aware"))
        text, n_pages, avg = extract_pdf_text(pdf_path, col_aware=col_aware)
        (TEXT / f"{did}.txt").write_text(text, encoding="utf-8")

        batang, _ = cut_penjelasan(text)
        pre, arts, struct = split_pasal(batang)
        parsed = parse_document(did, text)

        meta = fetch_bpk_meta(did, bpk_rel)
        judul = meta.get("judul") or fb.get("judul") or ""
        src_urls = meta.get("source_urls") or fb.get("source_urls") or []

        doc_path = DOCS / f"{did}.json"
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

        if doc_path.exists() and did == "PMK-2024-79":
            old = json.loads(doc_path.read_text(encoding="utf-8"))
            rec = canon_doc(did, jenis, tahun, old.get("judul") or judul, arts,
                            old.get("source") or {"origin": "fetched_bpk"},
                            extra={**extra, "source_urls": old.get("source_urls") or src_urls})
        else:
            rec = canon_doc(did, jenis, tahun, judul, arts,
                            {"origin": "manual_download", "file": fname, "pages": n_pages},
                            extra=extra)

        rec["penjelasan"] = parsed["penjelasan"]
        rec["penjelasan_articles"] = parsed["penjelasan_articles"]
        rec["provisions"] = parsed["provisions"]
        rec["structure"] = parsed["structure"]
        rec["quality"]["ocr_suspect"] = (avg < 60)
        rec["quality"]["zero_pasal"] = (len(parsed["provisions"]) == 0 and len(arts) == 0)
        doc_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

        n_pasal = sum(1 for p in parsed["provisions"] if p["level"] == "PASAL")
        print(f"[OK] {did:16} {parsed['structure']:14} pasal={n_pasal:3} "
              f"prov={len(parsed['provisions']):4} pages={n_pages:3} avg={avg:4.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
