# -*- coding: utf-8 -*-
"""Konversi 199 PDF Putusan Pengadilan Pajak (download-pdf/putusan/) menjadi
korpus yurisprudensi JSON terstruktur di data/jurisprudence/ +
data/jurisprudence_manifest.json.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.gaps import extract_citations  # noqa: E402

PUT_DIR = ROOT / "download-pdf" / "putusan"
OUT_DIR = ROOT / "data" / "jurisprudence"
MANIFEST = ROOT / "data" / "jurisprudence_manifest.json"


def detect_amar(text: str) -> tuple[str, str]:
    """Ekstrak blok amar akhir dan klasifikasikan kategori amar."""
    tail = text[-8000:] if len(text) > 8000 else text
    marks = list(re.finditer(r"(?i)\b(?:Memutuskan|MENGADILI)\s*:?", tail))
    amar_teks = ""
    if marks:
        seg = tail[marks[-1].start():]
        end = re.search(r"(?i)Demikian\s+diputus|Salinan\s+sesuai\s+dengan\s+aslinya", seg)
        amar_teks = re.sub(r"\s+", " ", seg[:end.start()] if end else seg[:1800]).strip()
    low = amar_teks.lower() or tail.lower()
    if "mengabulkan seluruhnya" in low or "mengabulkan gugatan" in low:
        kat = "KABUL_SELURUHNYA"
    elif "mengabulkan sebagian" in low:
        kat = "KABUL_SEBAGIAN"
    elif "menolak" in low:
        kat = "TOLAK"
    elif "tidak dapat diterima" in low:
        kat = "TIDAK_DAPAT_DITERIMA"
    elif "membatalkan" in low:
        kat = "BATAL"
    else:
        kat = "LAINNYA"
    return kat, amar_teks


def parse_putusan_text(rec: dict, text: str, n_pages: int, avg_chars: float) -> dict:
    rid = int(rec["id"])
    case_id = f"PP-PUT-{rid}"
    noput = rec.get("noput") or ""

    m_jp = re.search(r"(?i)Jenis\s+Pajak\s*:\s*([^\n]+)", text[:3000])
    m_tp = re.search(r"(?i)Tahun\s+Pajak\s*:\s*([^\n]+)", text[:3000])
    m_put_yr = re.search(r"Tahun\s+(\d{4})", noput)

    m_ps = re.search(
        r"(?is)Pokok\s+Sengketa\s*:\s*(.+?)(?=\n\s*Menurut\s+(?:Terbanding|Tergugat|Pemohon|Penggugat|Majelis))",
        text[:15000],
    )
    pokok = re.sub(r"\s+", " ", m_ps.group(1)).strip() if m_ps else (rec.get("abstraksi") or "")

    pertimbangan = ""
    maj_hits = list(re.finditer(r"(?i)Menurut\s+Majelis\s*:?", text))
    if maj_hits:
        start = maj_hits[-1].start()
        end_m = re.search(
            r"(?i)\b(?:Mengingat|Memutuskan|MENGADILI)\b",
            text[start + 20:],
        )
        end = (start + 20 + end_m.start()) if end_m else min(len(text), start + 25000)
        pertimbangan = text[start:end].strip()

    amar_kat, amar_teks = detect_amar(text)

    # Tautkan regulasi yang dikutip di putusan ke document_id kanonik kita
    cits = extract_citations({
        "document_id": case_id,
        "jenis": "PUTUSAN-PP",
        "judul": noput,
        "preamble": "",
        "provisions": [{"level": "PASAL", "nomor": "1", "text": text}],
        "penjelasan": "",
    })
    cited_regs = sorted({c["resolved_document_id"] for c in cits})

    return {
        "case_id": case_id,
        "setpp_id": rid,
        "putusan_nomor": noput,
        "klaster": rec.get("klaster"),
        "kode_pajak": rec.get("kode_pajak"),
        "jenis_pajak": m_jp.group(1).strip() if m_jp else rec.get("klaster"),
        "tahun_pajak": m_tp.group(1).strip() if m_tp else rec.get("tahun_sengketa"),
        "tahun_putusan": int(m_put_yr.group(1)) if m_put_yr else None,
        "abstraksi": rec.get("abstraksi"),
        "pokok_sengketa": pokok[:4000],
        "pertimbangan_majelis": pertimbangan[:30000],
        "amar_kategori": amar_kat,
        "amar_teks": amar_teks,
        "cited_regulations": cited_regs,
        "full_text": text,
        "pages": n_pages,
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "source": {
            "origin": "setpp.kemenkeu.go.id",
            "url": rec.get("url"),
            "pdf_file": rec.get("pdf_file"),
        },
        "quality": {
            "ocr_suspect": avg_chars < 60,
            "has_pertimbangan": bool(pertimbangan),
        },
    }


def main() -> int:
    idx = json.loads((PUT_DIR / "index.json").read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest_items = []
    by_klaster: Counter = Counter()
    by_amar: Counter = Counter()
    ocr_bad = 0

    for rec in idx:
        pdf_path = PUT_DIR / rec["rel_path"]
        if not pdf_path.exists():
            continue
        doc = fitz.open(pdf_path)
        pages = [pg.get_text() for pg in doc]
        n_pages = len(pages)
        avg = (sum(len(p) for p in pages) / n_pages) if n_pages else 0.0
        text = "\n\n".join(pages)

        item = parse_putusan_text(rec, text, n_pages, avg)
        out_path = OUT_DIR / f"{item['case_id']}.json"
        out_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")

        by_klaster[item["klaster"]] += 1
        by_amar[item["amar_kategori"]] += 1
        if item["quality"]["ocr_suspect"]:
            ocr_bad += 1

        manifest_items.append({
            "case_id": item["case_id"],
            "putusan_nomor": item["putusan_nomor"],
            "klaster": item["klaster"],
            "jenis_pajak": item["jenis_pajak"],
            "tahun_pajak": item["tahun_pajak"],
            "tahun_putusan": item["tahun_putusan"],
            "amar_kategori": item["amar_kategori"],
            "cited_regulations": item["cited_regulations"],
            "has_pertimbangan": item["quality"]["has_pertimbangan"],
            "ocr_suspect": item["quality"]["ocr_suspect"],
            "pages": n_pages,
            "path": f"knowledge_json/jurisprudence/{item['case_id']}.json",
            "source_url": item["source"]["url"],
        })

    manifest = {
        "total_cases": len(manifest_items),
        "by_klaster": dict(sorted(by_klaster.items())),
        "by_amar": dict(sorted(by_amar.items())),
        "ocr_suspect_count": ocr_bad,
        "cases": manifest_items,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Converted putusan: {len(manifest_items)} | ocr_suspect={ocr_bad}")
    print("  by_klaster:", manifest["by_klaster"])
    print("  by_amar   :", manifest["by_amar"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
