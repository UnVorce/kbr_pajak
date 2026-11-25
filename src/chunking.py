# -*- coding: utf-8 -*-
"""Tahap 4B — Chunker T2_RULE berbasis struktur hukum (src/chunking.py).

Prinsip (spec 8.7):
- Hanya pasal SUBSTANTIVE atau DEFINITION dari scope_manifest.jsonl.
- Tidak pernah memotong di tengah ayat.
- Pasal <= MAX_PASAL_CHARS tetap 1 chunk utuh; pasal panjang dipecah per AYAT
  (atau per HURUF bila 1 ayat > MAX_AYAT_CHARS), membawa konteks induk & locator.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

MAX_PASAL_CHARS = 2200
MAX_AYAT_CHARS = 3200
MAX_LEAF_CHARS = 3500

_CUT_TAIL_RE = re.compile(
    r"(?im)^\s*(?:Agar\s+setiap\s+orang\s+mengetahuinya\b|"
    r"Ditetapkan\s+di\s+[A-Z]|"
    r"LAMPIRAN\s+(?:[IVXLC]+\b|HURUF\b|PERATURAN\b|KEPUTUSAN\b))"
)


_WATERMARK_RE = re.compile(
    r"(?i)(?:"
    r"www\.(?:jdih\.kemenkeu|djpp\.depkumham|peraturan)\.go\.id(?:\s+\d{4},\s*No\.?\s*\d+(?:\s+\d+)?)?|"
    r"(?:MENTERI\s+KEUANGAN|PRESID[EO]N)\s+REP[UI]J?BLIK\s+INDONESIA\s*[-_]\s*\d+\s*[-_]?|"
    r"\bSK\s+No\.?\s*\d+\s*[A-Z]\b"
    r")"
)


def normalize_ocr_text(text: str) -> str:
    """Normalisasi artefak OCR & watermark PDF umum pada teks chunk (tanpa mengubah makna)."""
    t = text or ""
    # Hapus watermark header/footer halaman PDF yang terselip di tengah kalimat
    t = _WATERMARK_RE.sub(" ", t)
    # '3Oo/o' -> '30%', 'O,5%' -> '0,5%'
    t = re.sub(r"(?i)o\s*/\s*o", "%", t)
    # 'Rpl00...' -> 'Rp100...', 'RpS.000...' -> 'Rp5.000...'
    t = re.sub(r"(?<=Rp)\s*[lI](?=\d)", "1", t)
    t = re.sub(r"(?<=Rp)S(?=\.\d{3})", "5", t)
    # 'lO%' / 'IO%' / 'lO,5%' -> '1O%' -> '10%'
    t = re.sub(r"(?<![A-Za-z])[lI](?=[Oo]+(?:%|[.,]\d))", "1", t)
    # '0O' / '1O' / '3O%' / '.OO0' -> '00' / '10' / '30%' / '.000'
    t = re.sub(r"(?<=\d)[Oo]+(?=[.,\d%)\s]|$)", lambda m: "0" * len(m.group(0)), t)
    t = re.sub(r"(?<=\d[.,])[Oo]+(?=\d)", lambda m: "0" * len(m.group(0)), t)
    # 'O,5' di awal kata -> '0,5'
    t = re.sub(r"\bO(?=[.,]\d)", "0", t)
    # 'l' / 'I' sebagai angka 1 pada konteks angka
    t = re.sub(r"(?<=\d)[lI](?=[\s).,;:%]|$)", "1", t)
    # nomor ayat rusak: '(l)' -> '(1)', '(21' -> '(2)', '(21untuk' -> '(2) untuk'
    t = re.sub(r"\([lI]\)", "(1)", t)
    t = re.sub(r"\((\d+)[1lI](?=[\s\)])", r"(\1)", t)
    t = re.sub(r"\((\d+)[1lI](?=[A-Za-z])", r"(\1) ", t)
    # satukan baris agar source_quote mudah dicocokkan
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_table_like(text: str) -> bool:
    """Deteksi tabel tarif/kolom nyata (menghindari false-positive wrapping PDF biasa)."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if len(lines) < 6:
        return False
    col_lines = sum(1 for ln in lines if re.search(r"\S\s{3,}\S|\|", ln))
    if col_lines >= 4:
        return True
    short_val = sum(
        1 for ln in lines
        if len(ln) < 30 and re.search(r"(?:\d+\s*(?:%|o/o)|^Rp\s*[\d.,Oo]+)", ln, re.I)
    )
    if short_val >= 4:
        return True
    has_tbl_hdr = any(
        re.search(r"(?i)^(?:Lapisan\s+Penghasilan|Tarif\s+Pajak|Kelompok\s+Harta|No\.\s+Uraian)\b", ln)
        for ln in lines
    )
    pct_or_rp = sum(
        1 for ln in lines
        if re.search(r"(?:\d+\s*(?:%|o/o)|Rp\s*[\d.,Oo]+)", ln, re.I)
    )
    return has_tbl_hdr and pct_or_rp >= 3


