#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fase 2 (v3.1) — Parse struktur (S4) + konsolidasi-lite (S5).

1) Ambil 6 dokumen amandemen yang masih bolong (UU PPh/PPN chains)
2) Pastikan TXT semua dokumen regulasi tersedia
3) Parse struktur semua dokumen -> "provisions" di JSON kanonik
4) Konsolidasi-lite per rantai (config/consolidation.yaml) -> data/consolidated/
5) Laporan reports/fase_2.md

CATATAN ARAH (keputusan tim): pipeline berhenti di JSON. Tidak ada ekspor OWL —
masing-masing anggota membangun ontology sendiri dari JSON domainnya.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.fase1_korpus import (  # noqa: E402
    BPK,
    CORPUS_TXT,
    JENIS_LABEL,
    OUT_DOCS,
    OUT_TEXT,
    bpk_search,
    fetch_new,
    http_get,
    split_id,
)
from src.consolidate import consolidate  # noqa: E402
from src.parse_structure import parse_document  # noqa: E402
from src.crawl import BpkDetailParser, parse_date_id  # noqa: E402

import pymupdf as fitz  # noqa: E402

CHAIN_CFG = yaml.safe_load((ROOT / "config" / "consolidation.yaml").read_text(encoding="utf-8"))
OUT_CONS = ROOT / "data" / "consolidated"
REPORT = ROOT / "reports" / "fase_2.md"

NEW_FETCH = [
    ("UU-1991-7", "/Details/46659/uu-no-7-tahun-1991", "Amandemen PPh (1)", None),
    ("UU-1994-10", "/Details/46232/uu-no-10-tahun-1994", "Amandemen PPh (2)", None),
    ("UU-2000-17", "/Details/44968/uu-no-17-tahun-2000", "Amandemen PPh (3)", None),
    ("UU-2008-36", "/Details/39704/uu-no-36-tahun-2008", "Amandemen PPh (4)", None),
    ("UU-1994-11", "/Details/46235/uu-no-11-tahun-1994", "Amandemen PPN (1)", None),
    ("UU-2000-18", "/Details/44982/uu-no-18-tahun-2000", "Amandemen PPN (2)", None),
]

REG_JENIS = {"UU", "PP", "PMK", "PER-DJP"}


def ensure_txt(doc_id: str, source: dict):
    """TXT belum ada di data/text? Salin dari korpus tim bila asal corpus."""
    dst = OUT_TEXT / f"{doc_id}.txt"
    if dst.exists():
        return
    src = CORPUS_TXT / Path(source["file"]).with_suffix(".txt")
    if src.exists():
        dst.write_bytes(src.read_bytes())


def fetch_txt_only(doc_id: str, must_override: str = None, kw_override: str = None) -> bool:
    """Ambil PDF dari BPK dan simpan HANYA TXT (articles korpus tidak ditimpa)."""
    dst = OUT_TEXT / f"{doc_id}.txt"
    if dst.exists():
        return True
    jenis, tahun, nomor = split_id(doc_id)
    must = must_override or JENIS_LABEL.get(jenis)
    hits = bpk_search(JENIS_LABEL[jenis], nomor, tahun, must_contain=must)
    if not hits and kw_override:
        from urllib.parse import urlencode
        from bs4 import BeautifulSoup
        r = http_get(f"{BPK}/Search?{urlencode({'keywords': kw_override})}")
        soup = BeautifulSoup(r.text, "lxml")
        seen, hits = set(), []
        for a in soup.select('a[href^="/Details/"]'):
            if a["href"] in seen:
                continue
            seen.add(a["href"])
            hits.append((a["href"], a.get_text(" ", strip=True)))
    if not hits:
        hits = bpk_search(JENIS_LABEL[jenis], nomor, tahun)
    if not hits:
        print(f"  [TXT-GAGAL] {doc_id}: tidak ditemukan di BPK")
        return False
    href, txt = hits[0]
    url = BPK + href
    page = BpkDetailParser().parse(http_get(url).text, url)
    dl = next((a for a in page["pdf_links"] if a.startswith("/Download/")),
              next((a for a in page["pdf_links"] if a.startswith("/Read/")), None))
    if not dl:
        print(f"  [TXT-GAGAL] {doc_id}: tidak ada PDF")
        return False
    pdf = http_get(BPK + dl).content
    doc = fitz.open(stream=pdf, filetype="pdf")
    text = "\n\n".join(p.get_text() for p in doc)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    # update metadata di JSON tanpa menyentuh articles
    path = OUT_DOCS / f"{doc_id}.json"
    if path.exists():
        d = json.loads(path.read_text(encoding="utf-8"))
        d["source_urls"] = [{"source": "peraturan.bpk.go.id", "url": url},
                            {"source": "peraturan.bpk.go.id", "url": BPK + dl, "type": "pdf"}]
        if not d.get("status_sumber"):
            d["status_sumber"] = page["meta"].get("Status")
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [TXT-OK] {doc_id} <- {url}")
    return True


