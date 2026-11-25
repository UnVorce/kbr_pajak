#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fase 1 (v3.1) — Korpus & Kualitas.

1) Konversi korpus tim (../kbr_pajak/knowledge_json) -> JSON kanonik
   data/documents/<document_id>.json (+ salin TXT, dedupe hash, flag kualitas)
2) Enrich metadata dari halaman Detail BPK (judul bersih, status, tanggal, URL)
3) Ambil dokumen bolong: PDF -> teks -> cek OCR -> JSON kanonik
4) Registry CSV + laporan reports/fase_1.md

Util teks bersama ada di src/textutil.py.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

import pymupdf as fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ids import parse_document_ref  # noqa: E402
from src.crawl import BpkDetailParser, page_document_id, parse_date_id  # noqa: E402
from src.textutil import (  # noqa: E402
    GARBLED_RE,
    cut_penjelasan,
    split_pasal,
)

BPK = "https://peraturan.bpk.go.id"
CORPUS_JSON = ROOT.parent / "kbr_pajak" / "knowledge_json"
CORPUS_TXT = ROOT.parent / "kbr_pajak" / "knowledge_txt"
OUT_DOCS = ROOT / "data" / "documents"
OUT_TEXT = ROOT / "data" / "text"
OUT_TMP = ROOT / "data" / "cache" / "pdf_tmp"
REPORT = ROOT / "reports" / "fase_1.md"
REGISTRY = ROOT / "data" / "fase1_registry.csv"

UA = {"User-Agent": "KBR-Tax-Extraction/0.1 (proyek mahasiswa)"}
DELAY = 1.5
_last = 0.0


