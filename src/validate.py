# -*- coding: utf-8 -*-
"""S8 — Validator deterministik & antrean review untuk hasil LLM Colab (T2_RULE).

Pemeriksaan berurutan (spec 8.8):
1. Struktur & skema rule_type + tipe field.
2. Sumber: document_id & source_locator ada di chunk; source_quote substring persis
   dari teks chunk (setelah normalisasi spasi & baris baru).
3. Logika / anti-halusinasi: seluruh angka/tarif pada rate_or_value, condition,
   deadline, dan consequence harus muncul di teks chunk.
4. Deduplikasi & routing ke REVIEW_REQUIRED (tarif/angka, fasilitas, pengecualian,
   batas waktu, sanksi, confidence < 0.8, dan sampel acak 10%).
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

VALID_RULE_TYPES = {
    "eligibility", "obligation", "right", "prohibition", "exception",
    "sanction", "deadline", "rate", "definition", "procedure", "other",
}
LIST_FIELDS = (
    "condition", "obligation", "right", "prohibition",
    "exception", "rate_or_value", "cross_references",
)
HIGH_RISK_TYPES = {"rate", "sanction", "deadline", "eligibility", "exception"}

# Dokumen dengan PDF sumber terkonfirmasi korup/salah unduh dari BPK (lihat ISSUES.md #A7)
QUARANTINED_DOC_IDS = {"PER-DJP-2015-17"}

_MONTHS_ID = {
    1: "januari", 2: "februari", 3: "maret", 4: "april",
    5: "mei", 6: "juni", 7: "juli", 8: "agustus",
    9: "september", 10: "oktober", 11: "november", 12: "desember",
}


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


_WATERMARK_RE = re.compile(
    r"(?i)(?:"
    r"www\.(?:jdih\.kemenkeu|djpp\.depkumham|peraturan)\.go\.id(?:\s+\d{4},\s*No\.?\s*\d+(?:\s+\d+)?)?|"
    r"jdih\.kemenkeu\.go\.id(?:\s*-\s*\d+\s*-)?|"
    r"(?:MENTERI\s+KEUANGAN|PRES\s*ID[EO]N)\s+REP[UI]J?BLIK\s+INDONESIA\s*[-_]\s*\d+\s*[-_]?|"
    r"\bSK\s+No\.?\s*\d+\s*[A-Z]\b"
    r")"
)


def _normalize_ocr(s: str) -> str:
    """Normalisasi ligatur, artefak OCR, nomor halaman PDF & watermark."""
    t = unicodedata.normalize("NFKC", s or "").replace("\u00ad", "")
    t = _WATERMARK_RE.sub(" ", t)
    # Nomor halaman PDF yang terselip di tengah kalimat: "- 34 -", "K - 3 -"
    t = re.sub(r"(?<!\w)(?:[A-Z]\s+)?-\s*\d+\s*-(?!\w)", " ", t)
    # Spasi nyasar setelah tanda hubung di dalam kata majemuk ("Undang- Undang")
    t = re.sub(r"(?<=[A-Za-z])-\s+(?=[A-Za-z])", "-", t)
    t = re.sub(r"(?i)o\s*/\s*o|(?<=\d)[0oO]\s*/\s*[oO]|(?<=\d)oh\b", "%", t)
    t = re.sub(r"(?<=Rp)\s*[lI](?=\d)", "1", t)
    t = re.sub(r"(?<=Rp)S(?=\d{2}\.|\.\d{3})", "5", t)
    t = re.sub(r"(?<![A-Za-z])[lI](?=[Oo]+(?:%|[.,]\d))", "1", t)
    t = re.sub(r"(?<![A-Za-z])[lI](?=,\d)", "1", t)
    t = re.sub(r"(?<=\d)[Oo]+(?=[.,\d%)\s]|$)", lambda m: "0" * len(m.group(0)), t)
    t = re.sub(r"(?<=\d[.,])[Oo]+(?=\d)", lambda m: "0" * len(m.group(0)), t)
    t = re.sub(r"\bO(?=[.,]\d)", "0", t)
    t = re.sub(r"(?<=\d)[lI](?=[\s).,;:%]|$)", "1", t)
    t = re.sub(r"\([lI]\)", "(1)", t)
    t = re.sub(r"\((\d+)[1lI](?=[\s\)])", r"(\1)", t)
    t = re.sub(r"\((\d+)[1lI](?=[A-Za-z])", r"(\1) ", t)
    return t


def _token_coverage(quote_norm: str, chunk_norm: str) -> float:
    """Persentase token kutipan yang muncul di chunk (untuk kasus tabel)."""
    q = quote_norm.lower().split()
    if not q:
        return 0.0
    c = set(chunk_norm.lower().split())
    return sum(1 for t in q if t in c) / len(q)


def _replace_verified_iso_dates(txt: str, chunk_norm_low: str) -> str:
    """Jika tanggal ISO (YYYY-MM-DD) cocok dengan 'D Bulan YYYY' di teks, normalkan ke 'D YYYY'."""
    def _sub(m: re.Match) -> str:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        mname = _MONTHS_ID.get(mo)
        if mname and re.search(rf"(?<!\d){d}\s+{mname}\s+{y}(?!\d)", chunk_norm_low):
            return f"{d} {y}"
        return m.group(0)
    return re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b", _sub, txt)


def _digits_tokens(obj, chunk_norm_low: str = "") -> List[Tuple[str, str]]:
    """Ambil token angka bermakna dari nilai terstruktur."""
    txt = json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj
    # Terapkan normalisasi OCR yang sama pada field terstruktur (mis. '600/o' -> '60%', 'RpS00' -> 'Rp500')
    txt = _normalize_ocr(txt)
    # Hilangkan glitch ganda ',00,00' -> ',00' sebelum tokenisasi angka
    txt = re.sub(r",00,00(?!\d)", ",00", txt)
    if chunk_norm_low:
        txt = _replace_verified_iso_dates(txt, chunk_norm_low)
    toks = []
    for m in re.finditer(r"\d+(?:[.,]\d+)*", txt):
        raw = m.group(0)
        compact = raw.replace(".", "").replace(",", "")
        if compact:
            toks.append((raw, compact))
    return toks


def _number_in_text(
    raw: str,
    compact: str,
    chunk_norm: str,
    chunk_no_sep: str,
    chunk_no_sep_int: str = "",
) -> bool:
    if re.search(rf"(?<!\d){re.escape(raw)}(?!\d)", chunk_norm):
        return True
    # Normalisasi pemisah ribuan/desimal antar-digit (60.000.000 == 60000000),
    # tetap menjaga batas angka agar "25" tidak cocok dengan "2025".
    if re.search(rf"(?<!\d){re.escape(compact)}(?!\d)", chunk_no_sep):
        return True
    # Nominal Rupiah tanpa sen ',00' (Rp54.000.000,00 -> 54000000)
    if chunk_no_sep_int and re.search(rf"(?<!\d){re.escape(compact)}(?!\d)", chunk_no_sep_int):
        return True
    # Format US vs Indonesia (1,500.00 <-> 1.500,00 ; 7.5 <-> 7,5)
    if "." in raw or "," in raw:
        swapped = raw.translate(str.maketrans(".,", ",."))
        if re.search(rf"(?<!\d){re.escape(swapped)}(?!\d)", chunk_norm):
            return True
    # Kata 'nol' di teks untuk angka '0'
    if raw == "0" and re.search(r"\bnol\b", chunk_norm, re.I):
        return True
    return False


def validate_rule(rule: dict, chunk: dict) -> Tuple[str, List[str], List[str]]:
    """Kembalikan (status, errors, review_reasons).
    status: 'VALIDATED' | 'REVIEW_REQUIRED' | 'REJECTED'
    """
    errors: List[str] = []
    review_reasons: List[str] = []

    if not isinstance(rule, dict):
        return "REJECTED", ["rule bukan objek JSON"], []

    rtype = rule.get("rule_type")
    if rtype not in VALID_RULE_TYPES:
        errors.append(f"rule_type tidak valid: {rtype}")

    for lf in LIST_FIELDS:
        val = rule.get(lf)
        if val is not None and not isinstance(val, list):
            errors.append(f"{lf} harus list")

    quote = rule.get("source_quote")
    chunk_text = chunk.get("text") or ""
    ctx = chunk.get("context") or {}
    chunk_norm = _norm_ws(_normalize_ocr(chunk_text))
    quote_norm = _norm_ws(_normalize_ocr(quote or ""))
    if not quote_norm:
        errors.append("source_quote kosong")
    elif quote_norm not in chunk_norm:
        # Beda spasi/tanda baca OCR murni ('W ajib' vs 'Wajib'): karakter identik -> review
        q_ns = re.sub(r"[\s.,;:]+", "", quote_norm.lower())
        c_ns = re.sub(r"[\s.,;:]+", "", chunk_norm.lower())
        if q_ns and q_ns in c_ns:
            review_reasons.append("quote_whitespace_ocr_diff")
        # Tabel PDF sering teracak urutannya; jangan langsung tolak,
        # tetapi jangan auto-validasi. Wajib review manusia.
        elif ctx.get("is_table") and _token_coverage(quote_norm, chunk_norm) >= 0.9:
            review_reasons.append("table_layout_review")
        else:
            errors.append("source_quote bukan substring persis dari teks chunk")

    conf = rule.get("confidence", 0.0)
    try:
        conf_f = float(conf)
    except (TypeError, ValueError):
        errors.append(f"confidence bukan angka: {conf}")
        conf_f = 0.0

    # Cek angka tidak berhalusinasi (hanya hapus titik/koma di antara digit)
    chunk_no_sep = re.sub(r"(?<=\d)[.,](?=\d)", "", chunk_norm)
    chunk_no_sep_int = re.sub(r"(?<=\d)[.,](?=\d)", "", re.sub(r",00(?!\d)", "", chunk_norm))
    chunk_norm_low = chunk_norm.lower()
    for fld in ("rate_or_value", "condition", "deadline", "consequence"):
        val = rule.get(fld)
        if not val:
            continue
        for raw, compact in _digits_tokens(val, chunk_norm_low):
            if not _number_in_text(raw, compact, chunk_norm, chunk_no_sep, chunk_no_sep_int):
                errors.append(f"angka '{raw}' pada {fld} tidak ditemukan di teks chunk")

    if errors:
        return "REJECTED", errors, []

    # Cek kategori wajib review manusia (spec 8.8)
    if rtype in HIGH_RISK_TYPES:
        review_reasons.append(f"rule_type:{rtype}")
    if rule.get("rate_or_value"):
        review_reasons.append("has_rate_or_value")
    if rule.get("exception"):
        review_reasons.append("has_exception")
    if rule.get("deadline"):
        review_reasons.append("has_deadline")
    if ctx.get("mk_review_refs"):
        review_reasons.append("mk_constitutional_review")
    if ctx.get("sema_tun_refs"):
        review_reasons.append("sema_tun_guidance")
    if conf_f < 0.8:
        review_reasons.append("low_confidence")
    # Sampel acak deterministik >= 10%
    h = int(hashlib.sha1(f"{chunk['chunk_id']}|{quote_norm}".encode()).hexdigest()[:4], 16)
    if not review_reasons and (h % 10 == 0):
        review_reasons.append("random_10pct_sample")

    status = "REVIEW_REQUIRED" if review_reasons else "VALIDATED"
    return status, [], review_reasons


def validate_staging_results(
    results: List[dict],
    chunks_by_id: Dict[str, dict],
) -> Tuple[List[dict], List[dict], dict]:
    """Validasi sekumpulan hasil staging LLM -> (legal_rules, review_queue, report)."""
    legal_rules: List[dict] = []
    review_queue: List[dict] = []
    seen_keys: set[tuple] = set()
    counts: Counter = Counter()
    reject_reasons: Counter = Counter()
    quarantined_seen: set[str] = set()

    for res in results:
        cid = res.get("chunk_id")
        chunk = chunks_by_id.get(cid)
        if not chunk:
            counts["MISSING_CHUNK"] += 1
            continue

        if chunk.get("document_id") in QUARANTINED_DOC_IDS:
            counts["QUARANTINED_SOURCE"] += 1
            quarantined_seen.add(chunk["document_id"])
            continue

        if res.get("parse_error"):
            counts["PARSE_ERROR"] += 1
            review_queue.append({
                "chunk_id": cid,
                "document_id": chunk["document_id"],
                "source_locator": chunk["source_locator"],
                "reason": ["llm_parse_error"],
                "error": res.get("parse_error"),
                "raw_output": (res.get("raw_output") or "")[:600],
                "human_decision": "PENDING",
            })
            continue

        parsed = res.get("parsed_output") or {}
        if parsed.get("found") is False:
            counts["NOT_FOUND_IN_CHUNK"] += 1
            continue

        rules = parsed.get("rules")
        if not isinstance(rules, list):
            counts["NO_RULES_LIST"] += 1
            continue

        method = {
            "model_id": res.get("model_id"),
            "prompt_version": res.get("prompt_version"),
        }
        for idx, r in enumerate(rules, 1):
            status, errs, rev_reasons = validate_rule(r, chunk)
            if status == "REJECTED":
                counts["REJECTED"] += 1
                for e in errs:
                    reject_reasons[e.split(":")[0]] += 1
                review_queue.append({
                    "chunk_id": cid,
                    "document_id": chunk["document_id"],
                    "source_locator": chunk["source_locator"],
                    "reason": ["validator_rejected"] + errs,
                    "candidate_rule": r,
                    "chunk_text": chunk["text"][:1000],
                    "human_decision": "PENDING",
                })
                continue

            q_norm = _norm_ws(r.get("source_quote") or "")
            dedup_key = (chunk["document_id"], chunk["source_locator"], r.get("rule_type"), q_norm)
            if dedup_key in seen_keys:
                counts["DUPLICATE_SKIPPED"] += 1
                continue
            seen_keys.add(dedup_key)

            rid_hash = hashlib.sha1(f"{cid}|{idx}|{q_norm}".encode()).hexdigest()[:10]
            rule_id = f"R-{chunk['document_id']}-{rid_hash}"
            ctx = chunk.get("context") or {}
            rec = {
                "rule_id": rule_id,
                "domain": chunk.get("domain"),
                "document_id": chunk["document_id"],
                "source_locator": chunk["source_locator"],
                "chunk_id": cid,
                "rule_type": r.get("rule_type"),
                "subject": r.get("subject"),
                "condition": r.get("condition") or [],
                "obligation": r.get("obligation") or [],
                "right": r.get("right") or [],
                "prohibition": r.get("prohibition") or [],
                "exception": r.get("exception") or [],
                "consequence": r.get("consequence"),
                "deadline": r.get("deadline"),
                "rate_or_value": r.get("rate_or_value") or [],
                "cross_references": r.get("cross_references") or [],
                "source_quote": r.get("source_quote"),
                "effective_period_hint": r.get("effective_period_hint"),
                "confidence": r.get("confidence"),
                "mk_review_refs": ctx.get("mk_review_refs") or [],
                "sema_tun_refs": ctx.get("sema_tun_refs") or [],
                "validation_status": status,
                "review_reasons": rev_reasons,
                "extraction_method": method,
            }
            legal_rules.append(rec)
            counts[status] += 1
            if status == "REVIEW_REQUIRED":
                review_queue.append({
                    "rule_id": rule_id,
                    "chunk_id": cid,
                    "domain": chunk.get("domain"),
                    "document_id": chunk["document_id"],
                    "source_locator": chunk["source_locator"],
                    "reason": rev_reasons,
                    "source_quote": rec["source_quote"],
                    "mk_review_refs": rec["mk_review_refs"],
                    "sema_tun_refs": rec["sema_tun_refs"],
                    "candidate_rule": rec,
                    "human_decision": "PENDING",
                })

    report = {
        "total_results_processed": len(results),
        "total_legal_rules": len(legal_rules),
        "total_review_queue": len(review_queue),
        "counts": dict(sorted(counts.items())),
        "reject_reasons": dict(sorted(reject_reasons.items())),
        "quarantined_docs": sorted(quarantined_seen),
    }
    return legal_rules, review_queue, report
