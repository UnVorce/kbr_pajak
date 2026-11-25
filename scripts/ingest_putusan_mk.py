# -*- coding: utf-8 -*-
"""Konversi PDF Putusan Mahkamah Konstitusi (download-pdf/putusan_mk/) ke JSON
kanonik terstruktur di data/putusan_mk/ + data/mk_manifest.json.
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

MK_PDF_DIR = ROOT / "download-pdf" / "putusan_mk"
OUT_DIR = ROOT / "data" / "putusan_mk"
MANIFEST = ROOT / "data" / "mk_manifest.json"


def classify_mk_amar(amar_text: str) -> str:
    low = (amar_text or "").lower()
    if "sepanjang tidak dimaknai" in low or "secara bersyarat" in low or "bertentangan dengan" in low and "sepanjang" in low:
        return "KONSTITUSIONAL_BERSYARAT"
    if "untuk sebagian" in low:
        return "KABUL_SEBAGIAN"
    if "untuk seluruhnya" in low or "mengabulkan permohonan" in low:
        return "KABUL_SELURUHNYA"
    return "KABUL_LAINNYA"


# Pengganti (successor) yang tidak memakai nomor pasal yang sama → hanya catatan, bukan tautan pasal
SUCCESSOR_DOCS = {
    "UU-2009-28": ["UU-2022-1"],  # PDRD → HKPD
}
# Pasal UU HPP yang menempel ke UU KUP (hasil perubahan lampiran CK/HPP)
HPP_TO_KUP_PASAL = {"43A", "43B", "44", "44A", "44B", "45", "45A", "45B"}

AMENDER_TO_INDUK = {
    "UU-2007-28": ["UU-1983-6"],   # KUP
    "UU-2009-16": ["UU-1983-6"],   # penetapan PERPU 5/2008 → KUP
    "PERPU-2008-5": ["UU-1983-6"],
    "UU-2008-36": ["UU-1983-7"],   # PPh
    "UU-2009-42": ["UU-1983-8"],   # PPN
    "UU-2007-39": ["UU-1995-11"],  # Cukai
    "UU-2006-17": ["UU-1995-10"],  # Kepabeanan
}


def _strip_non_tested_clauses(text: str) -> str:
    """Ambil bagian sebelum rujukan UUD 1945 & sebelum 'sepanjang tidak dimaknai'."""
    t = re.sub(r"(?is)\b(?:bertentangan\s+dengan|terhadap)\s+Undang-Undang\s+Dasar[^.;\n]*", "", text or "")
    t = re.sub(r"(?is)\bPasal\s+\d+(?:\s+ayat\s+\(\d+[a-z]?\))?\s+(?:dan\s+Pasal\s+\d+[^\n,;]*)?UUD\s+(?:Tahun\s+)?1945", "", t)
    t = re.sub(r"(?is)\bsehingga\s+(?:norma\s+)?Pasal\s+[^\"]*?selengkapnya\s+berbunyi[^.;]*", "", t)
    return t


def extract_pasal_diuji(pokok: str, amar: str) -> list[str]:
    found = set()
    for src in (pokok or "", amar or ""):
        cleaned = _strip_non_tested_clauses(src)
        # buang pembungkus omnibus ("dalam Pasal 2 angka 13 UU 7/2021"): itu instruksi
        # perubahan, bukan norma yang diuji; norma ujinya tertulis lebih dulu.
        cleaned = re.sub(r"(?i)\bdalam\s+Pasal\s+\d+\s+angka\s+\d+\b", "", cleaned)
        cleaned = re.sub(r"(?i)\bPasal\s+\d+\s+angka\s+\d+\s+Undang-Undang\b", "Undang-Undang", cleaned)
        for m in re.finditer(
            r"(?i)(?:Penjelasan\s+)?Pasal\s+\d+[A-Z]?(?:\s+ayat\s+\(\d+[a-z]?\))?(?:\s+huruf\s+[a-z])?",
            cleaned,
        ):
            found.add(re.sub(r"\s+", " ", m.group(0)).strip())
    return sorted(found)


def _impacted_corpus_docs(uu_diuji: list[str], pokok: str, amar_full: str,
                          pasal_diuji: list[str] | None = None) -> list[str]:
    docs = set()
    for u in uu_diuji:
        if u in AMENDER_TO_INDUK:
            docs.update(AMENDER_TO_INDUK[u])
        docs.add(u)
    # UU HPP: pasal KUP (43A dst.) hasil perubahan HPP menempel ke UU-1983-6
    for s in pasal_diuji or []:
        m = re.match(r"(?i)(?:Penjelasan\s+)?Pasal\s+(\d+[A-Z]?)", s)
        if m and m.group(1).upper() in HPP_TO_KUP_PASAL and "UU-2021-7" in docs:
            docs.add("UU-1983-6")
    # Omnibus Cipta Kerja: lapisan pajak CK ada di UU-2023-6 (UU-2020-11 sendiri historis)
    if re.search(r"(?i)cipta\s+kerja", pokok or "") and "UU-2023-6" not in docs:
        docs.add("UU-2023-6")
    return sorted(docs)


def _successor_corpus_docs(uu_diuji: list[str]) -> list[str]:
    out = set()
    for u in uu_diuji:
        out.update(SUCCESSOR_DOCS.get(u, []))
    return sorted(out - set(uu_diuji))


def _uu_ids_from_pokok(pokok: str) -> list[str]:
    """Ambil UU/PERPU yang diuji dari 'pokok perkara' (bukan seluruh amar)."""
    out = []
    for m in re.finditer(
        r"(?i)(Peraturan\s+Pemerintah\s+Pengganti\s+Undang-Undang|Undang-Undang)\s+"
        r"(?:Republik\s+Indonesia\s+)?Nomor\s+(\d+)\s+Tahun\s+(\d{4})",
        pokok or "",
    ):
        jenis = "PERPU" if "Pengganti" in m.group(1) else "UU"
        out.append(f"{jenis}-{m.group(3)}-{int(m.group(2))}")
    return sorted(set(out))


def parse_mk_text(rec: dict, text: str, n_pages: int, avg_chars: float) -> dict:
    cid = rec["case_id"]
    nomor = rec["nomor_perkara"]
    pokok = rec.get("pokok_perkara") or ""
    amar_card = rec.get("amar_putusan") or ""

    # Ekstrak bagian PERTIMBANGAN HUKUM dan MENGADILI dari full_text PDF
    pertimbangan = ""
    m_ph = re.search(r"(?i)\[\s*3\.\d+\s*\]|PERTIMBANGAN\s+HUKUM", text)
    m_am = list(re.finditer(r"(?im)^\s*MENGADILI\b|AMAR\s+PUTUSAN\s*:", text))
    if m_ph and m_am and m_am[-1].start() > m_ph.start():
        pertimbangan = text[m_ph.start():m_am[-1].start()].strip()
    elif m_ph:
        pertimbangan = text[m_ph.start():m_ph.start() + 30000].strip()

    # Amar: kartu katalog JDIH sudah bersih & lengkap; PDF hanya dipakai bila kartu kosong.
    amar_full = re.sub(r"\s+", " ", amar_card or "").strip()
    if not amar_full and m_am:
        seg = text[m_am[-1].start():]
        end_m = re.search(r"(?i)Demikian\s+diputus|Demikian\s+diputuskan", seg)
        amar_full = re.sub(r"\s+", " ", seg[:end_m.start()] if end_m else seg[:4000]).strip()

    # Tautkan UU yang diuji (hanya dari pokok_perkara + bagian amar sebelum 'bertentangan dengan UUD')
    amar_tested = _strip_non_tested_clauses(amar_full)
    cits_pokok = extract_citations({
        "document_id": cid, "jenis": "PUTUSAN-MK", "judul": pokok,
        "preamble": "", "provisions": [{"level": "PASAL", "nomor": "1", "text": f"{pokok}\n{amar_tested}"}],
        "penjelasan": "",
    })
    uu_diuji = _uu_ids_from_pokok(pokok)
    if not uu_diuji:
        uu_diuji = sorted({c["resolved_document_id"] for c in cits_pokok if c["parsed_jenis"] in ("UU", "PERPU")})
    pasal_diuji = extract_pasal_diuji(pokok, amar_full)
    impacted_docs = _impacted_corpus_docs(uu_diuji, pokok, amar_full, pasal_diuji)
    successor_docs = _successor_corpus_docs(uu_diuji)

    cits_all = extract_citations({
        "document_id": cid, "jenis": "PUTUSAN-MK", "judul": pokok,
        "preamble": "", "provisions": [{"level": "PASAL", "nomor": "1", "text": text}],
        "penjelasan": "",
    })
    cited_regs = sorted({c["resolved_document_id"] for c in cits_all})

    m_yr = re.search(r"/(\d{4})$", nomor)
    tahun_reg = int(m_yr.group(1)) if m_yr else None
    m_put_yr = re.search(r"(\d{4})$", rec.get("tanggal_putusan") or "")
    tahun_put = int(m_put_yr.group(1)) if m_put_yr else tahun_reg

    return {
        "case_id": cid,
        "nomor_perkara": nomor,
        "tahun_registrasi": tahun_reg,
        "tahun_putusan": tahun_put,
        "tanggal_putusan": rec.get("tanggal_putusan"),
        "pemohon": rec.get("pemohon"),
        "pokok_perkara": pokok,
        "uu_diuji": uu_diuji,
        "impacted_corpus_docs": impacted_docs,
        "successor_corpus_docs": successor_docs,
        "pasal_diuji": pasal_diuji,
        "amar_kategori": classify_mk_amar(amar_full),
        "amar_lengkap": amar_full,
        "pertimbangan_inti": pertimbangan[:35000],
        "cited_regulations": cited_regs,
        "full_text": text,
        "pages": n_pages,
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "source": {
            "origin": "jdih.mkri.id",
            "pdf_url": rec.get("pdf_url"),
            "pdf_file": rec.get("pdf_file"),
        },
        "quality": {
            "ocr_suspect": avg_chars < 60,
            "has_amar": bool(amar_full),
        },
    }


def main() -> int:
    idx_path = MK_PDF_DIR / "index.json"
    if not idx_path.exists():
        print("Belum ada download-pdf/putusan_mk/index.json")
        return 1
    idx = json.loads(idx_path.read_text(encoding="utf-8"))
    if OUT_DIR.exists():
        for old in OUT_DIR.glob("*.json"):
            old.unlink()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest_items = []
    by_amar: Counter = Counter()
    by_uu: Counter = Counter()
    ocr_bad = 0

    for rec in idx:
        if not rec.get("downloaded") or not rec.get("pdf_file"):
            continue
        pdf_path = MK_PDF_DIR / rec["pdf_file"]
        if not pdf_path.exists():
            continue
        doc = fitz.open(pdf_path)
        pages = [pg.get_text() for pg in doc]
        n_pages = len(pages)
        avg = (sum(len(p.strip()) for p in pages) / n_pages) if n_pages else 0.0
        text = "\n\n".join(pages)

        item = parse_mk_text(rec, text, n_pages, avg)
        (OUT_DIR / f"{item['case_id']}.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        by_amar[item["amar_kategori"]] += 1
        for u in item["uu_diuji"]:
            by_uu[u] += 1
        if item["quality"]["ocr_suspect"]:
            ocr_bad += 1

        manifest_items.append({
            "case_id": item["case_id"],
            "nomor_perkara": item["nomor_perkara"],
            "tahun_registrasi": item["tahun_registrasi"],
            "tahun_putusan": item["tahun_putusan"],
            "tanggal_putusan": item["tanggal_putusan"],
            "pokok_perkara": item["pokok_perkara"],
            "uu_diuji": item["uu_diuji"],
            "impacted_corpus_docs": item["impacted_corpus_docs"],
            "successor_corpus_docs": item["successor_corpus_docs"],
            "pasal_diuji": item["pasal_diuji"],
            "amar_kategori": item["amar_kategori"],
            "cited_regulations": item["cited_regulations"],
            "ocr_suspect": item["quality"]["ocr_suspect"],
            "pages": n_pages,
            "path": f"knowledge_json/putusan_mk/{item['case_id']}.json",
            "pdf_url": item["source"]["pdf_url"],
        })

    manifest = {
        "total_cases": len(manifest_items),
        "by_amar": dict(sorted(by_amar.items())),
        "by_uu_diuji": dict(sorted(by_uu.items())),
        "ocr_suspect_count": ocr_bad,
        "cases": manifest_items,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Converted Putusan MK: {len(manifest_items)} | ocr_suspect={ocr_bad}")
    print("  by_amar:", manifest["by_amar"])
    print("  by_uu  :", manifest["by_uu_diuji"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