def _trim_tail(text: str) -> str:
    if len(text or "") <= 20:
        return (text or "").strip()
    m = _CUT_TAIL_RE.search(text, 20)
    return text[:m.start()].strip() if m else text.strip()


def _split_long_leaf(locator: str, text: str, sub_label: Optional[str]) -> List[tuple[str, str, Optional[str]]]:
    """Pecah chunk daun yang masih > MAX_LEAF_CHARS di batas baris/paragraf."""
    if len(text) <= MAX_LEAF_CHARS:
        return [(locator, text, sub_label)]
    lines = text.splitlines()
    parts: List[str] = []
    cur: List[str] = []
    cur_len = 0
    for ln in lines:
        add = len(ln) + 1
        if cur and cur_len + add > MAX_LEAF_CHARS - 200:
            parts.append("\n".join(cur).strip())
            cur, cur_len = [ln], len(ln)
        else:
            cur.append(ln)
            cur_len += add
    if cur:
        parts.append("\n".join(cur).strip())
    if len(parts) <= 1:
        # fallback potong di spasi jika teks tanpa newline
        raw = text
        parts = []
        while len(raw) > MAX_LEAF_CHARS:
            cut = raw.rfind(" ", 0, MAX_LEAF_CHARS - 100)
            if cut <= 500:
                cut = MAX_LEAF_CHARS - 100
            parts.append(raw[:cut].strip())
            raw = raw[cut:].strip()
        if raw:
            parts.append(raw)
    out = []
    tot = len(parts)
    for idx, p in enumerate(parts, 1):
        lbl = f"{sub_label} (bag. {idx}/{tot})" if sub_label else f"bag. {idx}/{tot}"
        out.append((f"{locator}#p{idx}", p, lbl))
    return out


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def make_chunk_id(document_id: str, locator: str, text: str) -> str:
    th = _text_hash(text)
    raw = f"{document_id}|{locator}|{th}|T2_RULE"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _pasal_intro(pasal_text: str) -> str:
    """Ambil kalimat pengantar pasal sebelum '(1)' (maks 600 char)."""
    m = re.search(r"(?m)^\s*\(1\)\s+", pasal_text or "")
    if m and 5 < m.start() <= 600:
        return pasal_text[:m.start()].strip()
    return ""


def _ayat_intro(ayat_text: str) -> str:
    m = re.search(r"(?m)^\s*a\.\s+", ayat_text or "")
    if m and 5 < m.start() <= 600:
        return ayat_text[:m.start()].strip()
    return ""


def chunk_pasal(
    *,
    document_id: str,
    domain: str,
    judul: str,
    source_kind: str,
    pasal_row: dict,
    children_by_parent: Dict[str, List[dict]],
    review_refs: Optional[dict] = None,
) -> List[dict]:
    """Pecah 1 pasal menjadi 1 atau beberapa chunk T2_RULE yang utuh."""
    p_loc = pasal_row["locator"]
    p_no = str(pasal_row.get("nomor", ""))
    p_text = _trim_tail(pasal_row.get("text") or "")
    if not p_text:
        return []

    refs = review_refs or {}

    def _emit_many(locator: str, text: str, sub_label: Optional[str] = None) -> List[dict]:
        res = []
        for sub_loc, sub_txt, lbl in _split_long_leaf(locator, text.strip(), sub_label):
            raw_txt = sub_txt
            table = is_table_like(raw_txt)
            norm_txt = normalize_ocr_text(raw_txt)
            ctx = {
                "judul": judul[:220],
                "pasal_induk": f"Pasal {p_no}",
                "sub_bagian": lbl,
                "role": pasal_row.get("role"),
                "is_table": table,
            }
            if refs.get("mk"):
                ctx["mk_review_refs"] = list(refs["mk"])
            if refs.get("sema"):
                ctx["sema_tun_refs"] = list(refs["sema"])
            res.append({
                "chunk_id": make_chunk_id(document_id, sub_loc, norm_txt),
                "task_type": "T2_RULE",
                "domain": domain,
                "document_id": document_id,
                "source_locator": sub_loc,
                "source_kind": source_kind,
                "context": ctx,
                "text": norm_txt,
                "text_raw": raw_txt,
                "text_hash": _text_hash(norm_txt),
                "char_len": len(norm_txt),
            })
        return res

    ayats = [c for c in children_by_parent.get(p_loc, []) if c.get("level") == "AYAT"]
    if len(p_text) <= MAX_PASAL_CHARS or not ayats:
        return _emit_many(p_loc, p_text)

    intro = _pasal_intro(p_text)
    out: List[dict] = []
    buf_locs: List[str] = []
    buf_texts: List[str] = []

    def flush_buf() -> None:
        if not buf_texts:
            return
        body = "\n".join(buf_texts)
        full = f"{intro}\n{body}".strip() if intro else body
        loc = buf_locs[0] if len(buf_locs) == 1 else f"{buf_locs[0]}..{buf_locs[-1].rsplit('/', 1)[-1]}"
        out.extend(_emit_many(loc, full, sub_label=f"ayat {', '.join(l.rsplit('/', 1)[-1] for l in buf_locs)}"))
        buf_locs.clear()
        buf_texts.clear()

    for ay in ayats:
        ay_loc = ay["locator"]
        ay_no = str(ay.get("nomor", ""))
        ay_raw = _trim_tail(ay.get("text") or "")
        if not ay_raw:
            continue
        ay_txt = f"({ay_no}) {ay_raw}".strip()
        hurufs = [h for h in children_by_parent.get(ay_loc, []) if h.get("level") == "HURUF"]

        if len(ay_txt) > MAX_AYAT_CHARS and hurufs:
            flush_buf()
            ay_intro = _ayat_intro(ay_raw)
            h_buf_locs: List[str] = []
            h_buf_txts: List[str] = []
            for hr in hurufs:
                h_no = str(hr.get("nomor", ""))
                h_raw = _trim_tail(hr.get("text") or "")
                if not h_raw:
                    continue
                h_txt = f"{h_no}. {h_raw}".strip()
                if h_buf_txts and sum(len(x) for x in h_buf_txts) + len(h_txt) > MAX_PASAL_CHARS:
                    hb = "\n".join(h_buf_txts)
                    pref = "\n".join(x for x in (intro, f"({ay_no}) {ay_intro}".strip() if ay_intro else f"({ay_no})") if x)
                    h_loc = h_buf_locs[0] if len(h_buf_locs) == 1 else f"{h_buf_locs[0]}..{h_buf_locs[-1].rsplit('/', 1)[-1]}"
                    out.extend(_emit_many(h_loc, f"{pref}\n{hb}".strip(), sub_label=f"ayat ({ay_no}) huruf"))
                    h_buf_locs, h_buf_txts = [], []
                h_buf_locs.append(hr["locator"])
                h_buf_txts.append(h_txt)
            if h_buf_txts:
                hb = "\n".join(h_buf_txts)
                pref = "\n".join(x for x in (intro, f"({ay_no}) {ay_intro}".strip() if ay_intro else f"({ay_no})") if x)
                h_loc = h_buf_locs[0] if len(h_buf_locs) == 1 else f"{h_buf_locs[0]}..{h_buf_locs[-1].rsplit('/', 1)[-1]}"
                out.extend(_emit_many(h_loc, f"{pref}\n{hb}".strip(), sub_label=f"ayat ({ay_no}) huruf"))
            continue

        cur_len = sum(len(x) for x in buf_texts) + (len(intro) if intro else 0)
        if buf_texts and cur_len + len(ay_txt) > MAX_PASAL_CHARS:
            flush_buf()
        buf_locs.append(ay_loc)
        buf_texts.append(ay_txt)

    flush_buf()
    return out


