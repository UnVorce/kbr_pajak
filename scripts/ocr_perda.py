# -*- coding: utf-8 -*-
"""Opsi 2 — OCR paralel (Tesseract 5 ind+eng) untuk 31 Perda scan/parsial + PMK-2009-105 hal 1.

- Memakai PyMuPDF (200 DPI grayscale PNG) + tesseract stdin stdout (--psm 3 -l ind+eng).
- Paralel multi-core (OMP_THREAD_LIMIT=1) & resumable lewat cache teks data/perda_ocr_text/.
- Memperbarui JSON di data/perda/*.json + data/perda_manifest.json serta
  data/documents/PMK-2009-105.json + data/text/PMK-2009-105.txt.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fase1_korpus import canon_doc  # noqa: E402
from src.parse_structure import parse_document  # noqa: E402
from src.textutil import cut_penjelasan, split_pasal  # noqa: E402

PERDA_PDF_DIR = ROOT / "download-pdf" / "perda"
PERDA_IDX = PERDA_PDF_DIR / "index.json"
PERDA_DIR = ROOT / "data" / "perda"
PERDA_MAN = ROOT / "data" / "perda_manifest.json"
OCR_TXT_DIR = ROOT / "data" / "perda_ocr_text"


def _ocr_page_task(args: tuple[str, int, int]) -> tuple[int, str]:
    pdf_path, page_idx, dpi = args
    doc = fitz.open(pdf_path)
    pg = doc[page_idx]
    existing = pg.get_text().strip()
    if len(existing) >= 40:
        return page_idx, pg.get_text()
    pix = pg.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), colorspace=fitz.csGRAY)
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    res = subprocess.run(
        ["tesseract", "stdin", "stdout", "-l", "ind+eng", "--psm", "3"],
        input=pix.tobytes("png"),
        capture_output=True,
        env=env,
        timeout=60,
    )
    return page_idx, res.stdout.decode("utf-8", errors="replace")


def ocr_pdf(pdf_path: Path, workers: int = 14, dpi: int = 200) -> tuple[str, int, float]:
    n_pages = len(fitz.open(pdf_path))
    tasks = [(str(pdf_path), i, dpi) for i in range(n_pages)]
    pages = [""] * n_pages
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_ocr_page_task, t) for t in tasks]
        for fut in as_completed(futs):
            idx, txt = fut.result()
            pages[idx] = txt
    avg = (sum(len(p.strip()) for p in pages) / n_pages) if n_pages else 0.0
    return "\n\n".join(pages), n_pages, avg


def fix_pmk_2009_105(workers: int, dpi: int) -> None:
    pdf_p = ROOT / "download-pdf" / "regulasi" / "PMK-2009-105.pdf"
    if not pdf_p.exists():
        return
    txt, n_pages, avg = ocr_pdf(pdf_p, workers=min(4, workers), dpi=dpi)
    (ROOT / "data" / "text" / "PMK-2009-105.txt").write_text(txt, encoding="utf-8")
    doc_p = ROOT / "data" / "documents" / "PMK-2009-105.json"
    d = json.loads(doc_p.read_text(encoding="utf-8"))
    batang, _ = cut_penjelasan(txt)
    _, arts, _ = split_pasal(batang)
    parsed = parse_document("PMK-2009-105", txt)
    rec = canon_doc("PMK-2009-105", "PMK", 2009, d["judul"], arts,
                    {**d.get("source", {}), "ocr_page1": "tesseract_ind"},
                    extra={k: d.get(k) for k in (
                        "status_sumber", "tanggal_penetapan", "tanggal_pengundangan",
                        "tanggal_berlaku_sumber", "sumber_publikasi", "subjek_sumber", "source_urls"
                    ) if d.get(k) is not None})
    rec["preamble"] = parsed["preamble"]
    rec["penjelasan"] = parsed["penjelasan"]
    rec["penjelasan_articles"] = parsed["penjelasan_articles"]
    rec["provisions"] = parsed["provisions"]
    rec["structure"] = parsed["structure"]
    rec["quality"]["ocr_suspect"] = False
    rec["quality"]["ocr_status"] = "OCR_DONE"
    rec["quality"]["zero_pasal"] = (len(parsed["provisions"]) == 0 and len(arts) == 0)
    doc_p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    n_pas = sum(1 for p in parsed["provisions"] if p["level"] == "PASAL")
    print(f"[PMK-2009-105] {parsed['structure']} pasal={n_pas} avg={avg:.0f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()

    fix_pmk_2009_105(args.workers, args.dpi)

    idx = json.loads(PERDA_IDX.read_text(encoding="utf-8")).get("downloaded", {})
    manifest = json.loads(PERDA_MAN.read_text(encoding="utf-8"))
    OCR_TXT_DIR.mkdir(parents=True, exist_ok=True)

    targets = [m for m in manifest["documents"] if m["ocr_status"] != "DIGITAL_OK"]
    print(f"Target Perda OCR: {len(targets)} dokumen ({sum(m['pages'] for m in targets)} halaman)")

    for k, m in enumerate(targets, 1):
        did = m["document_id"]
        bid = m["bpk_id"]
        info = idx.get(bid, {})
        pdf_path = PERDA_PDF_DIR / info["rel_path"]
        cache_txt = OCR_TXT_DIR / f"{did}.txt"
        if cache_txt.exists():
            text = cache_txt.read_text(encoding="utf-8", errors="replace")
            n_pages = m["pages"]
            avg = len(text.strip()) / n_pages if n_pages else 0.0
        else:
            text, n_pages, avg = ocr_pdf(pdf_path, workers=args.workers, dpi=args.dpi)
            cache_txt.write_text(text, encoding="utf-8")

        doc_path = PERDA_DIR / f"{did}.json"
        old = json.loads(doc_path.read_text(encoding="utf-8"))
        batang, _ = cut_penjelasan(text)
        _, arts, _ = split_pasal(batang)
        parsed = parse_document(did, text)

        ocr_ok = avg >= 60
        ocr_status = "OCR_DONE" if ocr_ok else "OCR_LOW_TEXT"
        rec = canon_doc(
            did, "PERDA", m["tahun"], old["judul"], arts,
            {**old.get("source", {}), "ocr_engine": "tesseract_ind+eng", "dpi": args.dpi},
            extra={k2: old.get(k2) for k2 in (
                "status_sumber", "tanggal_penetapan", "tanggal_pengundangan",
                "subjek_sumber", "source_urls"
            ) if old.get(k2) is not None},
        )
        rec["preamble"] = parsed["preamble"]
        rec["penjelasan"] = parsed["penjelasan"]
        rec["penjelasan_articles"] = parsed["penjelasan_articles"]
        rec["provisions"] = parsed["provisions"]
        rec["structure"] = parsed["structure"]
        rec["quality"]["ocr_suspect"] = not ocr_ok
        rec["quality"]["ocr_status"] = ocr_status
        rec["quality"]["zero_pasal"] = (len(parsed["provisions"]) == 0 and len(arts) == 0)
        doc_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

        n_pas = sum(1 for p in parsed["provisions"] if p["level"] == "PASAL")
        m["ocr_status"] = ocr_status
        m["structure"] = parsed["structure"]
        m["provisions_pasal_count"] = n_pas
        m["articles_count"] = len(rec["articles"])
        print(f"  [{k:2}/{len(targets)}] {did:36} {parsed['structure']:14} pasal={n_pas:3} avg={avg:5.0f}")

        if k % 5 == 0:
            _save_manifest(manifest)

    _save_manifest(manifest)
    print("Selesai OCR Perda:", manifest["by_ocr_status"])
    return 0


def _save_manifest(manifest: dict) -> None:
    st = Counter(d["ocr_status"] for d in manifest["documents"])
    manifest["by_ocr_status"] = dict(sorted(st.items()))
    PERDA_MAN.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
