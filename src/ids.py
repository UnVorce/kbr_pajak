# -*- coding: utf-8 -*-
"""Normalisasi document_id dan locator kanonik (KBR_Extraction_Spec.md Bagian 5.1).

document_id : {JENIS}-{TAHUN}-{NOMOR}
  contoh    : UU-1983-7, PP-2022-55, PMK-2024-81, PER-DJP-2013-14, PUTUSAN-MK-2022-14

locator     : <document_id>#<part>/<pasal>[/<ayat>[/<huruf>[/<angka>]]]
  contoh    : UU-1983-7#BT/17/1/a      (BT = batang tubuh, PJ = penjelasan)

Ketentuan (spec 5.1):
- Fungsi normalisasi harus IDEMPOTEN dan DIUJI dengan kasus nyata.
- Simpan `nomor_raw` (persis seperti di sumber) dan `nomor_norm` (angka/sufiks,
  mis. "4A").
- Jenis dokumen yang dikenali mengikuti tabel 5.1 spec.
- Nomor sisipan seperti "4A" dipertahankan (terutama untuk locator pasal).

Batas yang diketahui (dicatat, bukan disembunyikan):
- Heuristik tahun: "Tahun XXXX" bila ada, selain itu angka 4-digit terakhir.
  Untuk teks yang memuat lebih dari satu peraturan, berikan substring kutipan
  yang sudah difokuskan (S6/gaps.py bertanggung jawab memotongnya).
- Jenis di luar tabel 5.1 dikembalikan None (bukan ditebak). Pemanggil wajib
  menandai NEEDS_REVIEW. Menambah jenis baru butuh persetujuan manusia.
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Jenis dokumen (tabel 5.1 spec)
# ---------------------------------------------------------------------------

JENIS_KNOWN: Tuple[str, ...] = (
    "UU",
    "PERPU",
    "PP",
    "PERPRES",
    "PMK",
    "PER-DJP",
    "SE-DJP",
    "KMK",
    "PUTUSAN-MK",
)

# Pola deteksi jenis. URUTAN PENTING: nama panjang sebelum singkatan
# (mis. "Peraturan Pemerintah Pengganti Undang-Undang" sebelum "Peraturan Pemerintah").
_JENIS_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("PERPU", r"(?i)peraturan\s+pemerintah\s+pengganti\s+undang-undang|\bperppu\b|\bperpu\b"),
    ("PUTUSAN-MK", r"(?i)putusan\s+mahkamah\s+konstitusi|\d{1,4}\s*/\s*puu"),
    ("PER-DJP", r"(?i)peraturan\s+direktur\s+jenderal\s+pajak|peraturan\s+dirjen\s+pajak"
                r"|per[\s\-/]?\d{1,4}[a-z]?[\s\-/]*pj"),
    ("SE-DJP", r"(?i)surat\s+edaran\s+(?:direktur\s+jenderal\s+pajak|dirjen\s+pajak)"
               r"|se[\s\-/]?\d{1,4}[a-z]?[\s\-/]*pj"),
    ("PMK", r"(?i)peraturan\s+menteri\s+keuangan|\bpmk\b"),
    ("KMK", r"(?i)keputusan\s+menteri\s+keuangan|\bkmk\b"),
    ("PERPRES", r"(?i)peraturan\s+presiden|\bperpres\b"),
    ("PP", r"(?i)peraturan\s+pemerintah\b|\bpp\b"),
    ("UU", r"(?i)undang-undang|\buu\b"),
)

_CANONICAL_RE = re.compile(r"^([A-Za-z][A-Za-z-]*)-(\d{4})-(\d{1,4}[A-Za-z]?)$")
_TAHUN_RE = re.compile(r"(?i)\btahun\s+(\d{4})\b")
_4DIGIT_RE = re.compile(r"(?<!\d)\d{4}(?!\d)")
_NOMOR_RE = re.compile(r"(?i)\bnomor\s+([^\s,;]+)")
_NO_RE = re.compile(r"(?i)\bno\.?\s+([^\s,;]+)")
_NORM_RE = re.compile(r"\d{1,4}[A-Za-z]?")
_UUD_RE = re.compile(r"(?i)undang-undang\s+dasar")
# Bentuk kode pendek: PMK-81/PMK.03/2024, PER-14/PJ/2013, SE-29/PJ/2022, KMK-...
_SHORTCODE_RE = re.compile(r"(?i)\b(?:pmk|kmk|se|per)[\s\-/]*\d{1,4}[a-z]?(?:[\s\-/][a-z0-9.]+)*")
# Putusan MK: 14/PUU-XX/2022
_MK_RE = re.compile(r"(?i)\b\d{1,4}\s*/\s*puu[^\s,;]*")


# ---------------------------------------------------------------------------
# document_id
# ---------------------------------------------------------------------------

def _detect_jenis(text: str) -> Optional[str]:
    """Deteksi jenis dengan aturan POSISI TERAWAL + span terpanjang.

    Penting untuk judul seperti "UU No. 6 Tahun 2023 tentang Penetapan
    Peraturan Pemerintah Pengganti Undang-Undang Nomor 2 Tahun 2022" —
    jenis dokumennya UU (posisi 0), bukan PERPU yang disebut di dalam judul.
    """
    best = None  # ((start, -end), jenis)
    for jenis, pattern in _JENIS_PATTERNS:
        for m in re.finditer(pattern, text):
            key = (m.start(), -m.end())
            if best is None or key < best[0]:
                best = (key, jenis)
    return best[1] if best else None


def _extract_tahun(s: str) -> Optional[int]:
    m = _TAHUN_RE.search(s)
    if m:
        return int(m.group(1))
    hits = _4DIGIT_RE.findall(s)
    if hits:
        return int(hits[-1])
    return None


def _norm(raw: str) -> Optional[str]:
    """Angka/sufiks dari token nomor mentah, mis. '81/PMK.03/2024' -> '81', '4A' -> '4A'."""
    m = _NORM_RE.search(raw or "")
    return m.group(0) if m else None


def _extract_nomor(s: str, jenis: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (nomor_raw, nomor_norm).

    "Nomor X" dan "No. X" disatukan dan dipilih POSISI TERAWAL — judul dapat
    menyebut peraturan lain setelah nomor dokumennya sendiri (mis.
    "UU No. 6 Tahun 2023 tentang Penetapan PERPU Nomor 2 Tahun 2022").
    """
    candidates = []
    m = _NOMOR_RE.search(s)
    if m:
        candidates.append((m.start(), m.group(1)))
    m = _NO_RE.search(s)
    if m:
        candidates.append((m.start(), m.group(1)))
    if candidates:
        _, raw = min(candidates, key=lambda t: t[0])
        raw = raw.rstrip(".,;")
        return raw, _norm(raw)
    if jenis == "PUTUSAN-MK":
        m = _MK_RE.search(s)
    else:
        m = _SHORTCODE_RE.search(s)
    if m:
        raw = m.group(0)
        return raw, _norm(raw)
    return None, None