def build_all_chunks(
    scope_rows: List[dict],
    docs_dir: Path,
    cons_dir: Path,
    perda_dir: Path,
) -> List[dict]:
    """Bangun seluruh chunk T2_RULE dari daftar baris scope_manifest."""
    by_doc: Dict[str, List[dict]] = defaultdict(list)
    for r in scope_rows:
        if r.get("extract_t2"):
            by_doc[r["document_id"]].append(r)

    all_chunks: List[dict] = []
    for did, rows in sorted(by_doc.items()):
        pool = rows[0].get("pool", "national")
        base_dir = perda_dir if pool == "pilot_perda" else docs_dir
        d = json.loads((base_dir / f"{did}.json").read_text(encoding="utf-8"))
        judul = d.get("judul") or did

        src_kind = rows[0].get("source_kind", "document")
        if src_kind == "consolidated" and (cons_dir / f"{did}.json").exists():
            c = json.loads((cons_dir / f"{did}.json").read_text(encoding="utf-8"))
            provs = c.get("sub_provisions", [])
        else:
            provs = d.get("provisions", [])
            if not any(p.get("level") == "PASAL" for p in provs) and d.get("articles"):
                provs = [{
                    "level": "PASAL",
                    "nomor": str(a.get("nomor", "")),
                    "locator": a.get("locator") or f"{did}#BT/{a.get('nomor', '')}",
                    "parent": None,
                    "text": a.get("text") or "",
                    "role": a.get("role") or "SUBSTANTIVE",
                } for a in d["articles"]]

        children_by_parent: Dict[str, List[dict]] = defaultdict(list)
        pasal_by_loc: Dict[str, dict] = {}
        for pr in provs:
            par = pr.get("parent")
            if par:
                children_by_parent[par].append(pr)
            if pr.get("level") == "PASAL":
                pasal_by_loc[pr["locator"]] = pr

        seen_locs: set[str] = set()
        for r in rows:
            loc = r["locator"]
            if loc in seen_locs:
                continue
            seen_locs.add(loc)
            pr = pasal_by_loc.get(loc)
            if not pr:
                continue
            pr_with_role = {**pr, "role": r["role"]}
            all_chunks.extend(chunk_pasal(
                document_id=did,
                domain=r["domain"],
                judul=judul,
                source_kind=src_kind,
                pasal_row=pr_with_role,
                children_by_parent=children_by_parent,
                review_refs={
                    "mk": r.get("mk_review_refs") or [],
                    "sema": r.get("sema_tun_refs") or [],
                },
            ))
    return all_chunks
