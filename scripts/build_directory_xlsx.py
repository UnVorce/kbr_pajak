# -*- coding: utf-8 -*-
"""Bangkitkan indeks & riwayat pergerakan data (Excel .xlsx + CSV per sheet).

Output:
- data/directory/corpus_directory.xlsx (5 sheet: Ringkasan, Regulasi, Konsolidasi, Perda, Putusan)
- data/directory/*.csv (siap import ke Google Sheets)
- Salinan ke ../kbr_pajak/docs/corpus_directory.xlsx
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fase4_prepare import domain_for  # noqa: E402

DOCS = ROOT / "data" / "documents"
CONS = ROOT / "data" / "consolidated"
PERDA = ROOT / "data" / "perda"
CHUNKS_ALL = ROOT / "data" / "chunks" / "pending" / "all_t2_chunks.jsonl"
REPAIR_LOG = ROOT / "data" / "metadata_repair_log.json"
MANIFEST_KBR = ROOT.parent / "kbr_pajak" / "knowledge_json" / "metadata" / "manifest.json"
PERDA_MAN = ROOT / "data" / "perda_manifest.json"
JUR_MAN = ROOT / "data" / "jurisprudence_manifest.json"
MK_MAN = ROOT / "data" / "mk_manifest.json"
SEMA_MAN = ROOT / "data" / "sema_tun_manifest.json"
OUT_DIR = ROOT / "data" / "directory"
XLSX_PATH = OUT_DIR / "corpus_directory.xlsx"
KBR_XLSX = ROOT.parent / "kbr_pajak" / "docs" / "corpus_directory.xlsx"

GH_BASE = "https://github.com/UnVorce/kbr_pajak/blob/fatih-onto"

ORIGIN_LABEL = {
    "corpus": "korpus_awal_tim",
    "fetch": "crawl_bpk_fase1_3",
    "fetched_bpk": "crawl_bpk_fase1_3",
    "fetched_bpk_3b": "crawl_bpk_fase3b",
    "manual_download": "unduh_manual",
    "merged_pph_op": "merge_pph_op",
}


def _short_topic(judul: str, did: str) -> str:
    if not judul:
        return ""
    m = re.search(r"(?i)\btentang\s+(.+)$", judul)
    t = m.group(1) if m else judul
    t = re.sub(r"\s+", " ", t).strip().rstrip(".")
    return t[:140]


def _style_sheet(ws, headers: list[str], rows: list[list], link_cols: set[int]) -> None:
    hdr_fill = PatternFill("solid", fgColor="1F4E78")
    hdr_font = Font(bold=True, color="FFFFFF", size=10)
    link_font = Font(color="0563C1", underline="single", size=10)
    body_font = Font(size=10)

    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(1, col_idx)
        cell.fill = hdr_fill
        cell.font = hdr_font
        cell.alignment = Alignment(vertical="center", wrap_text=True)

    for r in rows:
        ws.append(r)
    for row_idx in range(2, len(rows) + 2):
        for col_idx in range(1, len(headers) + 1):
            c = ws.cell(row_idx, col_idx)
            val = c.value
            if col_idx in link_cols and isinstance(val, str) and val.startswith("http"):
                c.hyperlink = val
                c.font = link_font
            else:
                c.font = body_font
            c.alignment = Alignment(vertical="top", wrap_text=False)

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(rows) + 1}"

    for col_idx, h in enumerate(headers, 1):
        max_len = len(str(h))
        for r in rows[:200]:
            v = str(r[col_idx - 1] or "")
            max_len = max(max_len, min(len(v), 58))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 3, 62)


def _write_csv(name: str, headers: list[str], rows: list[list]) -> None:
    with (OUT_DIR / f"{name}.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST_KBR.read_text(encoding="utf-8"))
    perda_man = json.loads(PERDA_MAN.read_text(encoding="utf-8"))
    jur_man = json.loads(JUR_MAN.read_text(encoding="utf-8"))
    repairs = json.loads(REPAIR_LOG.read_text(encoding="utf-8")) if REPAIR_LOG.exists() else {}

    repaired_ids = {x["document_id"] for x in repairs.get("repairs", []) if x.get("status") == "ok"}

    # Hitung chunks T2 per document_id
    chunk_counts: Counter = Counter()
    if CHUNKS_ALL.exists():
        for line in CHUNKS_ALL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                chunk_counts[json.loads(line)["document_id"]] += 1

    # Indeks konsolidasi (induk & pengubah -> induk)
    cons_by_target: dict[str, dict] = {}
    amended_into: dict[str, list[str]] = defaultdict(list)
    for f in sorted(CONS.glob("*.json")):
        c = json.loads(f.read_text(encoding="utf-8"))
        tgt = c["target_document_id"]
        cons_by_target[tgt] = c
        for am in c.get("chain", []):
            amended_into[am].append(tgt)

    # Indeks PDF lokal regulasi
    local_pdfs: dict[str, str] = {}
    reg_pdf_idx = ROOT / "download-pdf" / "regulasi" / "index.json"
    if reg_pdf_idx.exists():
        for rec in json.loads(reg_pdf_idx.read_text(encoding="utf-8")):
            local_pdfs[rec["document_id"]] = f"fatih/download-pdf/regulasi/{rec['pdf_file']}"
    # manual PDFs
    manual_pdf_map = {
        "PMK-2019-128": "fatih/download-pdf/regulasi/128_PMK.010_2019Per.pdf",
        "PMK-2019-186": "fatih/download-pdf/regulasi/186~PMK.03~2019Per.pdf",
        "PMK-2022-234": "fatih/download-pdf/regulasi/234~PMK.03~2022Per.pdf",
        "PMK-2023-61": "fatih/download-pdf/regulasi/2023pmkeuangan061.pdf",
        "PMK-2024-69": "fatih/download-pdf/regulasi/2024pmkeuangan069.pdf",
        "PMK-2024-79": "fatih/download-pdf/regulasi/2024pmkeuangan079.pdf",
        "PMK-2026-28": "fatih/download-pdf/regulasi/2026pmkeuangan028.pdf",
        "PMK-2024-118": "fatih/download-pdf/regulasi/2024pmkeuangan118.pdf",
        "PMK-2024-136": "fatih/download-pdf/regulasi/2024pmkeuangan136.pdf",
        "PMK-2010-2": "fatih/download-pdf/regulasi/PMK Nomor 2 Tahun 2010.pdf",
        "PMK-2025-114": "fatih/download-pdf/regulasi/2025pmkeuangan114.pdf",
        "PER-DJP-2025-11": "fatih/download-pdf/regulasi/PER-11_PJ_2025_0.pdf",
        "PERPRES-2018-40": "fatih/download-pdf/regulasi/Perpres Nomor 40 Tahun 2018.pdf",
        "PERPU-2017-1": "fatih/download-pdf/regulasi/Perpu No 1 Tahun 2017.pdf",
        "UU-1997-19": "fatih/download-pdf/regulasi/UU Nomor 19 Tahun 1997.pdf",
        "UU-2000-19": "fatih/download-pdf/regulasi/UU 19_2000.pdf",
    }
    for k, v in manual_pdf_map.items():
        if (ROOT.parent / v).exists():
            local_pdfs.setdefault(k, v)

    # ---------------- Sheet 1: 1_Direktori_Regulasi ----------------
    reg_headers = [
        "document_id", "jenis", "tahun", "nama_peraturan", "domain", "topik_ringkas",
        "asal_perolehan", "nama_file_asal", "status_hukum_sumber", "peran_di_korpus",
        "active_for_rules", "status_ocr_dan_parsing", "jumlah_pasal_dasar",
        "jumlah_sub_unit", "pergerakan_konsolidasi", "jumlah_pasal_terbaru",
        "jumlah_chunk_t2", "path_json_dokumen", "path_json_terbaru",
        "path_pdf_lokal", "url_sumber_resmi", "url_pdf_resmi", "url_json_github",
        "catatan_riwayat",
    ]
    reg_rows: list[list] = []
    origin_stats: Counter = Counter()
    dom_stats: Counter = Counter()

    for m in manifest["documents"]:
        did = m["document_id"]
        d = json.loads((DOCS / f"{did}.json").read_text(encoding="utf-8"))
        src = d.get("source") or {}
        origin_code = src.get("origin") or ""
        origin_lbl = ORIGIN_LABEL.get(origin_code, origin_code)
        origin_stats[origin_lbl] += 1

        dom = ("NON_PAJAK_NOISE" if m.get("inactive_reason") in ("non_pajak_atau_digantikan", "panduan_atau_lampiran")
               else domain_for(did))
        dom_stats[dom] += 1

        orig_file = src.get("file") or src.get("source_file") or ""
        if did == "PMK-2024-127":
            orig_file = "2024pmkeuangan069.json (re-key)"

        if m["has_consolidated"]:
            peran = "INDUK_TERKONSOLIDASI"
        elif m.get("inactive_reason") == "sudah_dikonsolidasi_ke_dokumen_induk":
            peran = "PENGUBAH_MASUK_KONSOLIDASI"
        elif m.get("inactive_reason") == "klaster_pajak_sudah_dikonsolidasi":
            peran = "OMNIBUS_CK_DIKONSOLIDASI"
        elif m.get("inactive_reason") == "dicabut_atau_tidak_berlaku":
            peran = "DICABUT_HISTORIS"
        elif m.get("inactive_reason"):
            peran = m["inactive_reason"].upper()
        else:
            peran = "MANDIRI_AKTIF"

        ocr_st = (d.get("quality") or {}).get("ocr_status") or (
            "OCR_SUSPECT" if (d.get("quality") or {}).get("ocr_suspect") else "DIGITAL_OK"
        )
        parse_st = f"{ocr_st} / {d.get('structure') or '-'}"

        sub_cnt = sum(1 for p in d.get("provisions", []) if p.get("level") in ("AYAT", "HURUF", "ANGKA"))
        if did in cons_by_target:
            c = cons_by_target[did]
            chain = c.get("chain") or []
            pergerakan = " <- ".join([did] + chain) if chain else did
            pasal_terbaru = len(c.get("provisions", []))
            sub_cnt = sum(1 for p in c.get("sub_provisions", []) if p.get("level") in ("AYAT", "HURUF", "ANGKA"))
        elif did in amended_into:
            pergerakan = "masuk ke: " + ", ".join(amended_into[did])
            pasal_terbaru = ""
        else:
            pergerakan = "mandiri (tidak diubah)"
            pasal_terbaru = m["provisions_pasal_count"] or m["articles_count"]

        urls = [u for u in (m.get("source_urls") or []) if isinstance(u, str) and u.startswith("http")]
        url_page = next((u for u in urls if "/Download/" not in u and not u.endswith(".pdf")), urls[0] if urls else "")
        url_pdf = next((u for u in urls if "/Download/" in u or u.endswith(".pdf")), "")
        url_gh = f"{GH_BASE}/{m['recommended_source']}"

        notes = []
        if did in repaired_ids:
            notes.append("metadata BPK diperbaiki")
        if did == "PMK-2024-127":
            notes.append("re-key dari PMK-2024-69 (file tim salah label)")
        if did == "PMK-2009-105":
            notes.append("hal. 1 di-OCR Tesseract")
        if did == "PMK-2024-79":
            notes.append("PDF 2-kolom di-parse ulang (25 pasal)")
        if did == "PMK-2024-81":
            notes.append("konsolidasi memakai 466 articles dasar tim")
        if did == "PP-2010-94":
            notes.append("Pasal 2A otomatis dihapus (PP-2022-55 Ps.72b)")
        if did == "PER-DJP-2015-17":
            notes.append("judul manual; tanpa TXT sumber")
        if (d.get("lampiran")):
            notes.append(f"membawa {len(d['lampiran'])} node lampiran")

        reg_rows.append([
            did, m.get("jenis"), m.get("tahun"), m.get("judul"), dom,
            _short_topic(m.get("judul") or "", did),
            origin_lbl, orig_file, m.get("status_sumber") or "", peran,
            bool(m.get("active_for_rules")), parse_st,
            m.get("provisions_pasal_count", 0), sub_cnt, pergerakan,
            pasal_terbaru, chunk_counts.get(did, 0),
            m["document_path"], m["recommended_source"],
            local_pdfs.get(did, ""), url_page, url_pdf, url_gh,
            "; ".join(notes),
        ])

    # ---------------- Sheet 2: 2_Rantai_Konsolidasi ----------------
    cons_headers = [
        "target_document_id", "nama_dokumen_induk", "domain",
        "urutan_rantai_pengubah", "instruksi_diterapkan", "sisa_unparsed",
        "pasal_akhir", "sub_provisions_akhir", "memuat_cipta_kerja",
        "path_consolidated_json", "url_json_github",
    ]
    cons_rows: list[list] = []
    title_by_id = {m["document_id"]: m.get("judul") or "" for m in manifest["documents"]}
    for pinfo in perda_man["documents"]:
        title_by_id[pinfo["document_id"]] = pinfo.get("judul") or ""

    for tgt, c in sorted(cons_by_target.items()):
        chain = c.get("chain") or []
        cons_rows.append([
            tgt, title_by_id.get(tgt, tgt), domain_for(tgt),
            " -> ".join(chain), c.get("applied_count", 0), c.get("unparsed_count", 0),
            len(c.get("provisions", [])), len(c.get("sub_provisions", [])),
            "UU-2023-6" in chain,
            f"knowledge_json/consolidated/{tgt}.json",
            f"{GH_BASE}/knowledge_json/consolidated/{tgt}.json",
        ])

    # ---------------- Sheet 3: 3_Direktori_Perda ----------------
    perda_headers = [
        "document_id", "bpk_id", "tahun", "nama_perda", "status_sumber",
        "ocr_status", "structure", "jumlah_pasal", "articles_count",
        "masuk_pilot_fase4", "jumlah_chunk_t2", "path_json",
        "path_pdf_lokal", "url_bpk", "url_pdf_resmi", "url_json_github",
    ]
    perda_pdf_idx = json.loads((ROOT / "download-pdf" / "perda" / "index.json").read_text(encoding="utf-8")).get("downloaded", {})
    perda_rows: list[list] = []
    for d in perda_man["documents"]:
        did = d["document_id"]
        bid = str(d["bpk_id"])
        pinfo = perda_pdf_idx.get(bid, {})
        lpdf = f"fatih/download-pdf/perda/{pinfo['rel_path']}" if pinfo.get("rel_path") else ""
        ch_n = chunk_counts.get(did, 0)
        perda_rows.append([
            did, bid, d.get("tahun"), d.get("judul"), d.get("status_sumber"),
            d.get("ocr_status"), d.get("structure"), d.get("provisions_pasal_count", 0),
            d.get("articles_count", 0), ch_n > 0, ch_n, d.get("path"),
            lpdf, d.get("detail_url") or "", pinfo.get("pdf_url") or "",
            f"{GH_BASE}/{d.get('path')}",
        ])

    # ---------------- Sheet 4: 4_Direktori_Putusan ----------------
    jur_headers = [
        "case_id", "putusan_nomor", "klaster", "jenis_pajak",
        "tahun_pajak", "tahun_putusan", "amar_kategori",
        "regulasi_terkait", "jumlah_halaman", "ocr_suspect",
        "path_json", "url_setpp_pdf", "url_json_github",
    ]
    jur_rows: list[list] = []
    for c in jur_man["cases"]:
        jur_rows.append([
            c["case_id"], c.get("putusan_nomor"), c.get("klaster"), c.get("jenis_pajak"),
            c.get("tahun_pajak"), c.get("tahun_putusan"), c.get("amar_kategori"),
            ", ".join(c.get("cited_regulations") or []), c.get("pages", 0),
            bool(c.get("ocr_suspect")), c.get("path"),
            c.get("source_url") or "", f"{GH_BASE}/{c.get('path')}",
        ])

    # ---------------- Sheet 5: 5_Putusan_MK ----------------
    mk_man = json.loads(MK_MAN.read_text(encoding="utf-8")) if MK_MAN.exists() else {"cases": [], "by_amar": {}}
    sema_man = (json.loads(SEMA_MAN.read_text(encoding="utf-8")) if SEMA_MAN.exists()
                else {"items": [], "by_klaster": {}})

    mk_headers = [
        "case_id", "nomor_perkara", "tahun_registrasi", "tahun_putusan", "tanggal_putusan",
        "amar_kategori", "uu_diuji", "dokumen_korpus_terdampak", "pasal_diuji",
        "pemohon", "pokok_perkara", "jumlah_halaman", "ocr_suspect",
        "path_json", "url_pdf_mkri", "url_json_github", "catatan_review",
    ]
    mk_rows: list[list] = []
    for c in mk_man.get("cases", []):
        mk_rows.append([
            c["case_id"], c.get("nomor_perkara"), c.get("tahun_registrasi"),
            c.get("tahun_putusan"), c.get("tanggal_putusan"), c.get("amar_kategori"),
            ", ".join(c.get("uu_diuji") or []),
            ", ".join(c.get("impacted_corpus_docs") or []),
            ", ".join(c.get("pasal_diuji") or []),
            c.get("pemohon") or "", c.get("pokok_perkara") or "",
            c.get("pages", 0), bool(c.get("ocr_suspect")),
            c.get("path") or "", c.get("pdf_url") or "",
            f"{GH_BASE}/{c.get('path')}" if c.get("path") else "",
            "amar bersyarat: cek kutipan teks UU terdampak" if c.get("amar_kategori") == "KONSTITUSIONAL_BERSYARAT" else "",
        ])

    # ---------------- Sheet 6: 6_SEMA_Kamar_TUN ----------------
    sema_headers = [
        "sema_id", "sema_nomor", "tahun_rapat", "tahun_sema", "butir",
        "judul_rumusan", "klaster_pajak", "status_kaidah", "catatan_perubahan",
        "cited_regulations", "halaman_pdf", "path_json", "url_sumber_pdf",
        "url_json_github",
    ]
    sema_rows: list[list] = []
    for it in sema_man.get("items", []):
        if not it.get("is_pajak_terkait"):
            continue
        sema_rows.append([
            it["sema_id"], it.get("sema_nomor"), it.get("tahun_rapat"), it.get("tahun_sema"),
            it.get("butir"), it.get("judul_rumusan"), it.get("klaster_pajak"),
            it.get("status_kaidah"),
            (json.loads((ROOT / "data" / "sema_tun" / f"{it['sema_id']}.json")
                         .read_text(encoding="utf-8")).get("catatan_perubahan") or "")
            if (ROOT / "data" / "sema_tun" / f"{it['sema_id']}.json").exists() else "",
            ", ".join(it.get("cited_regulations") or []),
            "-".join(str(x) for x in (it.get("pages") or [])),
            it.get("path") or "", it.get("source_url") or "",
            f"{GH_BASE}/{it.get('path')}" if it.get("path") else "",
        ])

    # ---------------- Sheet 0: 0_Ringkasan ----------------
    sum_headers = ["Kategori", "Item", "Jumlah", "Keterangan"]
    sum_rows: list[list] = [
        ["Korpus Pusat", "Total regulasi kanonik (documents/)", len(manifest["documents"]), "Termasuk 21 dokumen unik hasil merge pph_op/"],
        ["Korpus Pusat", "Aktif untuk ekstraksi aturan (active_for_rules)", manifest["total_active_for_rules"], "Siap Fase 4"],
        ["Korpus Pusat", "Konsolidasi teks terbaru (consolidated/)", len(cons_by_target), "Termasuk Cipta Kerja (UU 6/2023), HPP, PMK-2024-118, Perda Semarang"],
        ["Perda PDRD", "Total Perda era HKPD (2023-2026)", perda_man["total_perda"], "493 DIGITAL_OK + 31 OCR_DONE (0 NEEDS_OCR)"],
        ["Perda PDRD", "Perda masuk pilot Fase 4", sum(1 for r in perda_rows if r[9]), "DKI Jakarta, Jabar, Kota Semarang, Kota Surabaya, Bali"],
        ["Yurisprudensi", "Total Putusan Pengadilan Pajak (SetPP)", jur_man["total_cases"], "6 klaster sengketa (0 ocr_suspect)"],
        ["Yurisprudensi", "Putusan MK pajak (dikabulkan/bersyarat)", len(mk_rows), "Hanya amar dikabulkan/dikabulkan sebagian; ditolak & NO dikecualikan"],
        ["Yurisprudensi", "Butir SEMA Kamar TUN terkait pajak", len(sema_rows), "SEMA 2012-2025, termasuk yang diubah SEMA lain"],
        ["Fase 4 Chunking", "Total chunks T2_RULE siap Colab", sum(chunk_counts.values()), "Maks 3.494 char/chunk (~2,0 juta input token)"],
    ]
    for k, v in sorted(origin_stats.items()):
        sum_rows.append(["Asal Perolehan (Pusat)", k, v, ""])
    for k, v in sorted(dom_stats.items()):
        sum_rows.append(["Domain (Pusat)", k, v, ""])

    wb = Workbook()
    ws0 = wb.active
    ws0.title = "0_Ringkasan"
    _style_sheet(ws0, sum_headers, sum_rows, set())

    ws1 = wb.create_sheet("1_Direktori_Regulasi")
    _style_sheet(ws1, reg_headers, reg_rows, {21, 22, 23})

    ws2 = wb.create_sheet("2_Rantai_Konsolidasi")
    _style_sheet(ws2, cons_headers, cons_rows, {11})

    ws3 = wb.create_sheet("3_Direktori_Perda")
    _style_sheet(ws3, perda_headers, perda_rows, {14, 15, 16})

    ws4 = wb.create_sheet("4_Direktori_Putusan")
    _style_sheet(ws4, jur_headers, jur_rows, {12, 13})

    ws5 = wb.create_sheet("5_Putusan_MK")
    _style_sheet(ws5, mk_headers, mk_rows, {15, 16})

    ws6 = wb.create_sheet("6_SEMA_Kamar_TUN")
    _style_sheet(ws6, sema_headers, sema_rows, {13, 14})

    wb.save(XLSX_PATH)
    shutil.copy2(XLSX_PATH, KBR_XLSX)

    _write_csv("0_Ringkasan", sum_headers, sum_rows)
    _write_csv("1_Direktori_Regulasi", reg_headers, reg_rows)
    _write_csv("2_Rantai_Konsolidasi", cons_headers, cons_rows)
    _write_csv("3_Direktori_Perda", perda_headers, perda_rows)
    _write_csv("4_Direktori_Putusan", jur_headers, jur_rows)
    _write_csv("5_Putusan_MK", mk_headers, mk_rows)
    _write_csv("6_SEMA_Kamar_TUN", sema_headers, sema_rows)

    print(f"Wrote {XLSX_PATH} & {KBR_XLSX} + 7 CSVs in {OUT_DIR}")
    print(f"  Sheets: Regulasi={len(reg_rows)}, Konsolidasi={len(cons_rows)}, "
          f"Perda={len(perda_rows)}, Putusan={len(jur_rows)}, "
          f"Putusan_MK={len(mk_rows)}, SEMA_TUN={len(sema_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