def _result(jenis: str, tahun: int, nomor_raw: str, nomor_norm: str) -> Dict[str, object]:
    return {
        "jenis": jenis,
        "tahun": tahun,
        "nomor_raw": nomor_raw,
        "nomor_norm": nomor_norm,
        "document_id": f"{jenis}-{tahun}-{nomor_norm}",
    }


def parse_document_ref(text: str) -> Optional[Dict[str, object]]:
    """Parse rujukan peraturan menjadi komponen kanonik.

    Return dict {jenis, tahun, nomor_raw, nomor_norm, document_id} atau None
    bila tidak dikenali (pemanggil wajib menandai NEEDS_REVIEW, jangan menebak).
    """
    s = (text or "").strip()
    if not s:
        return None
    # UUD 1945 bukan jenis dokumen yang dikelola registry ini (tabel 5.1).
    if _UUD_RE.search(s):
        return None
    # Bentuk kanonik -> lolos begitu saja (idempoten).
    m = _CANONICAL_RE.match(s)
    if m:
        jenis = m.group(1).upper()
        if jenis not in JENIS_KNOWN:
            return None
        tahun = int(m.group(2))
        nomor = m.group(3)
        return _result(jenis, tahun, nomor, nomor)
    jenis = _detect_jenis(s)
    if jenis is None:
        return None
    tahun = _extract_tahun(s)
    nomor_raw, nomor_norm = _extract_nomor(s, jenis)
    if tahun is None or nomor_norm is None:
        return None
    return _result(jenis, tahun, nomor_raw, nomor_norm)


def normalize_document_id(text: str) -> Optional[str]:
    """Return document_id kanonik atau None. Idempoten."""
    d = parse_document_ref(text)
    return d["document_id"] if d else None


def is_canonical_document_id(text: str) -> bool:
    s = (text or "").strip()
    m = _CANONICAL_RE.match(s)
    return bool(m and m.group(1).upper() in JENIS_KNOWN)


# ---------------------------------------------------------------------------
# locator
# ---------------------------------------------------------------------------

PART_TO_CODE = {"BATANG_TUBUH": "BT", "PENJELASAN": "PJ"}
CODE_TO_PART = {"BT": "BATANG_TUBUH", "PJ": "PENJELASAN"}

_LOCATOR_RE = re.compile(
    r"^(?P<document_id>[^#\s]+)#(?P<part_code>BT|PJ)(?:/(?P<pasal>[^/\s]+))?"
    r"(?:/(?P<ayat>[^/\s]+))?(?:/(?P<huruf>[^/\s]+))?(?:/(?P<angka>[^/\s]+))?$"
)


def part_to_code(part: str) -> str:
    """Terima 'BATANG_TUBUH'/'PENJELASAN' atau 'BT'/'PJ'; return kode 2 huruf."""
    if part in PART_TO_CODE:
        return PART_TO_CODE[part]
    if part in CODE_TO_PART:
        return part
    raise ValueError(
        f"bagian tidak dikenal: {part!r} (diharapkan BATANG_TUBUH/BT atau PENJELASAN/PJ)"
    )


def part_from_code(code: str) -> Optional[str]:
    """'BT' -> 'BATANG_TUBUH', 'PJ' -> 'PENJELASAN', lainnya None."""
    return CODE_TO_PART.get(code)


def build_locator(
    document_id: str,
    part: str = "BT",
    pasal=None,
    ayat=None,
    huruf=None,
    angka=None,
) -> str:
    """Susun locator kanonik. `pasal` wajib; sisipan seperti '4A' dipertahankan."""
    if pasal is None:
        raise ValueError("pasal wajib diisi untuk locator")
    code = part_to_code(part)
    segs = [f"{document_id}#{code}", str(pasal)]
    for x in (ayat, huruf, angka):
        if x is not None:
            segs.append(str(x))
    return "/".join(segs)


def parse_locator(locator: str) -> Optional[Dict[str, Optional[str]]]:
    """Urai locator kanonik. Return dict atau None bila bentuk tidak valid."""
    m = _LOCATOR_RE.match((locator or "").strip())
    if not m:
        return None
    g = m.groupdict()
    if g["pasal"] is None:
        return None
    return {
        "document_id": g["document_id"],
        "part_code": g["part_code"],
        "part": CODE_TO_PART[g["part_code"]],
        "pasal": g["pasal"],
        "ayat": g["ayat"],
        "huruf": g["huruf"],
        "angka": g["angka"],
    }
