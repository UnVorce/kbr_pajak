# -*- coding: utf-8 -*-
"""Ekstrak & strukturkan Rumusan Hukum Rapat Pleno Kamar Tata Usaha Negara
Mahkamah Agung RI (2012-2025) dari 2026_buku_kompilasi_rumusan_kamar.pdf
ke data/sema_tun/*.json + data/sema_tun_manifest.json.
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

PDF_PATH = ROOT / "download-pdf" / "sema" / "2026_buku_kompilasi_rumusan_kamar.pdf"
OUT_DIR = ROOT / "data" / "sema_tun"
MANIFEST = ROOT / "data" / "sema_tun_manifest.json"
SOURCE_URL = "https://kepaniteraan.mahkamahagung.go.id/images/artikel/2026_buku_kompilasi_rumusan_kamar.pdf"

TAX_KW_RE = re.compile(
    r"(?i)\b(?:pajak|perpajakan|kepabeanan|cukai|bea masuk|ppn|pph|ppnbm|pbb|"
    r"skp|skpkbt|pengadilan pajak|bungkil|palm kernel|lpg|branch profit tax|"
    r"production sharing|faktur pajak|surat paksa|penyitaan pajak|"
    r"wajib pajak|direktorat jenderal pajak|direktur jenderal pajak|"
    r"direktorat jenderal bea|keberatan.*banding.*pasal 25)\b"
)

# Halaman 261..292 (1-based) = SEMA 2025..2014 (layout 1-kolom)
# Halaman 293..317 (1-based) = SEMA 2013 (SEMA 4/2014) & 2012 (SEMA 7/2012) (tabel 2-kolom)
SEMA_HDR_RE = re.compile(
    r"(?is)(?:^[A-Z]\.\s+)?RUMUSAN\s+(?:MASALAH\s+)?HUKUM\s+KAMAR\s+TATA\s+USAHA\s+NEGARA\s+"
    r"(?:TAHUN\s+(\d{4})\s*)?\(SEMA\s+NOMOR\s+0?(\d+)\s+TAHUN\s+(\d{4})\)"
)

AMENDED_NOTES = {
    "SEMA-2019-2-TUN-5": "Angka 5 huruf b (SKPKBT setelah putusan pidana perpajakan) diubah oleh SEMA Nomor 3 Tahun 2023 Rumusan Kamar TUN angka 4.",
    "SEMA-2012-7-TUN-6": "Angka 6 huruf b (kumulasi gugatan) direvisi oleh SEMA Nomor 1 Tahun 2025 Rumusan Kamar TUN angka 1.",
    "SEMA-2016-4-TUN-6": "Poin 6 disempurnakan oleh SEMA Nomor 3 Tahun 2018 Rumusan Kamar TUN angka 2.",
    "SEMA-2017-1-TUN-4": "Angka 4 (sikap diam MODI) diubah oleh SEMA Nomor 2 Tahun 2024 Rumusan Kamar TUN angka 2.",
}


EXTRA_REFS = {
    "SEMA-2025-1-TUN-4": ["UU-1983-7"],
    "SEMA-2025-1-TUN-5": ["UU-1983-6", "UU-2002-14"],
    "SEMA-2024-2-TUN-1": ["UU-1986-5", "UU-2002-14", "MK-2024-24-PUU-XXII"],
    "SEMA-2024-2-TUN-5": ["UU-1995-10"],
    "SEMA-2023-3-TUN-4": ["UU-1983-6"],
    "SEMA-2022-1-TUN-4": ["UU-2002-14"],
    "SEMA-2014-4-TUN-7-1": ["UU-2002-14"],
    "SEMA-2014-4-TUN-8-2": ["UU-2002-14"],
}


def _clean_text(s: str) -> str:
    s = s.replace("\xad", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _unwrap_for_cit(s: str) -> str:
    s = re.sub(r"-\n\s*", "-", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _classify_klaster(txt: str) -> str:
    low = txt.lower()
    if not TAX_KW_RE.search(txt):
        return "TUN_UMUM"
    if "kepabeanan" in low or "bea masuk" in low or "waterproof footwear" in low or "cukai" in low:
        if "perpajakan, kepabeanan" in low:
            return "KUP_PENGADILAN_PAJAK"
        return "KEPABEANAN_CUKAI"
    if "branch profit tax" in low or "pasal 26 ayat (4)" in low or "production sharing" in low:
        return "PPH_BADAN_BUT"
    if "pertambahan nilai" in low or "ppn" in low or "palm kernel" in low or "lpg" in low:
        return "PPN"
    if "pidana" in low and ("skp" in low or "skpkbt" in low or "ultimum remedium" in low):
        return "KUP_PIDANA_PAJAK"
    if "pengadilan pajak" in low or "peninjauan kembali" in low or "surat kuasa" in low:
        return "PENGADILAN_PAJAK_PK"
    if "pasal 26a" in low or "pasal 25" in low or "direktur jenderal pajak" in low:
        return "KUP_SENGKETA_PAJAK"
    return "PAJAK_LAINNYA"


def _page_blocks_text(pg: fitz.Page) -> str:
    """Urutkan blok teks menurut posisi vertikal; jika ada kotak nomor terpisah di
    margin kiri ('1.', '2a.', '4.' di p.273-274), sisipkan tepat di baris sejajarnya."""
    d_blocks = [b for b in pg.get_text("dict")["blocks"] if "lines" in b]
    num_lines: list[tuple[float, str]] = []
    body_blocks: list[tuple[float, float, str]] = []
    for b in d_blocks:
        x0, y0, x1, y1 = b["bbox"]
        if y0 > 596:
            continue
        lines_txt = []
        for ln in b["lines"]:
            if ln["bbox"][1] > 596:
                continue
            lt = "".join(s["text"] for s in ln["spans"]).strip()
            if not lt:
                continue
            is_bold = any((s.get("flags", 0) & 16) or "bold" in (s.get("font") or "").lower()
                          for s in ln["spans"])
            if ln["bbox"][2] < 92 and re.fullmatch(r"\d+[a-z]?\.", lt):
                num_lines.append((ln["bbox"][1], lt))
            else:
                lines_txt.append((ln["bbox"][1], ln["bbox"][0], lt, is_bold))
        if lines_txt:
            body_blocks.append((y0, x0, lines_txt))

    if num_lines:
        all_lines = []
        for by0, bx0, lts in body_blocks:
            for ly, lx, lt, is_b in lts:
                # Pada area header atas, baris judul bold ('RUMUSAN...' + '2020 (SEMA...)')
                # harus tampil sebelum kalimat non-bold 'Rapat Pleno...' yang tumpang tindih y-nya.
                hdr_ord = (0 if is_b else 1) if ly < 105 else 2
                all_lines.append([by0, hdr_ord, ly, lx, lt])
        for ny, ntxt in num_lines:
            best = min(
                (ln for ln in all_lines if abs(ln[2] - ny) < 12),
                key=lambda ln: abs(ln[2] - ny),
                default=None,
            )
            if best is not None and not best[4].startswith(ntxt):
                best[4] = f"{ntxt} {best[4]}"
        out_lines = [ln[4] for ln in sorted(all_lines, key=lambda x: (x[0], x[1], x[2], x[3]))]
        return _clean_text("\n".join(out_lines))

    raw_blocks = [
        b for b in pg.get_text("blocks")
        if b[6] == 0 and b[4].strip() and b[1] <= 596
        and not (b[1] < 35 and re.fullmatch(r"\d{1,4}", b[4].strip()))
    ]
    raw_blocks.sort(key=lambda b: (round(b[1] / 6) * 6, b[0]))
    return _clean_text("\n".join(b[4].strip() for b in raw_blocks))


def _extract_1col_semas(doc: fitz.Document) -> list[dict]:
    """Ekstrak SEMA 2025..2014 dari halaman 261..292."""
    chunks_by_page = []
    for p in range(260, 292):  # 0-based: 260..291 => 1-based 261..292
        t = _page_blocks_text(doc[p])
        # buang header buku di p.261 ("3\nRUMUSAN HUKUM\nRAPAT PLENO KAMAR...")
        t = re.sub(r"(?is)^RUMUSAN HUKUM\s+RAPAT PLENO KAMAR TATA USAHA NEGARA\s+MAHKAMAH AGUNG RI\s*", "", t)
        chunks_by_page.append((p + 1, t))

    joined_pages = "\n".join(f"<<<PAGE:{pno}>>>\n{ptxt}" for pno, ptxt in chunks_by_page)
    hdr_re = re.compile(
        r"(?is)(?:[A-Z]\.\s+)?RUMUSAN\s+(?:MASALAH\s+)?HUKUM\s+KAMAR\s+TATA\s+USAHA\s+NEGARA\s+"
        r"(?:TAHUN\s+(\d{4})\s*)?\(SEMA\s+NOMOR\s+0?(\d+)\s+TAHUN\s+(\d{4})\)"
    )
    matches = list(hdr_re.finditer(joined_pages))
    items_out = []
    for idx, m in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(joined_pages)
        seg = joined_pages[m.start():end]
        yr_rapat = int(m.group(1) or m.group(3))
        sema_no = int(m.group(2))
        yr_sema = int(m.group(3))

        pgs = [int(x) for x in re.findall(r"<<<PAGE:(\d+)>>>", joined_pages[:m.start()])]
        first_pg = pgs[-1] if pgs else 261
        seg_pgs = [int(x) for x in re.findall(r"<<<PAGE:(\d+)>>>", seg)]
        last_pg = seg_pgs[-1] if seg_pgs else first_pg

        seg_clean = re.sub(r"<<<PAGE:\d+>>>\n?", "", seg)
        body_start = re.search(r"(?i)menghasilkan rumusan hukum\s*(?:sebagai berikut\s*:)?", seg_clean)
        body = seg_clean[body_start.end():].strip() if body_start else seg_clean[m.end() - m.start():].strip()

        item_re = re.compile(r"(?m)^\s*(\d+[a-z]?)\.\s+")
        ims = list(item_re.finditer(body))
        accepted = []
        exp = 1
        for im in ims:
            raw_no = im.group(1)
            base = int(re.sub(r"[a-z]+$", "", raw_no))
            if base == exp or (raw_no.endswith(("a", "b")) and base == exp):
                accepted.append(im)
                if not raw_no.endswith("a"):
                    exp = base + 1
            elif base == exp + 1 and accepted:
                accepted.append(im)
                exp = base + 1
        if not accepted:
            continue

        for k, im in enumerate(accepted):
            i_end = accepted[k + 1].start() if k + 1 < len(accepted) else len(body)
            itxt = body[im.start():i_end].strip()
            ino = im.group(1)
            first_para = re.split(r"\n\s*\n", itxt)[0]
            first_para = re.sub(r"-\s*\n\s*", "", first_para)
            first_para = re.sub(r"\s+", " ", first_para).strip()
            judul = re.sub(r"^\d+[a-z]?\.\s*", "", first_para)[:160]
            sid = f"SEMA-{yr_sema}-{sema_no}-TUN-{ino}"
            items_out.append({
                "sema_id": sid,
                "sema_nomor": f"SEMA Nomor {sema_no} Tahun {yr_sema}",
                "tahun_rapat": yr_rapat,
                "tahun_sema": yr_sema,
                "butir": ino,
                "judul_rumusan": judul,
                "teks": itxt,
                "pages": [first_pg, last_pg],
            })
    return items_out


def _extract_2col_table_sema(
    doc: fitz.Document,
    page_range: range,
    sema_no: int,
    yr_sema: int,
    yr_rapat: int,
) -> list[dict]:
    """Ekstrak SEMA 2013 (4/2014) & 2012 (7/2012) yang berformat tabel 3 kolom
    dengan mengelompokkan baris kata per kolom terpisah agar kolom tengah & kanan
    tidak pernah tercampur."""
    # Kumpulkan baris per (page, y_bucket) hanya untuk deteksi posisi awal tiap nomor urut
    anchors: list[tuple[int, float, str]] = []
    for p in page_range:
        words = doc[p].get_text("words")
        rows_no: dict[int, list[tuple[float, str]]] = {}
        for x0, y0, x1, y1, w, *_ in words:
            if y0 < 52 or y0 > 594 or x0 >= 90:
                continue
            yk = round(y0 / 4) * 4
            rows_no.setdefault(yk, []).append((x0, w))
        for yk in sorted(rows_no):
            txt_no = " ".join(w for _, w in sorted(rows_no[yk])).strip()
            m = re.match(r"^(\d+)\.$", txt_no)
            if m:
                anchors.append((p, yk - 4.0, m.group(1)))

    # Ekstrak seluruh baris kolom Q (90..243) dan A (>=243) terpisah per halaman
    q_lines: list[tuple[int, float, str]] = []
    a_lines: list[tuple[int, float, str]] = []
    for p in page_range:
        words = doc[p].get_text("words")
        qy: dict[int, list[tuple[float, str]]] = {}
        ay: dict[int, list[tuple[float, str]]] = {}
        for x0, y0, x1, y1, w, *_ in words:
            if y0 < 52 or y0 > 594:
                continue
            yk = round(y0 / 4) * 4
            if 90 <= x0 < 243:
                qy.setdefault(yk, []).append((x0, w))
            elif x0 >= 243:
                ay.setdefault(yk, []).append((x0, w))
        for yk in sorted(qy):
            s = " ".join(w for _, w in sorted(qy[yk])).strip()
            if not s or "PERMASALAHAN" in s or re.fullmatch(r"BIDANG\s+[A-Z ]+", s):
                continue
            q_lines.append((p, float(yk), s))
        for yk in sorted(ay):
            s = " ".join(w for _, w in sorted(ay[yk])).strip()
            if not s or "HASIL RUMUSAN HUKUM" in s or s == "PLENOKAMAR":
                continue
            a_lines.append((p, float(yk), s))

    out = []
    for idx, (p0, y0, no) in enumerate(anchors, 1):
        p_end, y_end = (anchors[idx][0], anchors[idx][1]) if idx < len(anchors) else (page_range.stop, 9999.0)
        q_seg = [s for p, y, s in q_lines if (p, y) >= (p0, y0) and (p, y) < (p_end, y_end)]
        a_seg = [s for p, y, s in a_lines if (p, y) >= (p0, y0) and (p, y) < (p_end, y_end)]
        q_txt = _clean_text("\n".join(q_seg))
        a_txt = _clean_text("\n".join(a_seg))
        full = f"Permasalahan:\n{q_txt}\n\nHasil Rumusan Hukum:\n{a_txt}".strip()
        first_line = " ".join(l.strip() for l in q_txt.splitlines()[:3]).strip() or f"Butir {no}"
        first_line = re.sub(r"\s+", " ", first_line)
        sid = f"SEMA-{yr_sema}-{sema_no}-TUN-{idx}-{no}"
        pg_last = max([p for p, y, _ in (q_lines + a_lines) if (p, y) >= (p0, y0) and (p, y) < (p_end, y_end)] or [p0])
        out.append({
            "sema_id": sid,
            "sema_nomor": f"SEMA Nomor {sema_no} Tahun {yr_sema}",
            "tahun_rapat": yr_rapat,
            "tahun_sema": yr_sema,
            "butir": no,
            "judul_rumusan": first_line[:160],
            "teks": full,
            "pages": [p0 + 1, pg_last + 1],
        })
    return out


def main() -> int:
    doc = fitz.open(PDF_PATH)
    if OUT_DIR.exists():
        for old_f in OUT_DIR.glob("*.json"):
            old_f.unlink()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    raw_items = _extract_1col_semas(doc)
    # 2013 (SEMA 4/2014): p.293..303 (0-based 292..303)
    raw_items.extend(_extract_2col_table_sema(doc, range(292, 303), sema_no=4, yr_sema=2014, yr_rapat=2013))
    # 2012 (SEMA 7/2012): p.304..317 (0-based 303..317)
    raw_items.extend(_extract_2col_table_sema(doc, range(303, 317), sema_no=7, yr_sema=2012, yr_rapat=2012))

    # Deduplikasi & perkaya metadata + citasi peraturan
    manifest_items = []
    by_klaster: Counter = Counter()
    tax_count = 0

    for it in raw_items:
        txt = it["teks"]
        is_tax = bool(TAX_KW_RE.search(txt)) or (it["sema_id"] == "SEMA-2024-2-TUN-1")
        kl = "PENGADILAN_PAJAK_PK" if it["sema_id"] == "SEMA-2024-2-TUN-1" else _classify_klaster(txt)
        cits = extract_citations({
            "document_id": it["sema_id"],
            "jenis": "SEMA",
            "judul": it["judul_rumusan"],
            "preamble": "",
            "provisions": [{"level": "PASAL", "nomor": "1", "text": _unwrap_for_cit(txt)}],
            "penjelasan": "",
        })
        cited = sorted({c["resolved_document_id"] for c in cits} | set(EXTRA_REFS.get(it["sema_id"], [])))

        status_kaidah = "AKTIF"
        catatan_perubahan = AMENDED_NOTES.get(it["sema_id"], "")
        if catatan_perubahan:
            status_kaidah = "DIUBAH_SEMA_LAIN"

        rec = {
            **it,
            "is_pajak_terkait": is_tax,
            "klaster_pajak": kl,
            "status_kaidah": status_kaidah,
            "catatan_perubahan": catatan_perubahan or None,
            "cited_regulations": cited,
            "content_hash": hashlib.sha256(txt.encode("utf-8")).hexdigest(),
            "source": {
                "origin": "kepaniteraan.mahkamahagung.go.id",
                "url": SOURCE_URL,
                "pdf_file": PDF_PATH.name,
            },
        }
        (OUT_DIR / f"{it['sema_id']}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        by_klaster[kl] += 1
        if is_tax:
            tax_count += 1
        manifest_items.append({
            "sema_id": it["sema_id"],
            "sema_nomor": it["sema_nomor"],
            "tahun_rapat": it["tahun_rapat"],
            "tahun_sema": it["tahun_sema"],
            "butir": it["butir"],
            "judul_rumusan": it["judul_rumusan"],
            "is_pajak_terkait": is_tax,
            "klaster_pajak": kl,
            "status_kaidah": status_kaidah,
            "cited_regulations": cited,
            "pages": it["pages"],
            "path": f"knowledge_json/sema_tun/{it['sema_id']}.json",
            "source_url": SOURCE_URL,
        })

    manifest = {
        "total_items": len(manifest_items),
        "total_pajak_terkait": tax_count,
        "by_klaster": dict(sorted(by_klaster.items())),
        "items": manifest_items,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SEMA Kamar TUN selesai: total={len(manifest_items)} | pajak_terkait={tax_count}")
    print("  by_klaster:", manifest["by_klaster"])
    for m in manifest_items:
        if m["is_pajak_terkait"]:
            print(f"  [PAJAK] {m['sema_id']:22} ({m['klaster_pajak']:20}) | {m['judul_rumusan'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
