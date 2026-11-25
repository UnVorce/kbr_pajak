# -*- coding: utf-8 -*-
"""S4 — parser struktur peraturan (Bab/Bagian/Paragraf/Pasal/Ayat/Huruf/Angka).

Fokus Fase 2: menghasilkan provisions ber-locator kanonik per dokumen.
- Dokumen biasa (Pasal 1, 2, 4A, ...) dan dokumen pengubah (Pasal I, II, ...).
- Bagian PENJELASAN dipisah; penjelasan pasal demi pasal dipetakan ke locator PJ.
- Hasil ditulis ke JSON dokumen di key "provisions" (tanpa menghapus "articles").
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from src.textutil import (  # noqa: E402
    ROM_H2,
    cut_penjelasan,
    filter_seq_numeric,
    filter_seq_roman,
    normalize_headings,
)

AYAT_RE = re.compile(r"(?im)^[ \t]*\((\d+[a-z]?)\)\s*(.*)$")
HURUF_RE = re.compile(r"(?im)^[ \t]*([a-z])\.\s+(.*)$")
ANGKA_RE = re.compile(r"(?im)^[ \t]*(\d+)\.\s+(.*)$")
# Heading romawi dokumen pengubah — kadang menyatu dengan kalimat sebelumnya
# ("... dikembalikan. Pasal II 1. Terhadap ...") atau judul inline.
ROM_H_ANY = re.compile(r'(?i)(?:^|[.]\s+|\n)Pasal\s+([IVXLC]+)\b')

ITEM_RE = re.compile(r"(?im)^[ \t]*(\d+)\.\s+(.*)$")

# Heading bagian (boleh judul inline di baris yang sama). [ \t] agar TIDAK
# melompati baris (PDF sering memisah "Bagian\nTahun").
SECTION_RE = re.compile(
    r'(?im)^[ \t]*(BAB[ \t]+[IVXLC]+|Bagian[ \t]+[A-Za-z]+|Paragraf[ \t]+\d+)'
    r'(?:[ \t]+(.*))?[ \t]*$'
)
# Heading pasal bernomor: satu baris penuh (kutip pembuka/penutup diizinkan).
PASAL_UNIT_RE = re.compile(r'(?im)^\s*["\u201c]?Pasal\s+(\d+[A-Z]?)\s*[.\u201d"]?\s*$')

LEVEL_FOR = {"bab": "BAB", "bagian": "BAGIAN", "paragraf": "PARAGRAF"}


def _blocks(text: str, pattern) -> list:
    ms = list(pattern.finditer(text))
    out = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        first = m.group(2) if m.re.groups >= 2 and m.group(2) is not None else ""
        out.append((m.group(1), (first + text[m.end():end]).strip()))
    return out


def _role_pasal(nomor: str, text: str, amending: bool) -> str:
    t = text.lower()
    if amending:
        if "mulai berlaku" in t or "diundangkan" in t:
            return "EFFECTIVITY"
        if "peralihan" in t:
            return "TRANSITIONAL"
        return "AMENDING_INSTRUCTION"
    if nomor == "1" and "yang dimaksud" in t:
        return "DEFINITION"
    return "SUBSTANTIVE"


def _emit_pasal(doc_id, part_code, nomor, text, amending, out):
    loc = f"{doc_id}#{part_code}/{nomor}"
    role = _role_pasal(nomor, text, amending)
    out.append({"level": "PASAL", "nomor": str(nomor), "locator": loc,
                "parent": None, "heading": "", "text": text, "role": role,
                "ord": len(out)})
    return loc


def _parse_ayat_content(content, doc_id, pasal_loc, out):
    # Normalisasi OCR ayat pembuka '(21 ' -> '(2) '
    content = re.sub(r"(?m)^([ \t]*)\((\d+[a-z]?)[1lI](?=[ \t])", r"\1(\2)", content)
    ayat = _blocks(content, AYAT_RE)
    if not ayat:
        return
    for num, text in ayat:
        huruf = _blocks(text, HURUF_RE)
        loc = f"{pasal_loc}/{num}"
        out.append({"level": "AYAT", "nomor": num, "locator": loc,
                    "parent": pasal_loc, "heading": "", "text": text, "role": None,
                    "ord": len(out)})
        for h, htext in huruf:
            angkas = _blocks(htext, ANGKA_RE)
            hloc = f"{loc}/{h}"
            out.append({"level": "HURUF", "nomor": h, "locator": hloc,
                        "parent": loc, "heading": "", "text": htext, "role": None,
                        "ord": len(out)})
            for n, ntext in angkas:
                out.append({"level": "ANGKA", "nomor": n,
                            "locator": f"{hloc}/{n}", "parent": hloc, "heading": "",
                            "text": ntext, "role": None, "ord": len(out)})


def parse_pasals_to_subprovisions(doc_id: str, pasals: List[dict]) -> List[dict]:
    """Pecah daftar pasal konsolidasi [{'nomor', 'text'}] ke sub-provisions ber-locator."""
    out: List[dict] = []
    for p in pasals:
        nomor = str(p.get("nomor", ""))
        text = p.get("text") or ""
        loc = _emit_pasal(doc_id, "BT", nomor, text, False, out)
        _parse_ayat_content(text, doc_id, loc, out)
    return out


def _parse_amending(doc_id, part_code, batang, out):
    romans = filter_seq_roman(list(ROM_H_ANY.finditer(batang)))
    for i, m in enumerate(romans):
        end = romans[i + 1].start() if i + 1 < len(romans) else len(batang)
        text = batang[m.end():end].strip()
        nomor = m.group(1)
        loc = _emit_pasal(doc_id, part_code, nomor, text, True, out)
        for n, itext in _blocks(text, ITEM_RE):
            out.append({"level": "ANGKA", "nomor": n, "locator": f"{loc}/{n}",
                        "parent": loc, "heading": "", "text": itext,
                        "role": "AMENDING_INSTRUCTION", "ord": len(out)})


def _parse_numeric(doc_id, part_code, batang, out):
    sections = list(SECTION_RE.finditer(batang))
    # filter urutan: rujukan antar-pasal (mis. "Pasal 20" di blok Mengingat) dibuang
    pasals = filter_seq_numeric(list(PASAL_UNIT_RE.finditer(batang)))
    units = sorted([("S", m) for m in sections] + [("P", m) for m in pasals],
                   key=lambda t: t[1].start())
    cur_section = None
    for idx, (typ, m) in enumerate(units):
        end = units[idx + 1][1].start() if idx + 1 < len(units) else len(batang)
        text = batang[m.end():end].strip()
        if typ == "P":
            nomor = m.group(1)
            loc = _emit_pasal(doc_id, part_code, nomor, text, False, out)
            if cur_section:
                out[-1]["section"] = cur_section
            _parse_ayat_content(text, doc_id, loc, out)
        else:
            g = m.group(1).split(None, 1)
            level = LEVEL_FOR[g[0].lower()]
            nomor = g[1] if len(g) > 1 else ""
            inline_title = (m.group(2) or "").strip()
            if not inline_title:
                inline_title = next((l.strip() for l in text.splitlines() if l.strip()), "")
            cur_section = f"{level} {nomor}" + (f" — {inline_title}" if inline_title else "")
            out.append({"level": level, "nomor": nomor, "locator": None,
                        "parent": None, "heading": inline_title[:200], "text": "",
                        "role": None, "ord": len(out), "section_only": True})


def parse_document(doc_id: str, text: str) -> dict:
    """Return {preamble, penjelasan, penjelasan_articles, provisions, structure}."""
    text = normalize_headings(text)
    batang, penjelasan = cut_penjelasan(text)
    first_pasal_pos = batang.find("Pasal")
    pre = batang[:first_pasal_pos].strip() if first_pasal_pos >= 0 else batang.strip()

    out: List[dict] = []
    roman = list(ROM_H_ANY.finditer(batang))
    romans_ok = filter_seq_roman(roman)
    first_one = next((m for m in PASAL_UNIT_RE.finditer(batang)
                      if m.group(1) == "1"), None)
    if len(romans_ok) >= 2 and (first_one is None
                                or romans_ok[0].start() < first_one.start()):
        _parse_amending(doc_id, "BT", batang, out)
        structure = "AMENDING_ROMAN"
    elif first_one is not None:
        _parse_numeric(doc_id, "BT", batang, out)
        structure = "NUMERIC"
    elif len(romans_ok) == 1:
        # OCR: "Pasal I" tunggal kemungkinan "Pasal 1" (mis. PP-2022-55).
        batang2 = re.sub(r"(?im)^(\s*)Pasal\s+I\s*$", r"\1Pasal 1", batang, count=1)
        _parse_numeric(doc_id, "BT", batang2, out)
        structure = "NUMERIC"
    else:
        structure = "UNKNOWN"

    penjelasan_articles = []
    if penjelasan:
        for nomor, ptext in _blocks(penjelasan,
                                    re.compile(r'(?im)^\s*Pasal\s+(\d+[A-Z]?)\s*$')):
            penjelasan_articles.append({
                "pasal": nomor, "text": ptext[:5000],
                "locator": f"{doc_id}#PJ/{nomor}",
            })
    return {"preamble": pre, "penjelasan": penjelasan,
            "penjelasan_articles": penjelasan_articles,
            "provisions": out, "structure": structure}