def throttle():
    global _last
    wait = DELAY - (time.monotonic() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.monotonic()


def http_get(url, retries=3):
    last_err = None
    for attempt in range(retries + 1):
        throttle()
        try:
            r = requests.get(url, headers=UA, timeout=90)
            if r.status_code == 200:
                return r
            last_err = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last_err = str(e)
        if attempt < retries:
            time.sleep([2, 5, 10][min(attempt, 2)])
    raise RuntimeError(f"gagal {url}: {last_err}")


def bpk_search(jenis_label, nomor, tahun, must_contain=None):
    q = urlencode({"keywords": jenis_label, "nomor": nomor, "tahun": str(tahun)})
    r = http_get(f"{BPK}/Search?{q}")
    soup = BeautifulSoup(r.text, "lxml")
    seen, hits = set(), []
    for a in soup.select('a[href^="/Details/"]'):
        href = a["href"]
        if href in seen:
            continue
        seen.add(href)
        txt = a.get_text(" ", strip=True)
        if must_contain and must_contain.casefold() not in txt.casefold():
            continue
        hits.append((href, txt))
    return hits


# ---------------------------------------------------------------------------
# Konversi korpus lama -> kanonik
# ---------------------------------------------------------------------------

def split_id(doc_id):
    """Pecah document_id -> (jenis, tahun, nomor). Aman untuk jenis ber-dash (PER-DJP)."""
    p = parse_document_ref(doc_id)
    if p:
        return p["jenis"], str(p["tahun"]), p["nomor_norm"]
    return doc_id.split("-")[0], None, None


def doc_id_from_filename(name: str):
    n = Path(name).stem
    m = re.match(r"(\d+)TAHUN(\d+)(UU|PP|PMK|PER)$", n, re.I)
    if m:
        jenis = {"UU": "UU", "PP": "PP", "PMK": "PMK", "PER": "PER-DJP"}[m.group(3).upper()]
        return f"{jenis}-{m.group(2)}-{int(m.group(1))}"
    m = re.match(r"(\d+)~PMK[.\s]*[\d]+~(\d{4})Per$", n, re.I)
    if m:
        return f"PMK-{m.group(2)}-{int(m.group(1))}"
    m = re.match(r"(\d{4})pmkeuangan(\d+)$", n, re.I)
    if m:
        return f"PMK-{m.group(1)}-{int(m.group(2))}"
    m = re.match(r"PER\s*-\s*(\d+)\.PJ[_ .]*(\d{4})$", n, re.I)
    if m:
        return f"PER-DJP-{m.group(2)}-{int(m.group(1))}"
    m = re.match(r"Salinan\s+(UU|PP)\s+Nomor\s+(\d+)\s+Tahun\s+(\d{4})", n, re.I)
    if m:
        return f"{m.group(1).upper()}-{m.group(3)}-{int(m.group(2))}"
    m = re.match(r"(UU|PP)\s+Nomor\s+(\d+)\s+Tahun\s+(\d{4})", n, re.I)
    if m:
        return f"{m.group(1).upper()}-{m.group(3)}-{int(m.group(2))}"
    return None


def canon_doc(doc_id, jenis, tahun, judul, articles, origin, extra=None):
    texts = "\n\n".join((a.get("full_text") or a.get("text") or "") for a in articles)
    out = {
        "document_id": doc_id,
        "jenis": jenis,
        "tahun": int(tahun) if tahun else None,
        "judul": judul,
        "articles": [
            {
                "locator": f"{doc_id}#BT/{a.get('pasal', '?')}",
                "part": "BATANG_TUBUH",
                "level": "PASAL",
                "nomor": str(a.get("pasal", "")),
                "text": a.get("full_text") or a.get("text") or "",
                "role": "SUBSTANTIVE",
                "text_hash": hashlib.sha256(
                    (a.get("full_text") or a.get("text") or "").encode()).hexdigest()[:16],
            }
            for a in articles
        ],
        "content_hash": hashlib.sha256(texts.encode()).hexdigest(),
        "source": origin,
        "quality": {
            "zero_pasal": len(articles) == 0,
            "garbled_title": bool(GARBLED_RE.search(judul or "")),
        },
    }
    if extra:
        out.update(extra)
    return out


def convert_corpus(records):
    """Konversi semua file korpus tim; kembalikan daftar record registry."""
    seen_hashes = {}
    for f in sorted(CORPUS_JSON.rglob("*.json")):
        rel = f.relative_to(CORPUS_JSON)
        name = f.name
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [SKIP] {name}: JSON rusak ({e})")
            continue
        meta = data.get("metadata", {})
        judul = (meta.get("title") or "").strip()
        articles = data.get("articles", [])
        doc_id = doc_id_from_filename(name)
        lamp = re.match(r"Lampiran\s*(\d)", name, re.I)
        if lamp:
            base = "PER-DJP-2015-17"
            did = f"{base}-LAMPIRAN-{lamp.group(1)}"
            rec = canon_doc(did, "LAMPIRAN", 2015,
                            f"Lampiran {lamp.group(1)} PER-17/PJ/2015 (NPPN)",
                            articles, {"origin": "corpus", "file": str(rel),
                                       "attachment_of": base})
        elif doc_id:
            jenis, tahun, _ = split_id(doc_id)
            rec = canon_doc(doc_id, jenis, tahun, judul, articles,
                            {"origin": "corpus", "file": str(rel)})
        else:  # manual / coretax
            slug = re.sub(r"[^a-z0-9]+", "-", name.rsplit(".", 1)[0].lower()).strip("-")
            did = f"CORETAX-{slug}" if "coretax" in name.lower() or "KT-" in name else f"MANUAL-{slug}"
            rec = canon_doc(did, "MANUAL", None, judul or name, articles,
                            {"origin": "corpus", "file": str(rel)})
        h = rec["content_hash"]
        has_content = bool(any((a.get("full_text") or a.get("text") or "").strip()
                               for a in articles))
        if has_content and h in seen_hashes:
            rec["quality"]["duplicate_of"] = seen_hashes[h]
        elif has_content:
            seen_hashes[h] = rec["document_id"]
        out = OUT_DOCS / f"{rec['document_id']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        txt_src = CORPUS_TXT / rel.with_suffix(".txt")
        if txt_src.exists():
            dst = OUT_TEXT / f"{rec['document_id']}.txt"
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(txt_src.read_bytes())
        flags = []
        if rec["quality"]["zero_pasal"]:
            flags.append("zero_pasal")
        if rec["quality"]["garbled_title"]:
            flags.append("garbled_title")
        if "duplicate_of" in rec["quality"]:
            flags.append(f"duplicate_of={rec['quality']['duplicate_of']}")
        records.append({
            "document_id": rec["document_id"], "jenis": rec["jenis"],
            "tahun": rec["tahun"], "judul": judul[:90], "pasal": len(articles),
            "hash": h[:10], "flags": ",".join(flags), "origin": "corpus",
            "status_sumber": "", "url": "",
        })
        print(f"  [corpus] {rec['document_id']:28} pasal={len(articles):>4} {flags or ''}")


# ---------------------------------------------------------------------------
# Enrich metadata dari BPK
# ---------------------------------------------------------------------------

JENIS_LABEL = {"UU": "Undang-Undang", "PP": "Peraturan Pemerintah",
               "PMK": "Peraturan Menteri Keuangan", "PER-DJP": "Peraturan Direktur Jenderal Pajak"}


def enrich_bpk(records):
    for rec in records:
        if rec["jenis"] not in JENIS_LABEL:
            continue
        doc_id = rec["document_id"]
        jenis, tahun, nomor = split_id(doc_id)
        hits = bpk_search(JENIS_LABEL[jenis], nomor, tahun,
                          must_contain=f"Nomor {int(nomor)}")
        if not hits:
            hits = bpk_search(JENIS_LABEL[jenis], nomor, tahun)
        if not hits:
            rec["flags"] += ",enrich_404"
            print(f"  [ENRICH-GAGAL] {doc_id}: tidak ditemukan di BPK")
            continue
        href, txt = hits[0]
        url = BPK + href
        try:
            html = http_get(url).text
            page = BpkDetailParser().parse(html, url)
            meta = page["meta"]
        except Exception as e:
            rec["flags"] += ",enrich_error"
            print(f"  [ENRICH-ERROR] {doc_id}: {e}")
            continue
        judul = meta.get("Judul") or ""
        path = OUT_DOCS / f"{doc_id}.json"
        if path.exists():
            d = json.loads(path.read_text(encoding="utf-8"))
            d["judul"] = judul
            d["status_sumber"] = meta.get("Status")
            d["tanggal_penetapan"] = parse_date_id(meta.get("Tanggal Penetapan"))
            d["tanggal_pengundangan"] = parse_date_id(meta.get("Tanggal Pengundangan"))
            d["tanggal_berlaku_sumber"] = parse_date_id(meta.get("Tanggal Berlaku"))
            d["sumber_publikasi"] = meta.get("Sumber")
            d["subjek_sumber"] = meta.get("Subjek")
            d["source_urls"] = [{"source": "peraturan.bpk.go.id", "url": url}]
            d["quality"]["garbled_title"] = bool(GARBLED_RE.search(judul))
            path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        rec["judul"] = judul[:90]
        rec["status_sumber"] = meta.get("Status") or ""
        rec["url"] = url
        if not rec["flags"]:
            rec["flags"] = "ok"
        print(f"  [enrich] {doc_id:28} status={meta.get('Status') or '-'}")


# ---------------------------------------------------------------------------
# Ambil dokumen baru (detail + PDF + OCR)
# ---------------------------------------------------------------------------

def fetch_new(doc_id, url_or_none, note, must_contain, records):
    print(f"  [FETCH] {doc_id} ({note})")
    records[:] = [r for r in records if r["document_id"] != doc_id]
    jenis, tahun, nomor = split_id(doc_id)
    if url_or_none:
        url = BPK + url_or_none
    else:
        hits = bpk_search(JENIS_LABEL[jenis], nomor, tahun, must_contain)
        if not hits:
            hits = bpk_search(JENIS_LABEL[jenis], nomor, tahun)
        if not hits:
            print(f"    -> TIDAK DITEMUKAN di BPK")
            records.append({"document_id": doc_id, "jenis": jenis, "tahun": tahun,
                            "judul": note, "pasal": 0, "hash": "", "flags": "not_found",
                            "origin": "fetch", "status_sumber": "", "url": ""})
            return
        href, txt = hits[0]
        url = BPK + href
        print(f"    -> {url} | {txt[:80]}")
    r = http_get(url)
    page = BpkDetailParser().parse(r.text, url)
    meta = page["meta"]
    judul = meta.get("Judul") or ""
    dl = next((a for a in page["pdf_links"] if a.startswith("/Download/")),
              next((a for a in page["pdf_links"] if a.startswith("/Read/")), None))
    if not dl:
        print(f"    -> TIDAK ADA tautan PDF")
        records.append({"document_id": doc_id, "jenis": jenis, "tahun": tahun,
                        "judul": judul[:90], "pasal": 0, "hash": "", "flags": "no_pdf",
                        "origin": "fetch", "status_sumber": meta.get("Status") or "", "url": url})
        return
    pdf_path = OUT_TMP / f"{doc_id}.pdf"
    if pdf_path.exists():
        pdf_bytes = pdf_path.read_bytes()
    else:
        pdf_bytes = http_get(BPK + dl).content
        pdf_path.write_bytes(pdf_bytes)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = [p.get_text() for p in doc]
    n_pages = len(pages)
    avg_chars = (sum(len(p) for p in pages) / n_pages) if n_pages else 0
    text = "\n\n".join(pages)
    batang, penjelasan = cut_penjelasan(text)
    pre, arts, struct = split_pasal(batang)
    ocr_suspect = avg_chars < 60
    rec = canon_doc(doc_id, jenis, tahun, judul, arts,
                    {"origin": "fetched_bpk", "url": url},
                    extra={
                        "status_sumber": meta.get("Status"),
                        "tanggal_penetapan": parse_date_id(meta.get("Tanggal Penetapan")),
                        "tanggal_pengundangan": parse_date_id(meta.get("Tanggal Pengundangan")),
                        "tanggal_berlaku_sumber": parse_date_id(meta.get("Tanggal Berlaku")),
                        "sumber_publikasi": meta.get("Sumber"),
                        "subjek_sumber": meta.get("Subjek"),
                        "source_urls": [{"source": "peraturan.bpk.go.id", "url": url},
                                        {"source": "peraturan.bpk.go.id", "url": BPK + dl,
                                         "type": "pdf"}],
                        "preamble": pre,
                        "penjelasan": penjelasan,
                        "structure": struct,
                    })
    rec["quality"]["ocr_suspect"] = ocr_suspect
    rec["quality"]["pages"] = n_pages
    rec["quality"]["avg_chars_page"] = round(avg_chars, 1)
    rec["quality"]["rough_split"] = True
    (OUT_DOCS / f"{doc_id}.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_TEXT / f"{doc_id}.txt").write_text(text, encoding="utf-8")
    flags = "ok"
    if ocr_suspect:
        flags += ",ocr_suspect"
    if len(arts) == 0:
        flags += ",zero_pasal"
    if struct != "NUMERIC":
        flags += f",structure={struct}"
    records.append({"document_id": doc_id, "jenis": jenis, "tahun": tahun,
                    "judul": judul[:90], "pasal": len(arts), "hash": rec["content_hash"][:10],
                    "flags": flags, "origin": "fetch",
                    "status_sumber": meta.get("Status") or "", "url": url})
    print(f"    -> struktur={struct} pasal={len(arts)} halaman={n_pages} "
          f"avg_chars={avg_chars:.0f} status={meta.get('Status') or '-'}"
          + ("  ⚠ OCR?" if ocr_suspect else ""))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    OUT_DOCS.mkdir(parents=True, exist_ok=True)
    OUT_TEXT.mkdir(parents=True, exist_ok=True)
    OUT_TMP.mkdir(parents=True, exist_ok=True)
    records = []

    print("== 1) Konversi korpus tim -> JSON kanonik ==")
    convert_corpus(records)

    print("\n== 1b) Re-parse dokumen 0-pasal dari TXT korpus ==")
    for rec in records:
        if rec["origin"] != "corpus" or "zero_pasal" not in rec["flags"]:
            continue
        did = rec["document_id"]
        txt_path = OUT_TEXT / f"{did}.txt"
        if not txt_path.exists() or txt_path.stat().st_size < 300:
            print(f"  [0-pasal] {did}: TXT tidak ada/terlalu pendek — tetap flagged")
            continue
        text = txt_path.read_text(encoding="utf-8", errors="replace")
        batang, _penj = cut_penjelasan(text)
        _pre, arts, _struct = split_pasal(batang)
        if len(arts) == 0:
            print(f"  [0-pasal] {did}: TXT ada tapi pola 'Pasal' tidak ketemu — tetap flagged")
            continue
        path = OUT_DOCS / f"{did}.json"
        d = json.loads(path.read_text(encoding="utf-8"))
        d["articles"] = [
            {"locator": f"{did}#BT/{a['pasal']}", "part": "BATANG_TUBUH",
             "level": "PASAL", "nomor": str(a["pasal"]), "text": a["full_text"],
             "role": "SUBSTANTIVE",
             "text_hash": hashlib.sha256(a["full_text"].encode()).hexdigest()[:16]}
            for a in arts
        ]
        d["content_hash"] = hashlib.sha256(
            "\n\n".join(a["text"] for a in d["articles"]).encode()).hexdigest()
        d["quality"]["zero_pasal"] = False
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        rec["pasal"] = len(arts)
        rec["flags"] = rec["flags"].replace("zero_pasal", "reparsed_from_txt").replace(",,", ",")
        print(f"  [reparse] {did}: {len(arts)} pasal dari TXT")

    print("\n== 2) Enrich metadata dari BPK ==")
    enrich_bpk(records)

    print("\n== 3) Ambil dokumen bolong ==")
    new_specs = [
        ("UU-1983-7", "/Details/46988/uu-no-7-tahun-1983", "UU PPh induk", None),
        ("UU-1994-9", "/Details/46230/uu-no-9-tahun-1994", "Amandemen KUP (1)", None),
        ("UU-2000-16", None, "Amandemen KUP (2)", "Ketentuan Umum"),
        ("UU-2007-28", "/Details/39916/uu-no-28-tahun-2007", "Amandemen KUP (3)", None),
        ("UU-2009-16", "/Details/38624/uu-no-16-tahun-2009", "Amandemen KUP (4)", None),
        ("UU-1994-12", None, "Amandemen PBB (re-extract)", "Pajak Bumi dan Bangunan"),
        ("PMK-2022-112", "/Details/217310/pmk-no-112pmk032022", "NPWP/NIK", None),
        ("PMK-2010-68", None, "Ambang PKP (PMK asli)", "Batasan Pengusaha Kecil"),
        ("PMK-2013-197", None, "Perubahan PMK 68/2010 (ambang PKP)",
         "Perubahan atas Peraturan Menteri Keuangan Nomor 68"),
        ("PMK-2025-53", None, "Perubahan PMK 81/2024", "Pajak"),
        ("PMK-2025-54", None, "Perubahan PMK 81/2024", "Pajak"),
        ("PMK-2026-1", None, "Perubahan PMK 81/2024", "Pajak"),
    ]
    for doc_id, url, note, mc in new_specs:
        fetch_new(doc_id, url, note, mc, records)

    print("\n== 4) Registry + laporan ==")
    cols = ["document_id", "jenis", "tahun", "judul", "status_sumber",
            "pasal", "hash", "flags", "origin", "url"]
    with REGISTRY.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in sorted(records, key=lambda x: (str(x["jenis"]), str(x["tahun"]), x["document_id"])):
            w.writerow(r)

    n_total = len(records)
    n_zero = sum(1 for r in records if "zero_pasal" in r["flags"])
    n_ocr = sum(1 for r in records if "ocr_suspect" in r["flags"])
    n_dup = sum(1 for r in records if "duplicate_of" in r["flags"])
    n_nf = sum(1 for r in records if "not_found" in r["flags"])
    n_garbled = sum(1 for r in records if "garbled_title" in r["flags"])
    n_fetch = sum(1 for r in records if r["origin"] == "fetch")

    lines = []
    lines += ["# Laporan Fase 1 — Korpus & Kualitas (v3.1)", "",
              "> Mengambil dokumen bolong dari peraturan.bpk.go.id, konversi korpus",
              "> tim ke JSON kanonik, enrich metadata, dedupe, dan cek kualitas (OCR).",
              "",
              "## Ringkasan", "",
              f"- Total dokumen di registry: **{n_total}**",
              f"- Baru diambil dari BPK: **{n_fetch}**",
              f"- Pasal kosong (0 pasal): **{n_zero}**",
              f"- Terindikasi OCR/pindaian: **{n_ocr}**",
              f"- Duplikat (hash sama): **{n_dup}**",
              f"- Judul rusak (diperbaiki dari BPK): **{n_garbled}**",
              f"- Tidak ditemukan di BPK: **{n_nf}**",
              "",
              "## Dokumen baru yang diambil", "",
              "| document_id | judul | status_sumber | pasal | flags |",
              "|---|---|---|---|---|"]
    for r in records:
        if r["origin"] == "fetch":
            lines.append(f"| `{r['document_id']}` | {r['judul'][:70]} | {r['status_sumber'] or '-'} | {r['pasal']} | {r['flags']} |")
    lines += ["", "## Masalah kualitas", ""]
    for r in records:
        bad = [f for f in r["flags"].split(",") if f and f != "ok"]
        if bad:
            lines.append(f"- `{r['document_id']}`: {', '.join(bad)}")
    lines += ["", "## Registry", "", f"Lihat `data/fase1_registry.csv` ({n_total} baris).",
              "", "## Langkah berikutnya",
              "", "- Review G1: periksa sampel dokumen baru + status flags.",
              "- Fase 2: parse struktur + konsolidasi-lite teks terbaru.",
              "", "*Agent berhenti di sini (G1).*"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:20]))
    print(f"\n[laporan] {REPORT}")
    print(f"[registry] {REGISTRY}")


if __name__ == "__main__":
    main()
