# -*- coding: utf-8 -*-
"""Util teks hukum bersama (dipakai Fase 1 & Fase 2): normalisasi heading,
potong penjelasan, split pasal kasar (dengan filter urutan)."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

GARBLED_RE = re.compile(r'[\\"{}<>]|I\.I|\(AN|NII|\bSASI\b|\bPEI\b|\bPENGGHASTLAN\b')

PASAL_ROMAN_RE = re.compile(r"(?im)^\s*Pasal\s+([IVXLC]+)\b")
PASAL_RE = re.compile(r"(?im)^\s*Pasal\s+(\d+[A-Z]?)\b")
PENJELASAN_RE = re.compile(r"(?m)^\s*(?:PENJELASAN|PENJE1ASAN)\b.*$")

# Heading pasal harus SATU BARIS PENUH (rujukan seperti "Pasal 17 ayat (3) UUD ..."
# tidak dihitung). Boleh ada kutip pembuka/penutup.
ROM_H = re.compile(r'(?im)^\s*["\u201c]?Pasal\s+([IVXLC]+)\.?\s*[\u201d"]?\s*$')
NUM_H = re.compile(r'(?im)^\s*["\u201c]?Pasal\s+(\d+[A-Z]?)(?:\.\s*)?[\u201d"]?\s*$')
# Untuk dokumen pengubah, heading romawi kadang menyatu dengan isi kalimat
# ("Pasal II Undang-undang ini mulai berlaku ...").
ROM_H2 = re.compile(r'(?im)^\s*["\u201c]?Pasal\s+([IVXLC]+)\b')

# PDF lama sering memisahkan "Pasal" dan nomornya ke dua baris -> gabungkan dulu.
JOIN_NUM = re.compile(r"(?m)^\s*Pasal\s*$\n^\s*(\d+[A-Z]?)\s*$")
JOIN_ROM = re.compile(r"(?m)^\s*Pasal\s*$\n^\s*([IVXLC]+)\s*$")

# Artefak OCR pada heading: "Pasa1 1" / "PasaI I" / "Pasal1" / "Pasa16" / "· Pasal 6" / "Pasall".
BULLET_H = re.compile(r"(?m)^([ \t]*)[·•]\s*(?=Pasa[1lI])")
ROM_LL_H = re.compile(r"(?m)^([ \t]*)Pasa[1lI][lI][ \t]*$")
OCR_H = re.compile(r"(?m)^([ \t]*)Pasa[1lI][ \t]*(?=(?:\d+[A-Z]?|[IVXLC]+)\b)")
DOT_H = re.compile(r'(?im)^([ \t]*["\u201c]?Pasal\s+\d+[A-Z]?)\s*\.\s*([\u201d"]?)\s*$')

ROMAN_VALUE = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def roman_to_int(s: str) -> int:
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total, prev = 0, 0
    for ch in reversed(s.upper()):
        v = vals.get(ch, 0)
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total


# Artefak OCR pada baris heading Pasal standalone:
# - kata "Pasal": Pasa1, PasaI, PasaL, PasaT, Pasa.l, Pasd, "Pasal,"
# - spasi/angka OCR: "Pasal 1 1" -> 11, "Pasal 2 I" -> 21, "Pasal L5" -> 15,
#   "Pasal T2" -> 72, "Pasal 1O1" -> 101, "Pasal TT" -> 77
_HEAD_WORD = r"(?:[Pp]asa[1lILT]|[Pp]asa\.l|[Pp]asd)"
_OCR_HEADING_RE = re.compile(
    rf'^([ \t]*["\u201c]?){_HEAD_WORD}(?:[ \t,]+|[ \t]*(?=\d))'
    rf'([0-9lLIOT ]{{1,6}}[A-Za-z]?)[ \t]*([.\u201d"]?)[ \t]*$',
    re.MULTILINE,
)


def _fix_ocr_heading(m: re.Match) -> str:
    prefix, raw_num, suffix = m.group(1), m.group(2), m.group(3)
    compact = re.sub(r"[ \t]+", "", raw_num)
    # Pertahankan Romawi murni (I, II, III, IV, V, X, L, C...) kecuali "Ll"
    if re.fullmatch(r"[IVXLC]+", compact):
        return f"{prefix}Pasal {compact}{suffix}"
    # Konversi spasi/huruf OCR angka pada token yang memang nomor angka/campuran
    # (hindari mengubah sufiks pasal sah seperti 4A, 16B, 11A, 32C).
    chars = list(raw_num.strip())
    out = []
    for idx, ch in enumerate(chars):
        if ch in " \t":
            continue
        if ch in ("l", "L"):
            out.append("1")
        elif ch == "O":
            out.append("0")
        elif ch == "T":
            out.append("7")
        elif ch == "I":
            # "I" di awal ("I 14") atau setelah spasi ("2 I") -> "1"; sufiks akhir "4I" tetap "I"
            prev_sp = idx > 0 and chars[idx - 1] in " \t"
            next_dig = any(c.isdigit() for c in chars[idx + 1:])
            out.append("1" if (prev_sp or next_dig or idx == 0) else "I")
        else:
            out.append(ch)
    fixed = "".join(out)
    # Validasi: harus angka (opsional 1 huruf kapital sufiks di akhir)
    if re.fullmatch(r"\d+[A-Z]?", fixed):
        return f"{prefix}Pasal {fixed}{suffix}"
    return m.group(0)


def normalize_headings(text: str) -> str:
    text = BULLET_H.sub(r"\1", text)
    text = ROM_LL_H.sub(r"\1Pasal I", text)
    text = _OCR_HEADING_RE.sub(_fix_ocr_heading, text)
    text = OCR_H.sub(r"\1Pasal ", text)
    text = DOT_H.sub(r"\1\2", text)
    for _ in range(3):
        new = JOIN_NUM.sub(r"Pasal \1", text)
        new = JOIN_ROM.sub(r"Pasal \1", new)
        if new == text:
            break
        text = new
    return text


def cut_penjelasan(text: str) -> Tuple[str, str]:
    """Pisahkan batang tubuh dari bagian PENJELASAN (rujukan pasal di penjelasan
    tidak boleh dihitung sebagai pasal)."""
    m = PENJELASAN_RE.search(text)
    if m:
        return text[:m.start()], text[m.start():]
    return text, ""


def _base_int(m) -> Optional[int]:
    base = re.sub(r"[A-Z]+$", "", m.group(1))
    return int(base) if base.isdigit() else None


def filter_seq_numeric(matches) -> list:
    """Terima heading bernomor yang membentuk urutan 1,2,3,...
    (sisipan bersufiks seperti '4A' diizinkan setelah nomor induknya).
    Heading lain dianggap rujukan antar-pasal (false positive PDF).
    Jika 1-2 nomor terlewati/tertukar kolom namun nomor yang ditunggu
    tidak muncul lagi di 5 kandidat berikutnya, lanjutkan dari nomor berikutnya."""
    ms = list(matches)
    accepted, expected = [], 1
    for i, m in enumerate(ms):
        num = m.group(1)
        base = re.sub(r"[A-Z]+$", "", num)
        if not base.isdigit():
            continue
        n = int(base)
        if num != base:  # sufiks huruf (mis. 4A): terima bila menyusul induknya
            if n == expected - 1:
                accepted.append(m)
            continue
        if n == expected:
            accepted.append(m)
            expected += 1
        elif n < expected:
            continue
        elif n <= expected + 2 and not any(
                _base_int(ms[j]) == expected for j in range(i + 1, min(i + 6, len(ms)))):
            accepted.append(m)
            expected = n + 1
    return accepted


def filter_seq_roman(matches) -> list:
    accepted, expected = [], 1
    for m in matches:
        n = roman_to_int(m.group(1))
        if n == expected:
            accepted.append(m)
            expected += 1
        elif n < expected:
            continue
    return accepted


def split_pasal(text: str) -> Tuple[str, list, str]:
    """Split kasar (Fase 1) — parser penuh di src/parse_structure.py.
    Return (preamble, articles, structure)."""
    text = normalize_headings(text)
    roman = list(ROM_H2.finditer(text))
    numeric = list(NUM_H.finditer(text))
    first_one = next((i for i, m in enumerate(numeric) if m.group(1) == "1"), None)
    if roman and (first_one is None or roman[0].start() < numeric[first_one].start()):
        roman = filter_seq_roman(roman)
        if roman:
            pre = text[:roman[0].start()].strip()
            arts = []
            for i, m in enumerate(roman):
                end = roman[i + 1].start() if i + 1 < len(roman) else len(text)
                arts.append({"pasal": m.group(1), "full_text": text[m.end():end].strip()})
            return pre, arts, "AMENDING_ROMAN"
        return text.strip(), [], "UNKNOWN"
    if first_one is None:
        return text.strip(), [], "UNKNOWN"
    numeric = filter_seq_numeric(numeric[first_one:])
    if not numeric:
        return text.strip(), [], "UNKNOWN"
    pre = text[:numeric[0].start()].strip()
    arts = []
    for i, m in enumerate(numeric):
        end = numeric[i + 1].start() if i + 1 < len(numeric) else len(text)
        arts.append({"pasal": m.group(1), "full_text": text[m.end():end].strip()})
    return pre, arts, "NUMERIC"
