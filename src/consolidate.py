# -*- coding: utf-8 -*-
"""S5-lite — konsolidasi teks TERBARU per pasal (tanpa riwayat/versi).

Instruksi perubahan diambil dari dokumen pengubah (bentuk "Pasal I" + butir
bernomor, atau pasal berskop "Beberapa ketentuan dalam UU X ... diubah").
Hanya pola yang dikenali (RULE) yang diterapkan; sisanya dicatat unparsed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.ids import parse_document_ref
from src.textutil import normalize_headings

ITEM_RE = re.compile(r"(?im)^[ \t]*(\d+)\.\s+")
BERBUNYI_RE = re.compile(r"berbunyi(?:\s+sebagai)?\s+berikut\s*:?\s*", re.I)
SCOPE_RE = re.compile(
    r"(?i)Beberapa ketentuan dalam (Undang-Undang|Peraturan Pemerintah|Peraturan Menteri Keuangan)"
    r"\s+Nomor\s+(\d+)\s+Tahun\s+(\d{4})"
)
_PN = r"(\d+(?:\s*[A-Z](?![a-z]))?)"
PASAL_REF_RE = re.compile(rf"(?i)Pasal\s+{_PN}")
SISIP_RE = re.compile(
    rf"(?i)Di\s*antara\s+Pasal\s+{_PN}\s+dan\s+(?:Pasal\s+{_PN}|BAB\s+[IVXLC]+[A-Z]?)\s+disisipkan"
)
# "Menambah ketentuan baru di antara Pasal 11 dan Pasal 12 yang dijadikan Pasal 11A"
SISIP2_RE = re.compile(
    rf"(?i)(?:di\s*antara|diantara)\s+Pasal\s+{_PN}\s+dan\s+(?:Pasal\s+{_PN}|BAB\s+[IVXLC]+[A-Z]?)"
    rf".{{0,140}}?(?:dijadikan|disisipkan)\s+Pasal\s+{_PN}", re.S,
)
# "Sebelum Pasal 44 dalam BAB IX disisipkan 1 (satu) pasal, yakni Pasal 43A"
SISIP_BEFORE_RE = re.compile(
    rf"(?i)Sebelum\s+Pasal\s+{_PN}(?:\s+dalam\s+BAB\s+[IVXLC]+[A-Z]?)?\s+disisipkan"
)
YAKNI_RE = re.compile(rf"(?i)(?:yakni|yaitu|dijadikan)\s+Pasal\s+{_PN}")
HAPUS_RE = re.compile(rf"(?i)Pasal\s+{_PN}\s+dihapus")
QUOTE_CHARS = '"“”\''


def _norm_ref(s: Optional[str]) -> Optional[str]:
    if not s:
        return s
    return re.sub(r"\s+", "", s).upper()

# Target berdasarkan topik — dipakai saat nomor pada kalimat lingkup rusak OCR
# (mis. "Nomor T Tahun 1983" pada UU 7/2021). Tahun ikut dicocokkan.
TOPIC_TARGET = [
    (r"pajak penghasilan", "UU-1983-7"),
    (r"ketentuan umum dan tata cara perpajakan", "UU-1983-6"),
    (r"pajak pertambahan nilai", "UU-1983-8"),
    (r"pajak bumi dan bangunan", "UU-1985-12"),
]


def scope_target(text: str) -> Optional[str]:
    """Ambil document_id target dari kalimat 'Beberapa ketentuan dalam ...'.

    Fallback OCR: nomor satu huruf (mis. 'Nomor T Tahun 1983') dipetakan lewat
    topik yang disebut sesudah 'tentang'. Tidak menebak bila topik tak dikenal.
    """
    sm = SCOPE_RE.search(text)
    if sm:
        jenis = {"undang-undang": "UU", "peraturan pemerintah": "PP",
                 "peraturan menteri keuangan": "PMK"}[sm.group(1).lower()]
        return f"{jenis}-{sm.group(3)}-{int(sm.group(2))}"
    om = re.search(
        r"(?i)Beberapa ketentuan dalam (?:Undang-Undang|Peraturan Pemerintah|"
        r"Peraturan Menteri Keuangan)\s+Nomor\s+([A-Za-z])\s+Tahun\s+(\d{4})"
        r"\s+tentang\s+([^(\n]{3,120})", text)
    if om:
        tahun = om.group(2)
        topic = om.group(3).lower()
        for pat, did in TOPIC_TARGET:
            # document_id = JENIS-TAHUN-NOMOR (jenis boleh ber-dash)
            if pat in topic and did.rsplit("-", 2)[-2] == tahun:
                return did
    return None


def target_from_title(judul: str) -> Optional[str]:
    """Target perubahan dari judul 'Perubahan ... atas <peraturan>'."""
    m = re.search(
        r"(?i)perubahan\s+(?:pertama|kedua|ketiga|keempat|kelima|keenam|"
        r"ketujuh|kedelapan|kesembilan|kesepuluh)?\s*atas\s+(.+)$", judul or "")
    if not m:
        return None
    ref = parse_document_ref(m.group(1)[:200])
    return ref["document_id"] if ref else None


def _cut_penjelasan_lines(lines: List[str]) -> List[str]:
    """Potong PENJELASAN asli (abaikan kata PENJELASAN di daftar isi awal)."""
    min_idx = len(lines) // 4
    for i, ln in enumerate(lines):
        if i >= min_idx and re.match(r"^\s*PENJELASAN\b", ln):
            return lines[:i]
    return lines


def _extract_omnibus_scope_blocks(text: str) -> List[dict]:
    """Ekstrak blok pasal pembuka 'Beberapa ketentuan dalam ...' pada omnibus raksasa
    (mis. UU 6/2023 Cipta Kerja) tanpa tersesat di seratus lebih pasal non-pajak."""
    lines = _cut_penjelasan_lines(normalize_headings(text).splitlines())
    scope_Starts: List[Tuple[int, str]] = []
    for i, ln in enumerate(lines):
        if re.match(r"(?i)^\s*Beberapa ketentuan dalam\b", ln):
            # cari heading 'Pasal N' 1-5 baris di atas (toleran spasi OCR 'Pasal 1 1 1')
            p_idx, p_no = i, str(len(scope_Starts) + 1)
            for j in range(max(0, i - 6), i):
                m = re.match(r"^\s*Pasal\s+([0-9][0-9 ]*[A-Z]?)\s*$", lines[j])
                if m:
                    p_idx = j
                    p_no = re.sub(r"\s+", "", m.group(1))
                    break
            scope_Starts.append((p_idx, p_no))
    blocks: List[dict] = []
    for k, (start, p_no) in enumerate(scope_Starts):
        next_start = scope_Starts[k + 1][0] if k + 1 < len(scope_Starts) else len(lines)
        end = next_start
        # berhenti di heading Bagian / BAB atau Pasal top-level berikutnya (mis. Pasal 114)
        base_num = int(re.sub(r"[A-Z]+$", "", p_no)) if re.sub(r"[A-Z]+$", "", p_no).isdigit() else None
        for j in range(start + 1, next_start):
            if re.match(r"^\s*(?:Bagian\s+[A-Za-z]+|BAB\s+[IVXLC]+)\b", lines[j]):
                end = j
                break
            if base_num is not None:
                m_nx = re.match(rf"^\s*Pasal\s+{base_num + 1}\s*$", lines[j])
                if m_nx:
                    end = j
                    break
        blocks.append({"nomor": p_no, "text": "\n".join(lines[start + 1:end]).strip()})
    return blocks


def split_top_level_pasals(text: str) -> List[dict]:
    """Pecah batang tubuh dokumen pengubah menjadi pasal TOP-LEVEL.

    Dokumen omnibus (mis. UU 7/2021 HPP) memuat pasal kutipan di dalam butir
    amandemen. Parser struktur biasa memecah kutipan itu sebagai pasal baru,
    sehingga teks pasal amandemen terpotong. Fungsi ini memakai urutan nomor
    pasal top-level (1,2,3,...) dan preferensi heading yang diikuti kalimat
    'Beberapa ketentuan dalam ...' agar kutipan tetap berada di dalam blok.
    """
    if len(text) > 400_000 and text.count("Beberapa ketentuan dalam") >= 10:
        omni = _extract_omnibus_scope_blocks(text)
        if omni:
            return omni
    lines = _cut_penjelasan_lines(text.splitlines())
    heads: List[Tuple[int, str]] = []
    for i, ln in enumerate(lines):
        m = re.match(r"^\s*Pasal\s+(\d+[A-Z]?)\s*$", ln)
        if m:
            heads.append((i, m.group(1)))
    start = next((k for k, (_, n) in enumerate(heads) if n == "1"), None)
    if start is None:
        return []

    def next_text(pos: int) -> str:
        for j in range(pos + 1, min(pos + 4, len(lines))):
            s = lines[j].strip()
            if s:
                return s
        return ""

    top: List[Tuple[int, str]] = [heads[start]]
    expected = 2
    idx = start + 1
    while idx < len(heads):
        remaining = {n for _, n in heads[idx:]}
        while expected < 80 and str(expected) not in remaining:
            expected += 1
        if expected >= 80:
            break
        i, n = heads[idx]
        if n != str(expected):
            idx += 1
            continue
        if next_text(i).lower().startswith("beberapa ketentuan"):
            top.append((i, n))
            expected += 1
            idx += 1
            continue
        # kutipan "Pasal N" di dalam blok: cari heading N lain yang membuka
        # kalimat lingkup; bila ada, lewati yang sekarang (kutipan).
        later = next(
            (k for k in range(idx + 1, len(heads))
             if heads[k][1] == n
             and next_text(heads[k][0]).lower().startswith("beberapa ketentuan")),
            None)
        if later is not None:
            idx = later
            continue
        top.append((i, n))
        expected += 1
        idx += 1

    blocks = []
    for k, (i, n) in enumerate(top):
        end = top[k + 1][0] if k + 1 < len(top) else len(lines)
        blocks.append({"nomor": n, "text": "\n".join(lines[i + 1:end]).strip()})
    return blocks


def natural_key(nomor: str) -> Tuple[int, str]:
    m = re.match(r"(\d+)([A-Z]*)", str(nomor))
    if m:
        return (int(m.group(1)), m.group(2))
    return (10**9, str(nomor))


def norm_nomor(n):
    """Normalisasi nomor pasal korpus (OCR: '3O' -> '30')."""
    return re.sub(r"(?<=\d)O(?=\d|$)", "0", str(n).strip())


def _strip_quotes(s: str) -> str:
    return s.strip().strip(QUOTE_CHARS).strip()


def _pasal_pattern(nomor: str) -> str:
    """Regex nomor pasal toleran spasi OCR ('11A' juga cocok dengan '1 1A')."""
    return r"Pasal\s+" + r"\s*".join(re.escape(ch) for ch in str(nomor))


def fix_ocr_rates(text: str) -> str:
    """Normalisasi artefak OCR umum pada tabel tarif (mis. '5o/o' -> '5%')."""
    t = re.sub(r"(?i)(\d+)\s*[O0]\s*o\s*/\s*o", r"\g<1>0%", text)
    t = re.sub(r"(?i)(\d+)\s*o\s*/\s*o", r"\1%", text)
    t = re.sub(r"(?i)\bl(\d+)\s*%", r"1\1%", t)
    t = re.sub(r"(?<=\d)[Oo](?=[.,\d])", "0", t)
    t = re.sub(r"(?<=[.,\d])[Oo](?=\d|$)", "0", t)
    return t


def _new_text_from_block(block: str, target_nomor: str) -> Optional[str]:
    """Ambil teks pengganti dari blok setelah 'berbunyi sebagai berikut'.
    Buang artefak halaman, kutip pembuka/penutup, dan baris heading 'Pasal N'."""
    b = block.strip()
    if not b:
        return None
    # kutip pembuka di awal
    b = re.sub(r'^["\u201c]', "", b)
    # heading 'Pasal N' (boleh didahului artefak halaman; toleran spasi OCR)
    m = re.search(rf'(?im)^\s*["\u201c]?\s*{_pasal_pattern(target_nomor)}\s*$', b[:600])
    if m:
        b = b[m.end():]
    # kutip penutup di akhir blok (biasanya berdiri sendiri)
    b = re.sub(r'["\u201d]\s*$', "", b)
    text = fix_ocr_rates(b.strip())
    return text or None


def parse_item(item_text: str, amending_doc_id: str, default_target: Optional[str]):
    """Parse satu butir instruksi -> dict atau None (tidak dikenali)."""
    # OCR: '16E}' -> '16B' (tidak pernah ada '}' pada nomor pasal sah)
    t = re.sub(r"(?<=\d)E\}", "B", item_text.strip())
    instr = {"amending": amending_doc_id, "raw": t[:300], "target_doc": default_target}

    # Target baru hanya bila BUTIR INI membuka kalimat lingkup. Kalimat lingkup
    # di dalam teks pengganti (nested amendment) TIDAK mengubah target butir —
    # itu urusan _nested_instructions.
    if re.match(r"(?i)\s*Beberapa ketentuan dalam", t):
        st = scope_target(t)
        if st:
            instr["target_doc"] = st

    # Ambil kemunculan PERTAMA: teks kutipan bisa memuat frasa "berbunyi
    # sebagai berikut" lagi (mis. butir berikutnya yang gagal terpisah).
    bm = BERBUNYI_RE.search(t)
    if bm:
        intro, block = t[:bm.start()], t[bm.end():]
        # OCR kadang memecah nomor: "Pasal 1 1A" -> "Pasal 11A"
        intro_norm = re.sub(r"(?i)(Pasal\s+\d)\s+(\d+[A-Z]?)", r"\1\2", intro)
        refs = [_norm_ref(r) for r in PASAL_REF_RE.findall(intro_norm)]
        if not refs:
            return None
        target = refs[-1]  # target adalah Pasal terakhir yang disebut sebelum "berbunyi"

        def _make_sisip(after: Optional[str], before: Optional[str], new_nomor: str):
            # OCR: '278' di antara '27A' dan '28' -> '27B'
            if new_nomor and new_nomor.endswith("8"):
                base_d = re.sub(r"[A-Z]+$", "", after or before or "")
                if base_d and new_nomor[:-1] == base_d:
                    new_nomor = new_nomor[:-1] + "B"
            new_text = _new_text_from_block(block, new_nomor)
            if new_text is None:
                return None
            instr.update({"action": "SISIP", "target": new_nomor,
                          "insert_after": after, "insert_before": before,
                          "new_text": new_text})
            m_tail = re.search(r"(?i)(?:yakni|yaitu|dijadikan)\s+(.+)$", intro_norm, re.S)
            if m_tail:
                multi = [_norm_ref(r) for r in PASAL_REF_RE.findall(m_tail.group(1))]
                if len(multi) >= 2:
                    instr["_multi_sisip"] = (multi, block)
            return instr

        sisip = SISIP_RE.search(intro_norm)
        if sisip:
            after = _norm_ref(sisip.group(1))
            before = _norm_ref(sisip.group(2))
            m_yn = YAKNI_RE.search(intro_norm)
            new_nomor = _norm_ref(m_yn.group(1)) if m_yn else f"{after}A"
            return _make_sisip(after, before, new_nomor)
        sisip2 = SISIP2_RE.search(intro_norm)
        if sisip2:
            return _make_sisip(_norm_ref(sisip2.group(1)),
                               _norm_ref(sisip2.group(2)),
                               _norm_ref(sisip2.group(3)))
        sisip_b = SISIP_BEFORE_RE.search(intro_norm)
        if sisip_b:
            before = _norm_ref(sisip_b.group(1))
            m_yn = YAKNI_RE.search(intro_norm)
            new_nomor = _norm_ref(m_yn.group(1)) if m_yn else target
            return _make_sisip(None, before, new_nomor)

        # OCR: intro "Pasal 168" tapi heading di blok "Pasal 16B" (atau 16E}->16B)
        if target.endswith("8") and not re.search(
                rf'(?im)^\s*["\u201c]?\s*{_pasal_pattern(target)}\s*$', block[:600]):
            alt = target[:-1] + "B"
            if re.search(rf'(?im)^\s*["\u201c]?\s*{_pasal_pattern(alt)}\s*$', block[:600]):
                target = alt
        new_text = _new_text_from_block(block, target)
        if new_text is None:
            return None
        # Kutipan penuh bila heading "Pasal target" muncul di awal blok,
        # boleh didahului artefak halaman (mis. "SK No ...", "- 56 -").
        full_quote = bool(re.search(
            rf'(?im)^\s*["\u201c]?\s*{_pasal_pattern(target)}\s*$', block[:600]))
        keseluruhan = "keseluruhan" in intro.lower()
        instr.update({"action": "UBAH", "target": target, "new_text": new_text,
                      "ayat_level": not (full_quote or keseluruhan)})
        return instr

    hm = HAPUS_RE.search(t)
    if hm:
        instr.update({"action": "HAPUS", "target": _norm_ref(hm.group(1))})
        return instr
    return None


def _split_multi_sisip(instr: dict) -> List[dict]:
    """Pecah sisipan jamak ('Pasal 16A, Pasal 16B, ...') menjadi satu instruksi per pasal."""
    info = instr.pop("_multi_sisip", None)
    if not info:
        return [instr]
    targets, block = info
    # Cari posisi awal heading masing-masing pasal target di dalam block
    # (abaikan baris elipsis seperti '"Pasal 16A…').
    pos: List[Tuple[int, str]] = []
    search_from = 0
    for t in targets:
        pat = re.compile(
            rf'(?im)^\s*["\u201c]?\s*{_pasal_pattern(t)}\s*$')
        m = pat.search(block, search_from)
        if m is None:
            # fallback: izinkan teks lanjut di baris yang sama tapi bukan elipsis
            pat2 = re.compile(
                rf'(?im)^\s*["\u201c]?\s*{_pasal_pattern(t)}(?!\s*[…\.])(?:\s+|$)')
            m = pat2.search(block, search_from)
        if m is None:
            return [instr]
        pos.append((m.start(), t))
        search_from = m.end()
    out: List[dict] = []
    prev_after = instr.get("insert_after")
    for k, (start, t) in enumerate(pos):
        end = pos[k + 1][0] if k + 1 < len(pos) else len(block)
        txt = _new_text_from_block(block[start:end], t)
        if not txt:
            continue
        sub = dict(instr)
        sub["target"] = t
        sub["insert_after"] = prev_after
        sub["insert_before"] = instr.get("insert_before") if k == len(pos) - 1 else None
        sub["new_text"] = txt
        out.append(sub)
        prev_after = t
    return out or [instr]


def _paragraph_items(text: str) -> List[Tuple[int, str]]:
    """Fallback: butir amandemen yang nomornya hilang dari ekstraksi PDF.

    Butir dikenali dari awal paragraf yang memuat kata kerja perubahan.
    Dipakai bila mode bernomor gagal atau melewatkan banyak butir (mis. UU 7/2021 HPP).
    """
    pat = re.compile(
        r"(?m)^[ \t]*(?:\d+(?:\s+\d+)?\.\s*)?(?:"
        r"(?:Ketentuan(?!\s+Umum)|Di\s*antara(?!\s+BAB)|Angka|Menambah|"
        r"Menghapus|Menyisipkan|Mencabut)\b"
        r"[^\n;]{0,220}?(?:\n[^\n;]{0,220}?){0,3}?"
        r"(?:diubah|dihapus|disisipkan|ditambahkan|menambah|menghapus|menyisipkan|mencabut|dijadikan)\b"
        r"|Mengubah\b.{0,260}?(?:diubah|berbunyi)\b"
        r"|Pasal\s+\d+[A-Z]?(?:\s+ayat\s+\([^)]+\))?\s+(?:diubah|dihapus)\b"
        r")", re.S)
    starts: List[int] = []
    for m in pat.finditer(text):
        s = m.start()
        seg = text[s:m.end()]
        # "Pasal 7. Ketentuan ..." -> mulai dari kata "Ketentuan"
        m2 = re.match(r"(?m)^[ \t]*(?:\d+\.\s*)?Pasal\s+\d+[A-Z]?\.\s*"
                      r"(Ketentuan|Di antara|Angka)", seg)
        if m2:
            s += m2.start(1)
        if not starts or s - starts[-1] > 5:
            starts.append(s)
    out: List[Tuple[int, str]] = []
    for k, s in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(text)
        out.append((k + 1, text[s:end]))
    return out


def split_amendment_items(text: str) -> List[Tuple[int, str]]:
    """Pisahkan butir amandemen TOP-LEVEL dari daftar bernomor di dalam kutipan.

    Butir amandemen berurutan (1,2,3,...) dan diawali kata kerja perubahan
    ('diubah', 'disisipkan', 'dihapus', 'ditambahkan'). Daftar bernomor milik
    pasal kutipan (mis. rincian objek PPh) tidak memenuhi syarat itu dan
    dikembalikan ke badan butir sebelumnya. Bila nomor butir hilang dari PDF
    (atau hanya sebagian kecil terbaca), dipakai fallback berbasis paragraf.
    """
    numbered = _numbered_items(text)
    para = _paragraph_items(text)
    if len(para) > len(numbered) and (len(numbered) < 3 or len(para) >= len(numbered) * 1.5):
        return para
    if len(numbered) >= 2:
        return numbered
    return para if len(para) > len(numbered) else numbered


def _numbered_items(text: str) -> List[Tuple[int, str]]:
    parts = ITEM_RE.split(text)
    items: List[Tuple[int, str]] = []
    expected = 1
    cur_num: Optional[int] = None
    cur_body: List[str] = []
    for k in range(1, len(parts) - 1, 2):
        num_s, body = parts[k], parts[k + 1]
        try:
            num = int(num_s)
        except ValueError:
            num = None
        head = body[:240]
        looks_top = bool(re.search(
            r"(?i)(diubah|disisipkan|dihapus|ditambahkan|menambah|mengubah|"
            r"menghapus|menyisipkan|mencabut)", head))
        accept = (num is not None and looks_top and (
            num == expected
            or (not items and num <= 5)
            or (num > expected and num <= expected + 2)))
        if accept:
            if cur_num is not None:
                items.append((cur_num, "".join(cur_body)))
            cur_num, cur_body = num, [body]
            expected = num + 1
        elif cur_num is not None:
            cur_body.append(f"{num_s}. {body}")
    if cur_num is not None:
        items.append((cur_num, "".join(cur_body)))
    return items


_REVOKE_PASAL_RE = re.compile(
    r"(?is)(?:ketentuan\s+)?Pasal\s+(\d+[A-Z]?)\s+"
    r"(Undang-Undang|Peraturan Pemerintah|Peraturan Menteri Keuangan)\s+"
    r"Nomor\s+([\dO]+)\s+Tahun\s+([\dO]{4})[^;]{0,600}?"
    r"dicabut\s+dan\s+dinyatakan\s+tidak\s+berlaku"
)


def _extract_revocations(doc_id: str, text: str) -> List[dict]:
    """Tangkap pencabutan pasal tertentu lintas-dokumen (mis. PP 55/2022 Pasal 72b)."""
    out: List[dict] = []
    if "dicabut dan dinyatakan tidak berlaku" not in text.lower():
        return out
    jmap = {"undang-undang": "UU", "peraturan pemerintah": "PP",
            "peraturan menteri keuangan": "PMK"}
    for m in _REVOKE_PASAL_RE.finditer(text):
        pno = _norm_ref(m.group(1))
        jenis = jmap[m.group(2).lower()]
        no = int(m.group(3).replace("O", "0"))
        thn = m.group(4).replace("O", "0")
        out.append({
            "amending": doc_id,
            "action": "HAPUS",
            "target": pno,
            "target_doc": f"{jenis}-{thn}-{no}",
            "raw": m.group(0)[:300],
            "ordinal": None,
        })
    return out


def extract_instructions(doc_id: str, provisions: List[dict],
                         default_target: Optional[str] = None) -> List[dict]:
    """Kumpulkan instruksi dari provisions dokumen pengubah.

    ``default_target`` dipakai bila pasal tidak menyebut kalimat lingkup
    (mis. UU 17/2000 — target hanya ada di judul 'Perubahan ... atas UU 7/1983').
    """
    out: List[dict] = []
    pasals = [p for p in provisions if p["level"] == "PASAL"]
    roman = any(re.match(r"^[IVXLC]+$", str(p["nomor"])) for p in pasals)

    for p in pasals:
        text = p.get("text") or ""
        out.extend(_extract_revocations(doc_id, text))
        # Lingkup langsung = kalimat sebelum "berbunyi sebagai berikut".
        # Kalimat "Beberapa ketentuan dalam ..." di dalam teks pengganti
        # adalah nested amendment, bukan target butir ini.
        bm = BERBUNYI_RE.search(text)
        intro = text[:bm.start()] if bm else text
        target = scope_target(intro) or default_target
        if not roman and target is None:
            continue  # dokumen numerik: hanya pasal yang menyebut lingkup UU target
        items = [(1, text)] if _is_outer_nested(text) else split_amendment_items(text)
        if not items and roman:
            # Pasal I tunggal dengan daftar panjang sebelum 'diubah' (mis. Perppu 5/2008)
            items = [(1, text)]
        for n, itext in items:
            ins = parse_item(itext, doc_id, target)
            if ins is None:
                continue
            for sub in _split_multi_sisip(ins):
                sub["ordinal"] = n
                out.append(sub)
    return out


def _is_outer_nested(text: str) -> bool:
    """True bila pasal mengganti satu pasal yang isinya amandemen nested.

    Contoh PMK 53/2025 Pasal I: "Ketentuan Pasal 20 dalam PMK 11/2025 ...
    berbunyi sebagai berikut: Pasal 20 Beberapa ketentuan dalam PMK 81/2024 ...
    diubah sebagai berikut: 1. ...". Butir 1-4 milik nested, bukan top-level.
    """
    bm = BERBUNYI_RE.search(text)
    if not bm:
        return False
    if not re.match(r"(?is)\s*Ketentuan\s+Pasal\s+\d+[A-Z]?\b", text[:bm.start()]):
        return False
    after = text[bm.end():bm.end() + 500]
    return bool(re.match(
        r"(?is)\s*[\"\u201c]?\s*Pasal\s+\d+[A-Z]?\s+Beberapa ketentuan dalam",
        after))


def apply_instruction(state: Dict[str, str], order: List[str], ins: dict) -> Tuple[bool, str]:
    action = ins["action"]
    target = ins["target"]
    if action in ("UBAH", "HAPUS") and target not in state and target.endswith("8"):
        # OCR: '168' -> '16B', '448' -> '44B' bila nomor berakhir 8 tidak ada di dokumen
        alt = target[:-1] + "B"
        if alt in state:
            target = alt
    if action == "UBAH":
        if target not in state:
            return False, f"target {target} tidak ada"
        state[target] = ins["new_text"]
        return True, "ok"
    if action == "SISIP":
        if target in state:
            return False, f"sisipan {target} sudah ada"
        after = ins.get("insert_after")
        before = ins.get("insert_before")
        if after in order:
            order.insert(order.index(after) + 1, target)
        elif before in order:
            order.insert(order.index(before), target)
        else:
            order.append(target)
        state[target] = ins["new_text"]
        return True, "ok"
    if action == "HAPUS":
        if target not in state:
            return False, f"target {target} tidak ada untuk dihapus"
        del state[target]
        if target in order:
            order.remove(target)
        return True, "ok"
    return False, f"aksi tidak dikenal {action}"


def _nested_instructions(new_text: str, amending: str, target_id: str) -> List[dict]:
    """Instruksi di dalam teks pengganti (nested amendment).

    Contoh: PMK 53/2025 mengubah Pasal 20 PMK 11/2025; Pasal 20 baru itu
    memuat 'Beberapa ketentuan dalam PMK 81/2024 ... diubah sebagai berikut'.
    """
    if scope_target(new_text) != target_id:
        return []
    marks = list(re.finditer(r"(?i)sebagai berikut\s*:?", new_text))
    body = new_text[marks[-1].end():] if marks else new_text
    out: List[dict] = []
    parts = ITEM_RE.split(body)
    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            ins = parse_item(parts[i + 1], amending, target_id)
            if ins is not None:
                ins["ordinal"] = int(parts[i]) if parts[i].isdigit() else None
                ins["nested"] = True
                out.append(ins)
    return out


def _apply_ins(ins: dict, am_id: str, state: Dict[str, str], order: List[str],
               applied: List[dict], unparsed: List[dict]) -> None:
    if ins.get("ayat_level"):
        unparsed.append({"amending": am_id, "ordinal": ins.get("ordinal"),
                         "reason": "ayat-level (lite belum menangani)",
                         "raw": ins["raw"]})
        return
    ok, msg = apply_instruction(state, order, ins)
    rec = {"amending": am_id, "ordinal": ins.get("ordinal"),
           "action": ins["action"], "target": ins["target"],
           "source_quote": ins["raw"][:200]}
    if ins.get("nested"):
        rec["nested"] = True
    (applied if ok else unparsed).append({**rec, "note": msg})


def consolidate(target_id: str, chain: List[str], docs_dir: Path,
                out_dir: Path, text_dir: Optional[Path] = None) -> dict:
    """Bangun teks terbaru target dari rantai pengubah (tanpa riwayat)."""
    target = json.loads((docs_dir / f"{target_id}.json").read_text(encoding="utf-8"))
    pasals = [p for p in target.get("provisions", []) if p["level"] == "PASAL"]
    articles = [{"nomor": norm_nomor(a["nomor"]), "text": a.get("text") or ""}
                for a in target.get("articles", [])]
    # Dasar: articles tim (lengkap) — teks parsed provisions menimpa bila ada
    # (agar pasal yang gagal di-parse TIDAK hilang dari konsolidasi).
    state = {a["nomor"]: a["text"] for a in articles}
    for p in pasals:
        state[str(p["nomor"])] = p.get("text") or ""
    if not state and pasals:
        state = {str(p["nomor"]): p.get("text") or "" for p in pasals}
    order = sorted(state.keys(), key=natural_key)

    applied: List[dict] = []
    unparsed: List[dict] = []
    text_dir = Path(text_dir) if text_dir else docs_dir.parent / "text"
    sources: Dict[str, str] = {}
    for am_id in chain:
        path = docs_dir / f"{am_id}.json"
        if not path.exists():
            unparsed.append({"amending": am_id, "reason": "dokumen pengubah tidak ada"})
            continue
        am = json.loads(path.read_text(encoding="utf-8"))
        provisions = am.get("provisions", [])
        provision_source = "provisions"
        text_path = text_dir / f"{am_id}.txt"
        if text_path.exists():
            raw = text_path.read_text(encoding="utf-8", errors="replace")
            # Omnibus: >1 kalimat lingkup -> kutipan pasal di dalam butir
            # membuat parser struktur memotong blok; pakai split top-level.
            if raw.count("Beberapa ketentuan dalam") >= 2:
                blocks = split_top_level_pasals(raw)
                if blocks:
                    provisions = [{"level": "PASAL", "nomor": b["nomor"],
                                   "text": b["text"]} for b in blocks]
                    provision_source = "text_top_level"
        sources[am_id] = provision_source
        default_target = target_from_title(am.get("judul") or "")
        if default_target is None and target_id.startswith("PERDA-") and re.search(
                r"(?i)peraturan\s+daerah\b.*perubahan\s+.*atas\s+peraturan\s+daerah",
                am.get("judul") or ""):
            default_target = target_id
        instructions = extract_instructions(am_id, provisions, default_target)
        if not instructions:
            reason = "tidak ada instruksi terdeteksi"
            if re.search(r"(?i)lampiran\s+[IVXLC]+\b.{0,120}?diubah",
                         "\n".join(p.get("text") or "" for p in provisions), re.S):
                reason = "perubahan hanya pada lampiran (tidak dikonsolidasikan)"
            unparsed.append({"amending": am_id, "reason": reason,
                             "provision_source": provision_source})
            continue
        for ins in instructions:
            tgt = ins.get("target_doc")
            if tgt == target_id:
                _apply_ins(ins, am_id, state, order, applied, unparsed)
            elif ins.get("new_text") and scope_target(ins["new_text"]) == target_id:
                nested = _nested_instructions(ins["new_text"], am_id, target_id)
                if not nested:
                    unparsed.append({"amending": am_id, "ordinal": ins.get("ordinal"),
                                     "reason": "nested amendment tidak terparsing",
                                     "raw": ins["raw"]})
                for nins in nested:
                    _apply_ins(nins, am_id, state, order, applied, unparsed)
            elif tgt is not None:
                continue  # instruksi untuk dokumen lain (omnibus)
            else:
                unparsed.append({"amending": am_id, "ordinal": ins.get("ordinal"),
                                 "reason": "target dokumen tidak terdeteksi",
                                 "raw": ins["raw"]})

    out = {
        "target_document_id": target_id,
        "chain": chain,
        "provision_sources": sources,
        "applied_count": len(applied),
        "unparsed_count": len(unparsed),
        "applied": applied,
        "unparsed": unparsed,
        "provisions": [{"nomor": n, "text": state[n]} for n in order],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{target_id}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