def parse_all(docs: list) -> list:
    stats = []
    for d in docs:
        did = d["document_id"]
        if d.get("jenis") not in REG_JENIS:
            continue
        ensure_txt(did, d.get("source", {}))
        txt_path = OUT_TEXT / f"{did}.txt"
        if not txt_path.exists():
            stats.append((did, "TXT_HILANG", 0, 0, 0))
            continue
        text = txt_path.read_text(encoding="utf-8", errors="replace")
        r = parse_document(did, text)
        d["structure"] = r["structure"]
        d["provisions"] = r["provisions"]
        d["preamble"] = r["preamble"]
        d["penjelasan"] = r["penjelasan"]
        d["penjelasan_articles"] = r["penjelasan_articles"]
        path = OUT_DOCS / f"{did}.json"
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        pasal = sum(1 for p in r["provisions"] if p["level"] == "PASAL")
        ayat = sum(1 for p in r["provisions"] if p["level"] == "AYAT")
        stats.append((did, r["structure"], pasal, ayat, len(r["penjelasan_articles"])))
    return stats


def main():
    OUT_CONS.mkdir(parents=True, exist_ok=True)
    records: list = []
    print("== 1) Ambil 6 dokumen amandemen yang bolong ==")
    for doc_id, url, note, mc in NEW_FETCH:
        if (OUT_DOCS / f"{doc_id}.json").exists() and (
                OUT_TEXT / f"{doc_id}.txt").exists():
            print(f"  [SUDAH ADA] {doc_id} — lewati")
            continue
        fetch_new(doc_id, url, note, mc, records)

    print("\n== 1b) Ambil TXT dokumen korpus yang belum punya teks ==")
    OVERRIDES = {
        "PER-DJP-2015-17": ("Direktur Jenderal Pajak", "PER-17/PJ/2015"),
        "UU-2022-1": ("Undang-undang (UU)", None),
        "PMK-2024-69": ("Peraturan Menteri Keuangan", "Peraturan Menteri Keuangan Nomor 69 Tahun 2024"),
        "PMK-2026-6": ("Peraturan Menteri Keuangan", None),
    }
    SKIP = {"PER-DJP-2015-17", "PMK-2024-69"}  # pencarian BPK tidak menemukan; NEEDS_REVIEW
    for f in sorted(OUT_DOCS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("jenis") not in REG_JENIS:
            continue
        if d["document_id"] in SKIP:
            d.setdefault("quality", {})["txt_status"] = "missing_needs_review"
            f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  [TXT-SKIP] {d['document_id']}: ditandai NEEDS_REVIEW (cari manual)")
            continue
        if not (OUT_TEXT / f"{d['document_id']}.txt").exists():
            must, kw = OVERRIDES.get(d["document_id"], (None, None))
            fetch_txt_only(d["document_id"], must, kw)

    print("\n== 2) Parse struktur semua dokumen regulasi ==")
    docs = []
    for f in sorted(OUT_DOCS.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("jenis") in REG_JENIS:
            docs.append(d)
    stats = parse_all(docs)

    print("\n== 3) Konsolidasi-lite ==")
    chain_stats = {}
    for target, chain in CHAIN_CFG["chains"].items():
        res = consolidate(target, chain, OUT_DOCS, OUT_CONS, OUT_TEXT)
        chain_stats[target] = res
        print(f"  {target}: applied={res['applied_count']} unparsed={res['unparsed_count']} "
              f"pasal_final={len(res['provisions'])}")

    print("\n== 4) Laporan ==")
    lines = ["# Laporan Fase 2 — Parse Struktur & Konsolidasi-lite (v3.1)", "",
             "> S4: parser Bab/Bagian/Paragraf/Pasal/Ayat/Huruf/Angka + dokumen pengubah",
             "> (Pasal I/II/...). S5-lite: konsolidasi teks TERBARU per pasal (tanpa riwayat).",
             "",
             "## Keputusan arah (disetujui tim)", "",
             "- Pipeline **berhenti di JSON** — tidak ada ekspor OWL dari pipeline.",
             "  Masing-masing anggota membangun ontology domainnya sendiri dari JSON ini,",
             "  agar struktur ontology tetap seragam sesuai kesepakatan tim.",
             "",
             "## Statistik parsing", "",
             "| document_id | struktur | pasal | ayat | penjelasan |",
             "|---|---|---|---|---|"]
    n_numeric = n_roman = n_unknown = n_missing = 0
    for did, struct, pasal, ayat, pj in stats:
        lines.append(f"| `{did}` | {struct} | {pasal} | {ayat} | {pj} |")
        if struct == "NUMERIC":
            n_numeric += 1
        elif struct == "AMENDING_ROMAN":
            n_roman += 1
        elif struct == "UNKNOWN":
            n_unknown += 1
        else:
            n_missing += 1
    lines += ["", f"- NUMERIC: {n_numeric} · AMENDING_ROMAN: {n_roman} · "
              f"UNKNOWN: {n_unknown} · TXT hilang: {n_missing}",
              "",
              "## Konsolidasi-lite", "",
              "| target | rantai | diterapkan | tak terparsing | pasal akhir |",
              "|---|---|---|---|---|"]
    for target, res in chain_stats.items():
        lines.append(f"| `{target}` | {' → '.join(res['chain'])} | "
                     f"{res['applied_count']} | {res['unparsed_count']} | "
                     f"{len(res['provisions'])} |")
    lines += ["",
              "## Catatan & batasan", "",
              f"- Lapisan Cipta Kerja **DITUNDA**: {', '.join(CHAIN_CFG.get('pending_ck', []))} — "
              "teks konsolidasi belum mencakup perubahan dari UU Cipta Kerja/Perpu (perlu "
              "penanganan khusus). Tercatat sebagai PENDING_CK, bukan diabaikan.",
              "- Instruksi `ayat_level` (hanya sebagian ayat dikutip tanpa pasal utuh) dicatat "
              "di `unparsed` — ditangani di fase berikutnya atau review manusia.",
              "- **TXT tidak ditemukan (NEEDS_REVIEW, cari manual):** `PER-DJP-2015-17` "
              "(NPPN) dan `PMK-2024-69` — pencarian BPK tidak menemukan halamannya; "
              "tim bisa mencarikan URL detailnya.",
              "- **Kualitas korpus tim:** `PP-2022-55` articles tim mengandung nomor OCR "
              "(`3O` → sudah dinormalisasi ke `30`) dan hanya mencakup 74 dari 131 pasal — "
              "konsolidasi PP-55 sebagian; perlu re-ekstraksi teks penuh.",
              "- `PMK-2022-112` & `UU-2023-6` punya heading yang belum sepenuhnya terpetakan "
              "(flag `rough_split`) — parser S4 akan disempurnakan bila domainnya diproses.",
              "- Hasil konsolidasi di `data/consolidated/<target>.json` (teks TERBARU per pasal).",
              "",
              "## Langkah berikutnya (G2)", "",
              "- Manusia memeriksa sampel hasil parsing + konsolidasi terhadap sumber resmi,",
              "  mis. tarif Pasal 17 UU PPh versi terkini.",
              "",
              "*Agent berhenti di sini (G2).*"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[laporan] {REPORT}")


if __name__ == "__main__":
    main()
