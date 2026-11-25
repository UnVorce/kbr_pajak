# -*- coding: utf-8 -*-
"""Step B — Parser & RDF Exporter untuk Tabel TER PPh 21 (PP 58/2023) & KBLI SKOS (PER-17/PJ/2015 + PP 78/2019).

Menghasilkan:
- ontology/kbr_ter_pph21.ttl  (127 bracket TER A/B/C/Harian tervalidasi silang dengan terbilang & kontinuitas)
- ontology/kbr_kbli.ttl       (W3C SKOS Concept graph kode KLU/KBLI 5-digit + NPPN 3 wilayah + Tax Allowance PP 78/2019)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rdflib import Graph, Literal, Namespace, RDF, RDFS, XSD

BASE_IRI = "http://www.semanticweb.org/ontology/kbr_pajak#"
SKOS_IRI = "http://www.w3.org/2004/02/skos/core#"

# Pasal 1 ayat (2) PER-17/PJ/2015: 10 Ibu Kota Provinsi
SEPULUH_IBUKOTA_PROVINSI = {
    "MEDAN", "PALEMBANG", "JAKARTA", "DKI JAKARTA", "WILAYAH_DKI_JAKARTA",
    "BANDUNG", "KOTA BANDUNG", "SEMARANG", "KOTA SEMARANG", "WILAYAH_KOTA_SEMARANG",
    "SURABAYA", "KOTA SURABAYA", "WILAYAH_KOTA_SURABAYA",
    "DENPASAR", "KOTA DENPASAR", "MANADO", "MAKASSAR", "PONTIANAK",
}

IBUKOTA_PROVINSI_LAIN = {
    "BANDA ACEH", "PADANG", "PEKANBARU", "TANJUNGPINANG", "JAMBI", "BENGKULU",
    "BANDAR LAMPUNG", "PANGKALPINANG", "SERANG", "YOGYAKARTA", "KOTA YOGYAKARTA",
    "MATARAM", "KUPANG", "PALANGKA RAYA", "BANJARMASIN", "SAMARINDA", "TANJUNG SELOR",
    "GORONTALO", "PALU", "MAMUJU", "KENDARI", "TERNATE", "SOFIFI",
    "AMBON", "MANOKWARI", "JAYAPURA",
}


def resolve_nppn_wilayah_kelompok(pemda_or_city: Optional[str]) -> str:
    """Petakan kota/daerah ke 3 kelompok wilayah PER-17/PJ/2015 Pasal 1 secara akurat.

    Penting: Wilayah_Jawa_Barat & Wilayah_Prov_Bali level provinsi TIDAK otomatis
    10_IbuKota_Provinsi (hanya Kota Bandung & Kota Denpasar yang termasuk).
    """
    if not pemda_or_city:
        return "Daerah_Lain"
    norm = pemda_or_city.strip().upper().replace("-", " ")
    if norm in ("10_IBUKOTA_PROVINSI", "IBUKOTA_PROVINSI_LAIN", "DAERAH_LAIN"):
        return {
            "10_IBUKOTA_PROVINSI": "10_IbuKota_Provinsi",
            "IBUKOTA_PROVINSI_LAIN": "IbuKota_Provinsi_Lain",
            "DAERAH_LAIN": "Daerah_Lain",
        }[norm]
    clean = norm.replace("WILAYAH_", "").replace("PROVINSI ", "").replace("KOTA_", "").replace("KABUPATEN ", "").replace("_", " ").strip()
    if norm in SEPULUH_IBUKOTA_PROVINSI or clean in SEPULUH_IBUKOTA_PROVINSI:
        return "10_IbuKota_Provinsi"
    if clean in IBUKOTA_PROVINSI_LAIN:
        return "IbuKota_Provinsi_Lain"
    return "Daerah_Lain"


@dataclass
class TerBracket:
    kategori: str
    order: int
    min_exclusive: Optional[float]  # None for first bracket (<= upper)
    max_inclusive: Optional[float]  # None for last bracket (> lower)
    rate_percent: float
    raw_range: str


def _parse_id_terbilang(text: str) -> Optional[float]:
    """Konversi terbilang Indonesia ('enam juta dua ratus ribu rupiah' / 'satu koma dua lima persen') ke float."""
    w = text.lower()
    for bad, good in (
        ("iima", "lima"),
        ("be las", "belas"), ("tqiuh", "tujuh"), ("tqjuh", "tujuh"), ("tuiuh", "tujuh"),
        ("empa.t", "empat"), ("ernpat", "empat"),
        ("sembiian", "sembilan"), ("sembitan", "sembilan"), ("sembilan".lower(), "sembilan"),
        ("persenl", "persen"), ("perseni", "persen"),
        ("seribij", "seribu"), ("jtrta", "juta"), ("jutq", "juta"),
        ("delapen", "delapan"), ("sepu1uh", "sepuluh"), ("sebeias", "sebelas"),
        ("duabelas", "dua belas"), ("tigabelas", "tiga belas"), ("empatbelas", "empat belas"),
        ("limabelas", "lima belas"), ("enambelas", "enam belas"), ("tujuhbelas", "tujuh belas"),
        ("delapanbelas", "delapan belas"), ("sembilanbelas", "sembilan belas"),
        ("duapuluh", "dua puluh"), ("tigapuluh", "tiga puluh"),
    ):
        w = w.replace(bad, good)
    w = re.sub(r"[^a-z\s]", " ", w)
    w = re.sub(r"\s+", " ", w).strip()
    words = w.split()
    if not words:
        return None
    units = {
        "nol": 0, "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
        "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9, "sepuluh": 10, "sebelas": 11,
    }

    def parse_int(toks: List[str]) -> Optional[int]:
        if not toks:
            return None
        total = 0
        group = 0
        cur = 0
        matched = False
        for t in toks:
            if t in units:
                cur = units[t]
                matched = True
            elif t == "belas":
                group += 10 + cur
                cur = 0
                matched = True
            elif t == "puluh":
                group += (cur if cur else 1) * 10
                cur = 0
                matched = True
            elif t == "ratus":
                group += (cur if cur else 1) * 100
                cur = 0
                matched = True
            elif t == "seratus":
                group += 100
                matched = True
            elif t == "seribu":
                total += 1000
                group = 0
                cur = 0
                matched = True
            elif t == "ribu":
                val = group + cur
                total += (val if val else 1) * 1000
                group = 0
                cur = 0
                matched = True
            elif t == "juta":
                val = group + cur
                total += (val if val else 1) * 1_000_000
                group = 0
                cur = 0
                matched = True
            elif t in ("miliar", "milyar"):
                val = group + cur
                total += (val if val else 1) * 1_000_000_000
                group = 0
                cur = 0
                matched = True
        return (total + group + cur) if matched else None

    if "persen" in words:
        words = [x for x in words if x != "persen"]
        if "koma" in words:
            idx = words.index("koma")
            whole = parse_int(words[:idx])
            if whole is None:
                whole = 0
            frac = "".join(str(units[t]) for t in words[idx + 1:] if t in units)
            return float(f"{whole}.{frac}") if frac else float(whole)
        val = parse_int(words)
        return float(val) if val is not None else None
    words = [x for x in words if x != "rupiah"]
    val = parse_int(words)
    return float(val) if val is not None else None


def _norm_ocr_digits(s: str, *, is_currency: bool = False) -> Optional[float]:
    s = s.strip()
    for ch, rep in (("O", "0"), ("o", "0"), ("I", "1"), ("l", "1"), ("L", "1"), ("t", "1"), ("r", "1"), ("f", "1"), ("!", "1"), ("T", "7"), ("a", "4"), ("S", "5"), ("Z", "2")):
        s = s.replace(ch, rep)
    s = re.sub(r"\s+", "", s)
    if is_currency:
        s = re.sub(r"[.,]\d{2}$", "", s)
        s = s.replace(".", "").replace(",", "")
    else:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _clean_pp58_section(sec: str) -> str:
    lines = []
    for ln in sec.splitlines():
        st = ln.strip()
        if not st or re.match(r"^SK\s*No", st, re.I) or re.match(r"^[-_]\s*\d+\s*[-_]$", st) or st.endswith(". . ."):
            continue
        if any(x in st for x in (
            "PRESIDEN", "PRESIBEN", "REPUBLIK", "EPUBLIK", "TNDONEISIA", "INDONESIA",
            "Penghasilan Bruto", "Tarif Pajak", "Salinan sesuai", "KEMENTERIAN",
            "Perundang-undangan", "inistrasi Hukum", "JOKO WIDODO", "Plh", "Lestari",
            "BUK I", "INOO", "trrI", "Erfd", "hIiI", "kr{trt", "tJ{*{",
        )):
            continue
        if st in ("ttd", "-3", "\\i"):
            continue
        lines.append(st)
    return re.sub(r"\s+", " ", " ".join(lines))


def parse_pp58_ter(txt_path: Path) -> List[TerBracket]:
    """Parse seluruh tabel TER (Kategori A, B, C, Harian) dari PP-2023-58.txt dan validasi kontinuitas."""
    txt = txt_path.read_text(encoding="utf-8", errors="ignore")
    lamp = txt[txt.find("LAMPIRAN"):]
    pA = lamp.upper().find("KATEGORIA")
    pB = lamp.upper().find("KATEGORI B")
    pC = lamp.upper().find("KATEGORI C")
    pD = lamp.upper().find("TARIF EFEKTIF HARIAN")
    sections = [
        ("TER_A", lamp[pA:pB]),
        ("TER_B", lamp[pB:pC]),
        ("TER_C", lamp[pC:pD]),
        ("TER_Harian", lamp[pD:]),
    ]

    amt_pat = r"Rp\s*[0-9OoIlLtrf!TaSZ.,\s]+,[0-9Oo]{2}\s*[\({f][^)}]+[)}I]"
    rate_pat = re.compile(
        r"([0-9OoIlLtrSZ]+(?:[.,][0-9OoIlLtrSZ]+)?)\s*(?:%|0/o|o/o|yo|0/0|o/0|o/\")\s*[\({f]\s*([^)}]*?persen)[)}\]I]?",
        re.I,
    )
    range_pat = re.compile(
        rf"(di\s*atas\s+{amt_pat}\s+sampai\s+dengan\s+{amt_pat}"
        rf"|sampai\s+dengan\s+{amt_pat}"
        rf"|di\s*atas\s+{amt_pat}(?!\s+sampai))",
        re.I,
    )

    def _extract_amt(part: str) -> float:
        m = re.search(r"Rp\s*([0-9OoIlLtrf!TaSZ.,\s]+,[0-9Oo]{2})\s*[\({f]([^)}]+)[)}I]", part)
        if not m:
            raise ValueError(f"Gagal parse nominal TER: {part!r}")
        d_val = _norm_ocr_digits(m.group(1), is_currency=True)
        w_val = _parse_id_terbilang(m.group(2))
        if d_val is not None and d_val > 0:
            return d_val
        if w_val is not None and w_val > 0:
            return w_val
        raise ValueError(f"Nominal TER tidak terbaca: {part!r}")

    all_brackets: List[TerBracket] = []
    for cat, sec in sections:
        flat = _clean_pp58_section(sec)
        ranges = range_pat.findall(flat)
        raw_rates = rate_pat.findall(flat)
        if len(ranges) != len(raw_rates) or not ranges:
            raise ValueError(f"Ketidakcocokan jumlah bracket vs tarif pada {cat}: ranges={len(ranges)} rates={len(raw_rates)}")

        # Pilih nilai persen tervalidasi silang (digit vs terbilang) yang konsisten monoton
        rates: List[float] = []
        prev_r = -1.0
        for r_num, r_words in raw_rates:
            d_val = _norm_ocr_digits(r_num)
            w_val = _parse_id_terbilang(r_words)
            if d_val is not None and w_val is not None and abs(d_val - w_val) < 1e-6:
                val = w_val
            elif w_val is not None and prev_r <= w_val <= 34.0 and (d_val is None or d_val < prev_r or d_val > 34.0 or (w_val - prev_r) < (d_val - prev_r)):
                val = w_val
            elif d_val is not None and prev_r <= d_val <= 34.0:
                val = d_val
            else:
                val = w_val if w_val is not None else d_val
            if val is None:
                raise ValueError(f"Persen TER tidak terbaca ({cat}): {r_num!r} / {r_words!r}")
            rates.append(val)
            prev_r = val

        cat_brackets: List[TerBracket] = []
        for idx, (rng_txt, pct) in enumerate(zip(ranges, rates), start=1):
            parts = re.split(r"\s+sampai\s+dengan\s+", rng_txt, flags=re.I)
            if len(parts) == 2:
                mn = _extract_amt(parts[0])
                mx = _extract_amt(parts[1])
            elif rng_txt.lower().startswith("sampai"):
                mn = None
                mx = _extract_amt(rng_txt)
            else:
                mn = _extract_amt(rng_txt)
                mx = None
            cat_brackets.append(TerBracket(cat, idx, mn, mx, float(pct), rng_txt))

        # Validasi kontinuitas ketat: prev.max_inclusive == cur.min_exclusive & tarif monoton naik
        for i in range(1, len(cat_brackets)):
            prev, cur = cat_brackets[i - 1], cat_brackets[i]
            if prev.max_inclusive != cur.min_exclusive:
                raise ValueError(f"Celah kontinuitas TER {cat} baris {i}: {prev.max_inclusive} != {cur.min_exclusive}")
            if cur.rate_percent < prev.rate_percent:
                raise ValueError(f"Tarif TER {cat} tidak monoton pada baris {i}: {prev.rate_percent} -> {cur.rate_percent}")

        all_brackets.extend(cat_brackets)

    return all_brackets


def export_ter_ttl(brackets: List[TerBracket], out_ttl: Path) -> int:
    g = Graph()
    KBR = Namespace(BASE_IRI)
    g.bind("kbr", KBR)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    for b in brackets:
        uri = KBR[f"TERBracket_{b.kategori}_{b.order:02d}"]
        g.add((uri, RDF.type, KBR.BracketTER_PPh21))
        g.add((uri, KBR.hasKategoriTER, Literal(b.kategori, datatype=XSD.string)))
        g.add((uri, KBR.hasUrutanBracket, Literal(b.order, datatype=XSD.integer)))
        if b.min_exclusive is not None:
            g.add((uri, KBR.hasBatasBawahEksklusif, Literal(b.min_exclusive, datatype=XSD.decimal)))
        if b.max_inclusive is not None:
            g.add((uri, KBR.hasBatasAtasInklusif, Literal(b.max_inclusive, datatype=XSD.decimal)))
        g.add((uri, KBR.hasTarifPersen, Literal(b.rate_percent, datatype=XSD.decimal)))
        g.add((uri, KBR.hasSourceLocator, Literal("PP-2023-58#LM/1", datatype=XSD.string)))
        g.add((uri, KBR.diaturDalam, KBR.Reg_PP_2023_58))

    out_ttl.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(out_ttl), format="turtle")
    return len(brackets)


def parse_per17_lampiran(txt_path: Path) -> Dict[str, dict]:
    """Parse Lampiran I/II/III PER-17/PJ/2015 secara deterministik."""
    txt = txt_path.read_text(encoding="utf-8", errors="ignore")
    HEADER_EXACT = {"NOKLU", "10", "IBUKOTA", "PROVINSI", "LAINNYA", "PENGHASILAN", "Pasal 14", "Tentang"}
    PCT_END_RE = re.compile(r"(100|\d{1,2}(?:[.,]\d+)?|-)\s+(100|\d{1,2}(?:[.,]\d+)?|-)\s+(100|\d{1,2}(?:[.,]\d+)?|-)\s*$")

    lines = [ln.replace("\xad", "").strip() for ln in txt.splitlines()]
    blocks = []
    cur = ""
    in_desc = False
    for ln in lines:
        if not ln or ln.startswith("--- Halaman") or re.match(r"^-\d+-$", ln) or ln.startswith("# Source:"):
            continue
        if ln in HEADER_EXACT or re.match(
            r"^(NOKLU\s|NOKLUURAIAN|PENGHASILAN\s|Pasal 14\s|Lampiran|Peraturan\s|Nomor\s|DAFTAR\s|UNTUK\s|TIDAK ATAU TIDAK|ATAU PENCATATAN|10\s+IBUKOTA|PROVINSI\s+LAINNYA|LAINNYA\s*DAFTAR|Tentang$)",
            ln,
        ):
            continue
        # Hindari menganggap baris sambungan "47721 S.D. 47727..." sebagai baris baru
        if re.match(r"^\d{5,10}(?:\s\d)?\s*[A-Z]", ln) and not re.match(r"^\d{5}\s+S\.?D\.?\b", ln):
            if cur:
                blocks.append(cur)
            cur = ln
            rest0 = re.split(r"(?:NOKLU|Tentang\s|Kelompok\s)", cur)[0].strip()
            in_desc = bool(PCT_END_RE.search(rest0))
        elif ln.startswith("Kelompok ") or ln[0].islower():
            in_desc = True
        elif cur and not in_desc:
            cur += " " + ln
            rest0 = re.split(r"(?:NOKLU|Tentang\s|Kelompok\s)", cur)[0].strip()
            if PCT_END_RE.search(rest0):
                in_desc = True
    if cur:
        blocks.append(cur)

    rows_by_no: Dict[int, dict] = {}
    expected_no = 1
    for blk in blocks:
        m_num = re.match(r"^(\d+(?:\s\d)?)\s*(.+)$", blk)
        if not m_num:
            continue
        num_raw = m_num.group(1).replace(" ", "")
        rest = m_num.group(2)
        no_val = None
        klu = None
        for cand_no in range(expected_no, expected_no + 8):
            pref = str(cand_no)
            if num_raw.startswith(pref):
                rem = num_raw[len(pref):]
                if len(rem) == 5:
                    no_val, klu = cand_no, rem
                    break
                if len(rem) == 4 and int(rem) >= 1111:
                    no_val, klu = cand_no, "0" + rem
                    break
        if no_val is None:
            continue
        rest = re.split(r"(?:NOKLU|Tentang\s|Kelompok\s+(?:ini|mi))", rest)[0].strip()
        rest = re.sub(r"\s+\d{6,10}\s+[A-Z].*$", "", rest).strip()
        rest = re.sub(r"\b(\d{5})(\d{2}(?:[.,]\d+)?)\s+(\d{1,2}(?:[.,]\d+)?)\s+(\d{1,2}(?:[.,]\d+)?)\s*$", r"\1 \2 \3 \4", rest)
        m_pct = PCT_END_RE.search(rest)
        if not m_pct:
            continue
        uraian = rest[:m_pct.start()].strip()
        vals = [None if x == "-" else float(x.replace(",", ".")) for x in m_pct.groups()]
        if no_val not in rows_by_no:
            rows_by_no[no_val] = {
                "no": no_val,
                "klu": klu,
                "uraian": uraian,
                "p_10ibukota": vals[0],
                "p_ibukota_lain": vals[1],
                "p_daerah_lain": vals[2],
            }
            expected_no = no_val + 1

    return {r["klu"]: r for r in rows_by_no.values()}


def _norm_kbli_token_pp78(tok: str) -> Optional[str]:
    if len(tok) != 5:
        return None
    out = []
    for ch in tok:
        if ch.isdigit():
            out.append(ch)
        elif ch in "oO":
            out.append("0")
        elif ch in "iIlLtr":
            out.append("1")
        elif ch in "sS":
            out.append("5")
        elif ch in "zZ":
            out.append("2")
        elif ch in "bB":
            out.append("8")
        elif ch == "g":
            out.append("9")
        else:
            return None
    res = "".join(out)
    if not (res.isdigit() and len(res) == 5) or res == "20171" or res.startswith("00"):
        return None
    return res


def parse_pp78_tax_allowance(txt_path: Path, known_kblis: Dict[str, dict]) -> Dict[str, dict]:
    """Parse kode KBLI Lampiran I (Nasional) & Lampiran II (Daerah Tertentu) dari PP-2019-78.txt."""
    txt = txt_path.read_text(encoding="utf-8", errors="ignore")
    p1 = txt.find("LAMPIRAN I\n")
    p2 = txt.find("LAMPIRAN II\n")
    out: Dict[str, dict] = {}

    def _resolve_against_known(raw_code: str) -> str:
        if raw_code in known_kblis:
            return raw_code
        # Koreksi OCR 1-digit umum (mis. 07122 -> 01122) HANYA jika hanya ada tepat 1 kandidat cocok di known_kblis
        if raw_code[1] == "7":
            cand = raw_code[0] + "1" + raw_code[2:]
            if cand in known_kblis:
                return cand
        return raw_code

    for lamp_name, sec in (("LAMPIRAN_I", txt[p1:p2]), ("LAMPIRAN_II", txt[p2:])):
        lines = sec.splitlines()
        for i, ln in enumerate(lines):
            st = ln.strip()
            if len(st) != 5 or st in ("2017", "20L7"):
                continue
            k = _norm_kbli_token_pp78(st)
            if not k:
                continue
            k = _resolve_against_known(k)
            ctx_window = " ".join(x.strip() for x in lines[i + 1:min(len(lines), i + 25)])
            prov_note = "Nasional (Lampiran I PP 78/2019)"
            except_dki = False
            if lamp_name == "LAMPIRAN_II":
                if "kecuali DKI Jakarta" in ctx_window or "kecuali\nDKI Jakarta" in "\n".join(lines[i:i + 20]):
                    prov_note = "Seluruh provinsi di Indonesia, kecuali DKI Jakarta"
                    except_dki = True
                else:
                    # Ambil daftar provinsi eksplisit bila disebut
                    provs = [p for p in (
                        "Aceh", "Sumatera Utara", "Sumatera Barat", "Riau", "Jambi", "Sumatera Selatan",
                        "Bengkulu", "Lampung", "Kalimantan Tengah", "Kalimantan Selatan",
                        "Kalimantan Timur", "Kalimantan Utara", "Kalimantan Barat",
                        "Sulawesi", "Maluku", "Papua Barat", "Papua", "Nusa Tenggara",
                    ) if p in ctx_window]
                    prov_note = ", ".join(provs) if provs else "Daerah Tertentu (Lampiran II PP 78/2019)"
            out[k] = {
                "klu": k,
                "lampiran": lamp_name,
                "provinsi_syarat": prov_note,
                "kecuali_dki": except_dki,
            }
    return out


def _infer_pekerjaan_from_klu(klu: str, uraian: str) -> Optional[str]:
    """Pemetaan ringan kode KLU spesifik profesi ke individu JenisPekerjaan yang ada di OWL."""
    u = uraian.upper()
    if klu.startswith("8620") or "PRAKTIK DOKTER" in u:
        return "Dokter"
    if klu == "69100" or "ADVOKAT" in u or "PENGACARA" in u:
        return "Pengacara"
    if klu == "69200" or "AKUNTAN" in u:
        return "Akuntan"
    if klu == "71101" or "ARSITEK" in u:
        return "Arsitek"
    if klu.startswith("7020"):
        return "Konsultan"
    if klu == "69102" or "NOTARIS" in u:
        return "Notaris_PPAT"
    if klu == "66210" or "AGEN ASURANSI" in u:
        return "Agen_Asuransi"
    if klu == "73100" or "PERIKLANAN" in u:
        return "Agen_Iklan"
    if klu.startswith("4791"):
        return "Pedagang_ECommerce"
    if klu.startswith("5610"):
        return "Usaha_Kuliner_Warung"
    if klu.startswith("47"):
        return "Pedagang_Ritel_Grosir"
    return None


def parse_perbkpm_industri_pionir(txt_path: Path) -> Dict[str, dict]:
    """Parse Lampiran I PerBKPM 7/2020: rincian KBLI 5-digit Industri Pionir (PMK 130/2020 Pasal 3(3))."""
    txt = txt_path.read_text(encoding="utf-8", errors="ignore")
    p2 = txt.find("LAMPIRAN II")
    sec = txt[:p2] if p2 > 0 else txt
    lines = sec.splitlines()

    # Sektor Industri Pionir A..R
    current_sector = "Industri Pionir (PerBKPM 7/2020)"
    out: Dict[str, dict] = {}
    i = 0
    while i < len(lines):
        st = lines[i].strip()
        # Deteksi header huruf sektor tunggal A..R
        if re.match(r"^[A-R]$", st):
            sec_lines = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if re.match(r"^\d+\.$", nxt) or re.match(r"^[A-R]$", nxt) or re.match(r"^-\s*\d+\s*-$", nxt):
                    break
                if nxt:
                    sec_lines.append(nxt)
                j += 1
            if sec_lines:
                current_sector = f"{st}. " + re.sub(r"\s+", " ", " ".join(sec_lines))[:180]
        # Baris KBLI utama: "170. 17011A" (satu baris) ATAU baris terpisah "1.\n24101A"
        m_same = re.match(r"^\d+\.\s+(\d{5})([A-Z]?)$", st)
        m_sub = re.match(r"^(\d{5})([A-Z]?)$", st)
        prev_nonempty = next((lines[k].strip() for k in range(i - 1, -1, -1) if lines[k].strip()), "")
        if m_same:
            code5, sub_letter = m_same.group(1), m_same.group(2)
        elif m_sub and re.match(r"^\d+\.$", prev_nonempty):
            code5, sub_letter = m_sub.group(1), m_sub.group(2)
        else:
            code5, sub_letter = None, ""

        if code5:
            subcode = f"{code5}{sub_letter}"
            prod_lines = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if re.match(r"^\d+\.(?:\s+\d{5}[A-Z]?)?$", nxt) or re.match(r"^[A-R]$", nxt) or re.match(r"^-\s*\d+\s*-$", nxt):
                    break
                if nxt:
                    prod_lines.append(nxt)
                j += 1
            prod_txt = re.sub(r"\s+", " ", " ".join(prod_lines))[:240]
            rec = out.setdefault(
                code5,
                {
                    "klu": code5,
                    "sektor": current_sector,
                    "subcodes": [],
                    "jenis_produksi": [],
                },
            )
            if subcode not in rec["subcodes"]:
                rec["subcodes"].append(subcode)
            if prod_txt and len(rec["jenis_produksi"]) < 3:
                rec["jenis_produksi"].append(prod_txt)
        i += 1
    return out


def parse_pmk16_padat_karya(ocr_txt_path: Path) -> Dict[str, dict]:
    """Parse Lampiran A PMK-16/PMK.010/2020 (konsolidasi PMK-81/2024 Pasal 423): 45 KBLI Padat Karya."""
    txt = ocr_txt_path.read_text(encoding="utf-8", errors="ignore")
    m_b = re.search(r"LAMPIRAN\s+B", txt, re.I)
    lamp_a = txt[:m_b.start()] if m_b else txt
    lines = lamp_a.splitlines()
    out: Dict[str, dict] = {}
    for i, ln in enumerate(lines):
        # Abaikan rujukan persyaratan "(KBLI 17011)"
        if "(KBLI " in ln or "KBLI 17011" in ln:
            continue
        for m in re.finditer(r"\b(\d{5})\b", ln):
            code = m.group(1)
            if code in ("20171", "17011") or code.startswith("00") or int(code) < 10000:
                continue
            # Ambil konteks uraian & syarat wilayah dari sekitar baris
            ctx = " ".join(x.strip() for x in lines[max(0, i - 1):min(len(lines), i + 7)])
            except_dki = "kecuali DKI" in ctx or "kecuali\nDKI" in ctx
            prov_note = "Seluruh provinsi di Indonesia, kecuali DKI Jakarta" if except_dki else "Seluruh provinsi di Indonesia (PMK 16/2020 & PMK 81/2024 Pasal 423)"
            out[code] = {
                "klu": code,
                "provinsi_syarat": prov_note,
                "kecuali_dki": except_dki,
                "sumber": "PMK-2020-16#LM/A & PMK-2024-81#BT/423",
            }
    return out


def export_kbli_skos_ttl(
    *,
    lamp1: Dict[str, dict],
    lamp2: Dict[str, dict],
    lamp3: Dict[str, dict],
    pp78: Dict[str, dict],
    perbkpm7: Optional[Dict[str, dict]] = None,
    pmk16: Optional[Dict[str, dict]] = None,
    out_ttl: Path,
) -> dict:
    """Bangun graf RDF W3C SKOS `ontology/kbr_kbli.ttl`."""
    perbkpm7 = perbkpm7 or {}
    pmk16 = pmk16 or {}

    g = Graph()
    KBR = Namespace(BASE_IRI)
    SKOS = Namespace(SKOS_IRI)
    g.bind("kbr", KBR)
    g.bind("skos", SKOS)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    scheme = KBR.SkemaKBLI_PajakIndonesia
    g.add((scheme, RDF.type, SKOS.ConceptScheme))
    g.add((scheme, SKOS.prefLabel, Literal("Skema Klasifikasi KBLI/KLU Perpajakan Indonesia (PER-17/PJ/2015, PP 78/2019, PerBKPM 7/2020, PMK 16/2020)", lang="id")))

    all_codes = sorted(set(lamp1) | set(lamp2) | set(lamp3) | set(pp78) | set(perbkpm7) | set(pmk16))
    for code in all_codes:
        r1 = lamp1.get(code)
        r2 = lamp2.get(code)
        r3 = lamp3.get(code)
        r78 = pp78.get(code)
        r_pionir = perbkpm7.get(code)
        r_pk = pmk16.get(code)
        uraian = (r1 or r2 or r3 or {}).get("uraian") or f"Bidang Usaha KBLI {code}"

        c_uri = KBR[f"KBLI_{code}"]
        g.add((c_uri, RDF.type, SKOS.Concept))
        g.add((c_uri, SKOS.inScheme, scheme))
        g.add((c_uri, SKOS.notation, Literal(code, datatype=XSD.string)))
        g.add((c_uri, SKOS.prefLabel, Literal(uraian, lang="id")))

        if r1:
            if r1["p_10ibukota"] is not None:
                g.add((c_uri, KBR.nppn_OP_10IbuKota, Literal(r1["p_10ibukota"], datatype=XSD.decimal)))
                g.add((c_uri, KBR.nppn_OP_IbuKotaLain, Literal(r1["p_ibukota_lain"], datatype=XSD.decimal)))
                g.add((c_uri, KBR.nppn_OP_DaerahLain, Literal(r1["p_daerah_lain"], datatype=XSD.decimal)))
            g.add((c_uri, KBR.didasarkanPadaAturan, KBR.Aturan_R_UU_1983_7_df018b5a7f))
        if r2 and r2["p_10ibukota"] is not None:
            g.add((c_uri, KBR.nppn_Pemeriksaan_OP_10IbuKota, Literal(r2["p_10ibukota"], datatype=XSD.decimal)))
            g.add((c_uri, KBR.nppn_Pemeriksaan_OP_IbuKotaLain, Literal(r2["p_ibukota_lain"], datatype=XSD.decimal)))
            g.add((c_uri, KBR.nppn_Pemeriksaan_OP_DaerahLain, Literal(r2["p_daerah_lain"], datatype=XSD.decimal)))
        if r3 and r3["p_10ibukota"] is not None:
            g.add((c_uri, KBR.nppn_Pemeriksaan_Badan_10IbuKota, Literal(r3["p_10ibukota"], datatype=XSD.decimal)))
            g.add((c_uri, KBR.nppn_Pemeriksaan_Badan_IbuKotaLain, Literal(r3["p_ibukota_lain"], datatype=XSD.decimal)))
            g.add((c_uri, KBR.nppn_Pemeriksaan_Badan_DaerahLain, Literal(r3["p_daerah_lain"], datatype=XSD.decimal)))
        if r78:
            g.add((c_uri, KBR.isTaxAllowanceKBLI, Literal(True, datatype=XSD.boolean)))
            g.add((c_uri, KBR.taxAllowanceLampiran, Literal(r78["lampiran"], datatype=XSD.string)))
            g.add((c_uri, KBR.taxAllowanceProvinsi, Literal(r78["provinsi_syarat"], datatype=XSD.string)))
            g.add((c_uri, KBR.taxAllowanceKecualiDKI, Literal(r78["kecuali_dki"], datatype=XSD.boolean)))
            g.add((c_uri, KBR.didasarkanPadaAturan, KBR.Aturan_R_PP_2019_78_17ae360038))
        if r_pionir:
            g.add((c_uri, KBR.isIndustriPionirKBLI, Literal(True, datatype=XSD.boolean)))
            g.add((c_uri, KBR.industriPionirSektor, Literal(r_pionir["sektor"], datatype=XSD.string)))
            g.add((c_uri, KBR.industriPionirSubkode, Literal(", ".join(r_pionir["subcodes"]), datatype=XSD.string)))
            g.add((c_uri, KBR.didasarkanPadaAturan, KBR.Aturan_R_PMK_2020_130_2794b42cfb))
        if r_pk:
            g.add((c_uri, KBR.isIndustriPadatKaryaKBLI, Literal(True, datatype=XSD.boolean)))
            g.add((c_uri, KBR.padatKaryaProvinsi, Literal(r_pk["provinsi_syarat"], datatype=XSD.string)))
            g.add((c_uri, KBR.padatKaryaKecualiDKI, Literal(r_pk["kecuali_dki"], datatype=XSD.boolean)))
            g.add((c_uri, KBR.didasarkanPadaAturan, KBR.Aturan_R_PMK_2024_81_10955d1fd9))

        job_id = _infer_pekerjaan_from_klu(code, uraian)
        if job_id:
            g.add((c_uri, KBR.terkaitJenisPekerjaan, KBR[job_id]))

    out_ttl.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(out_ttl), format="turtle")
    return {
        "total_kbli_concepts": len(all_codes),
        "lamp1_nppn_op": len(lamp1),
        "lamp2_pemeriksaan_op": len(lamp2),
        "lamp3_pemeriksaan_badan": len(lamp3),
        "pp78_tax_allowance": len(pp78),
        "perbkpm7_industri_pionir": len(perbkpm7),
        "pmk16_padat_karya": len(pmk16),
        "out_ttl": str(out_ttl),
    }


def lookup_ter_rate_sparql(g: Graph, kategori: str, bruto_bulanan_or_harian: float) -> Optional[dict]:
    """Cari tarif efektif PPh 21 dari kbr_ter_pph21.ttl menggunakan SPARQL."""
    q = f"""
    PREFIX kbr: <{BASE_IRI}>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    SELECT ?order ?minB ?maxB ?rate ?loc
    WHERE {{
      ?b a kbr:BracketTER_PPh21 ;
         kbr:hasKategoriTER "{kategori}"^^xsd:string ;
         kbr:hasUrutanBracket ?order ;
         kbr:hasTarifPersen ?rate ;
         kbr:hasSourceLocator ?loc .
      OPTIONAL {{ ?b kbr:hasBatasBawahEksklusif ?minB . }}
      OPTIONAL {{ ?b kbr:hasBatasAtasInklusif ?maxB . }}
      FILTER((!BOUND(?minB) || {float(bruto_bulanan_or_harian)} > xsd:decimal(?minB))
             && (!BOUND(?maxB) || {float(bruto_bulanan_or_harian)} <= xsd:decimal(?maxB)))
    }}
    LIMIT 1
    """
    for r in g.query(q):
        return {
            "kategori": kategori,
            "bracket_order": int(r.order),
            "min_exclusive": float(r.minB) if r.minB is not None else 0.0,
            "max_inclusive": float(r.maxB) if r.maxB is not None else None,
            "tarif_persen": float(r.rate),
            "source_locator": str(r.loc),
        }
    return None


def lookup_kbli_sparql(g: Graph, kode_kbli: str) -> Optional[dict]:
    """Lookup 1 kode KBLI/KLU 5-digit di graf SKOS kbr_kbli.ttl via SPARQL."""
    safe = re.sub(r"[^0-9]", "", kode_kbli.strip())
    if not safe:
        return None
    q = f"""
    PREFIX kbr: <{BASE_IRI}>
    PREFIX skos: <{SKOS_IRI}>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
    SELECT ?c ?label ?p1 ?p2 ?p3 ?pem1 ?pem2 ?pem3 ?bad1 ?bad2 ?bad3 ?isTA ?taLamp ?taProv ?taExDki ?isPionir ?pSektor ?pSub ?isPK ?pkProv ?pkExDki ?job
    WHERE {{
      ?c a skos:Concept ;
         skos:notation "{safe}"^^xsd:string ;
         skos:prefLabel ?label .
      OPTIONAL {{ ?c kbr:nppn_OP_10IbuKota ?p1 . }}
      OPTIONAL {{ ?c kbr:nppn_OP_IbuKotaLain ?p2 . }}
      OPTIONAL {{ ?c kbr:nppn_OP_DaerahLain ?p3 . }}
      OPTIONAL {{ ?c kbr:nppn_Pemeriksaan_OP_10IbuKota ?pem1 . }}
      OPTIONAL {{ ?c kbr:nppn_Pemeriksaan_OP_IbuKotaLain ?pem2 . }}
      OPTIONAL {{ ?c kbr:nppn_Pemeriksaan_OP_DaerahLain ?pem3 . }}
      OPTIONAL {{ ?c kbr:nppn_Pemeriksaan_Badan_10IbuKota ?bad1 . }}
      OPTIONAL {{ ?c kbr:nppn_Pemeriksaan_Badan_IbuKotaLain ?bad2 . }}
      OPTIONAL {{ ?c kbr:nppn_Pemeriksaan_Badan_DaerahLain ?bad3 . }}
      OPTIONAL {{ ?c kbr:isTaxAllowanceKBLI ?isTA . }}
      OPTIONAL {{ ?c kbr:taxAllowanceLampiran ?taLamp . }}
      OPTIONAL {{ ?c kbr:taxAllowanceProvinsi ?taProv . }}
      OPTIONAL {{ ?c kbr:taxAllowanceKecualiDKI ?taExDki . }}
      OPTIONAL {{ ?c kbr:isIndustriPionirKBLI ?isPionir . }}
      OPTIONAL {{ ?c kbr:industriPionirSektor ?pSektor . }}
      OPTIONAL {{ ?c kbr:industriPionirSubkode ?pSub . }}
      OPTIONAL {{ ?c kbr:isIndustriPadatKaryaKBLI ?isPK . }}
      OPTIONAL {{ ?c kbr:padatKaryaProvinsi ?pkProv . }}
      OPTIONAL {{ ?c kbr:padatKaryaKecualiDKI ?pkExDki . }}
      OPTIONAL {{ ?c kbr:terkaitJenisPekerjaan ?job . }}
    }}
    LIMIT 1
    """
    for r in g.query(q):
        return {
            "kode_kbli": safe,
            "uri": str(r.c),
            "uraian": str(r.label),
            "nppn_op": {
                "10_IbuKota_Provinsi": float(r.p1) if r.p1 is not None else None,
                "IbuKota_Provinsi_Lain": float(r.p2) if r.p2 is not None else None,
                "Daerah_Lain": float(r.p3) if r.p3 is not None else None,
            },
            "nppn_pemeriksaan_op": {
                "10_IbuKota_Provinsi": float(r.pem1) if r.pem1 is not None else None,
                "IbuKota_Provinsi_Lain": float(r.pem2) if r.pem2 is not None else None,
                "Daerah_Lain": float(r.pem3) if r.pem3 is not None else None,
            },
            "nppn_pemeriksaan_badan": {
                "10_IbuKota_Provinsi": float(r.bad1) if r.bad1 is not None else None,
                "IbuKota_Provinsi_Lain": float(r.bad2) if r.bad2 is not None else None,
                "Daerah_Lain": float(r.bad3) if r.bad3 is not None else None,
            },
            "tax_allowance": {
                "eligible_kbli": bool(r.isTA) if r.isTA is not None else False,
                "lampiran": str(r.taLamp) if r.taLamp is not None else None,
                "provinsi_syarat": str(r.taProv) if r.taProv is not None else None,
                "kecuali_dki": bool(r.taExDki) if r.taExDki is not None else False,
            },
            "industri_pionir": {
                "eligible_kbli": bool(r.isPionir) if r.isPionir is not None else False,
                "sektor": str(r.pSektor) if r.pSektor is not None else None,
                "subkode": str(r.pSub) if r.pSub is not None else None,
            },
            "industri_padat_karya": {
                "eligible_kbli": bool(r.isPK) if r.isPK is not None else False,
                "provinsi_syarat": str(r.pkProv) if r.pkProv is not None else None,
                "kecuali_dki": bool(r.pkExDki) if r.pkExDki is not None else False,
            },
            "terkait_jenis_pekerjaan": str(r.job).split("#")[-1] if r.job is not None else None,
        }
    return None


def search_kbli_sparql(g: Graph, query: str = "", limit: int = 20) -> List[dict]:
    """Cari kode/uraian KBLI di graf SKOS kbr_kbli.ttl."""
    safe_q = (query or "").replace("\\", "\\\\").replace('"', '\\"').strip()
    flt = f'FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{safe_q}")) || CONTAINS(STR(?code), "{safe_q}"))' if safe_q else ""
    q = f"""
    PREFIX kbr: <{BASE_IRI}>
    PREFIX skos: <{SKOS_IRI}>
    SELECT ?code ?label ?p1 ?isTA ?isPionir ?isPK
    WHERE {{
      ?c a skos:Concept ;
         skos:notation ?code ;
         skos:prefLabel ?label .
      OPTIONAL {{ ?c kbr:nppn_OP_10IbuKota ?p1 . }}
      OPTIONAL {{ ?c kbr:isTaxAllowanceKBLI ?isTA . }}
      OPTIONAL {{ ?c kbr:isIndustriPionirKBLI ?isPionir . }}
      OPTIONAL {{ ?c kbr:isIndustriPadatKaryaKBLI ?isPK . }}
      {flt}
    }}
    ORDER BY ?code
    LIMIT {max(1, min(int(limit), 100))}
    """
    return [
        {
            "kode_kbli": str(r.code),
            "uraian": str(r.label),
            "nppn_10ibukota": float(r.p1) if r.p1 is not None else None,
            "is_tax_allowance": bool(r.isTA) if r.isTA is not None else False,
            "is_industri_pionir": bool(r.isPionir) if r.isPionir is not None else False,
            "is_industri_padat_karya": bool(r.isPK) if r.isPK is not None else False,
        }
        for r in g.query(q)
    ]
