# -*- coding: utf-8 -*-
"""Step C — Ekstraktor Deterministik Tarif Pajak Daerah (524 Perda / 390 Pemda) & RDF Exporter.

Menghasilkan:
- ontology/kbr-perda-rates.ttl   (graf RDF ABox tarif PKB, BBNKB, PBB-P2, NJOPTKP, BPHTB, NPOPTKP, PBJT, Opsen)
- ontology/step_c_build_report.json
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rdflib import Graph, Literal, Namespace, RDF, RDFS, XSD

from src.ter_kbli import resolve_nppn_wilayah_kelompok

BASE_IRI = "http://www.semanticweb.org/ontology/kbr_pajak#"

PCT_PAT = r"([0-9OoIlLSZ]+(?:[.,][0-9OoIlLSZ]+)?)\s*(?:%|0/o|o/o|persen)"
RP_PAT = r"Rp\.?\s*([0-9OoIlL.\s]+(?:,[0-9Oo]{2})?)"


def canonicalize_pemda(judul: str, document_id: str) -> Tuple[str, str, str]:
    """Kembalikan (tingkat: PROV|KOTA|KAB, pemda_id, nama_resmi) dari judul/document_id."""
    j = re.sub(r"\s+", " ", (judul or "")).strip()
    m = re.search(r"\b(Provinsi|Kota|Kabupaten)\s+(.+?)\s+Nomor\b", j, re.I)
    if m:
        tk_raw, nama = m.group(1).upper(), m.group(2).strip()
        tk = "PROV" if tk_raw.startswith("PROV") else ("KOTA" if tk_raw == "KOTA" else "KAB")
        nama = re.sub(r"^(?:Pemerintah\s+)?(?:Daerah\s+)?(?:Provinsi|Kota|Kabupaten)\s+", "", nama, flags=re.I)
        slug = re.sub(r"[^A-Z0-9]+", "_", nama.upper()).strip("_")
        if tk == "PROV" and slug == "DAERAH_KHUSUS_IBUKOTA_JAKARTA":
            slug = "DKI_JAKARTA"
            nama = "DKI Jakarta"
        label_prefix = "Provinsi" if tk == "PROV" else ("Kota" if tk == "KOTA" else "Kabupaten")
        return tk, f"{tk}_{slug}", f"{label_prefix} {nama}"
    parts = document_id.split("-")
    if len(parts) >= 4 and parts[1] in ("PROV", "KOTA", "KAB"):
        tk = parts[1]
        slug = "_".join(parts[2:-2])
        nama = slug.replace("_", " ").title()
        label_prefix = "Provinsi" if tk == "PROV" else ("Kota" if tk == "KOTA" else "Kabupaten")
        return tk, f"{tk}_{slug}", f"{label_prefix} {nama}"
    return "UNK", re.sub(r"[^A-Z0-9_]", "_", document_id.upper()), document_id


def _norm_pct(raw: str, *, lo: float = 0.01, hi: float = 75.0) -> Optional[float]:
    s = raw.strip()
    for ch, rep in (("O", "0"), ("o", "0"), ("I", "1"), ("l", "1"), ("L", "1"), ("S", "5"), ("Z", "2")):
        s = s.replace(ch, rep)
    s = s.replace(",", ".")
    s = re.sub(r"[^0-9.]", "", s)
    if s.count(".") > 1:
        return None
    try:
        v = float(s)
        return round(v, 4) if lo <= v <= hi else None
    except ValueError:
        return None


def _norm_rp(raw: str, *, lo: float = 1_000_000.0, hi: float = 5_000_000_000.0) -> Optional[float]:
    s = raw.strip()
    for ch, rep in (("O", "0"), ("o", "0"), ("I", "1"), ("l", "1"), ("L", "1")):
        s = s.replace(ch, rep)
    s = re.sub(r"[.,][0-9]{2}$", "", s)
    s = re.sub(r"[^0-9]", "", s)
    try:
        v = float(s)
        return v if lo <= v <= hi else None
    except ValueError:
        return None


def _extract_rates_from_clause(txt: str) -> List[Tuple[str, str, float, str]]:
    """Ekstrak daftar (tax_key, unit: '%'|'IDR', value, snippet) dari 1 teks klausul Perda."""
    out: List[Tuple[str, str, float, str]] = []
    low = txt.lower()

    # 1. PKB (Provinsi)
    if "pkb" in low or "kendaraan bermotor" in low:
        m = re.search(rf"tarif\s+pkb\b[^.]*?ditetapkan\s+(?:sebesar|paling\s+tinggi)\s+{PCT_PAT}", low, re.I)
        if m:
            v = _norm_pct(m.group(1), lo=0.1, hi=5.0)
            if v is not None:
                out.append(("PKB_Ke1", "%", v, txt[:450]))
        m1 = re.search(rf"{PCT_PAT}\s*(?:\([^)]+\)\s*)?untuk\s+kepemilikan[^.;]*?kendaraan\s+bermotor\s+pertama", low, re.I)
        if not m1:
            m1 = re.search(rf"kendaraan\s+bermotor\s+pertama[^.;]*?{PCT_PAT}", low, re.I)
        if m1:
            v = _norm_pct(m1.group(1), lo=0.1, hi=5.0)
            if v is not None:
                out.append(("PKB_Ke1", "%", v, txt[:450]))
        for idx, word in ((2, "kedua"), (3, "ketiga"), (4, "keempat"), (5, "kelima")):
            mp = re.search(rf"{PCT_PAT}\s*(?:\([^)]+\)\s*)?untuk\s+kepemilikan[^.;]*?kendaraan\s+bermotor\s+{word}", low, re.I)
            if not mp:
                mp = re.search(rf"kendaraan\s+bermotor\s+{word}[^.;]*?{PCT_PAT}", low, re.I)
            if mp:
                v = _norm_pct(mp.group(1), lo=0.1, hi=10.0)
                if v is not None:
                    out.append((f"PKB_Ke{idx}", "%", v, txt[:450]))

    # 2. BBNKB (Provinsi)
    m_bbn = re.search(rf"tarif\s+bbnkb\b[^.]*?ditetapkan\s+(?:sebesar|paling\s+tinggi)\s+{PCT_PAT}", low, re.I)
    if m_bbn:
        v = _norm_pct(m_bbn.group(1), lo=0.5, hi=20.0)
        if v is not None:
            out.append(("BBNKB", "%", v, txt[:450]))

    # 3. PBB-P2 (Kab/Kota/DKI) — max 0,5% sesuai UU 1/2022 HKPD Pasal 41
    # Tarif khusus (lahan produksi pangan/ternak) dipisah agar tidak menimpa tarif umum.
    if "pbb" in low:
        m_pbb = re.search(rf"tarif\s+pbb[- ]?p2\b[^.]*?(?:ditetapkan\s+)?(?:sebesar|paling\s+tinggi)\s+{PCT_PAT}", low, re.I)
        if m_pbb:
            v = _norm_pct(m_pbb.group(1), lo=0.01, hi=0.5)
            if v is not None:
                khusus = any(k in low for k in ("lahan produksi pangan", "produksi pangan dan/ atau ternak", "produksi pangan atau ternak"))
                out.append(("PBB_P2_Khusus" if khusus else "PBB_P2", "%", v, txt[:450]))

    # 4. NJOPTKP (Kab/Kota/DKI)
    if "njoptkp" in low or "tidak kena pajak" in low:
        m_nj = re.search(rf"(?:njoptkp|njop\s+tidak\s+kena\s+pajak)\b[^.]*?(?:ditetapkan\s+(?:paling\s+rendah\s+)?sebesar|paling\s+rendah\s+sebesar|sebesar)\s+{RP_PAT}", low, re.I)
        if m_nj and "npoptkp" not in low and "bphtb" not in low:
            v = _norm_rp(m_nj.group(1), lo=5_000_000.0, hi=500_000_000.0)
            if v is not None:
                out.append(("NJOPTKP", "IDR", v, txt[:450]))

    # 5. BPHTB & NPOPTKP (Kab/Kota/DKI)
    m_bp = re.search(rf"tarif\s+bphtb\b[^.]*?ditetapkan\s+(?:sebesar|paling\s+tinggi)\s+{PCT_PAT}", low, re.I)
    if m_bp:
        v = _norm_pct(m_bp.group(1), lo=1.0, hi=5.0)
        if v is not None:
            out.append(("BPHTB", "%", v, txt[:450]))

    if "npoptkp" in low or "perolehan objek pajak tidak kena pajak" in low:
        m_np = re.search(rf"(?:npoptkp|nilai\s+perolehan\s+objek\s+pajak\s+tidak\s+kena\s+pajak)\b[^.]*?(?:ditetapkan\s+(?:paling\s+rendah\s+)?sebesar|paling\s+rendah\s+sebesar|sebesar)\s+{RP_PAT}", low, re.I)
        if m_np and "hibah wasiat" not in low and "waris" not in low:
            v = _norm_rp(m_np.group(1), lo=20_000_000.0, hi=1_000_000_000.0)
            if v is not None:
                out.append(("NPOPTKP", "IDR", v, txt[:450]))

    # 6. PBJT Umum (<= 10%) vs PBJT Hiburan Khusus (40%-75%)
    if "pbjt" in low:
        m_hib = re.search(rf"(?:khusus\s+tarif\s+pbjt|tarif\s+pbjt)\s+atas\s+jasa\s+(?:hiburan|kesenian)[^.]*?(?:diskotek|karaoke|kelab|bar|mandi\s+uap|spa)[^.]*?{PCT_PAT}", low, re.I)
        if m_hib:
            v = _norm_pct(m_hib.group(1), lo=20.0, hi=75.0)
            if v is not None:
                out.append(("PBJT_Hiburan_Khusus", "%", v, txt[:450]))
        m_pb = re.search(rf"(?:^\(\d+\)\s*)?tarif\s+pbjt\s+ditetapkan\s+(?:sebesar|paling\s+tinggi)\s+{PCT_PAT}", low, re.I)
        if m_pb:
            v = _norm_pct(m_pb.group(1), lo=1.0, hi=15.0)
            if v is not None:
                out.append(("PBJT_Umum", "%", v, txt[:450]))

    # 7. Opsen PKB & Opsen BBNKB (Kab/Kota, UU 1/2022 = 66%)
    m_opkb = re.search(rf"tarif\s+opsen\s+pkb\b[^.]*?ditetapkan\s+(?:sebesar|paling\s+tinggi)\s+{PCT_PAT}", low, re.I)
    if m_opkb:
        v = _norm_pct(m_opkb.group(1), lo=10.0, hi=66.0)
        if v is not None:
            out.append(("Opsen_PKB", "%", v, txt[:450]))

    m_obbn = re.search(rf"tarif\s+opsen\s+bbnkb\b[^.]*?ditetapkan\s+(?:sebesar|paling\s+tinggi)\s+{PCT_PAT}", low, re.I)
    if m_obbn:
        v = _norm_pct(m_obbn.group(1), lo=10.0, hi=66.0)
        if v is not None:
            out.append(("Opsen_BBNKB", "%", v, txt[:450]))

    return out


def build_perda_rates_ttl(perda_dir: Path, out_ttl: Path) -> dict:
    """Ekstrak tarif dari seluruh 524 Perda dan simpan graf RDF `kbr-perda-rates.ttl`."""
    perdas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(perda_dir.glob("*.json"))]

    # Kelompokkan berdasarkan Pemda kanonik
    by_pemda: Dict[str, dict] = {}
    for d in perdas:
        tk, pid, nama = canonicalize_pemda(d.get("judul", ""), d["document_id"])
        is_perub = "perubahan" in (d.get("judul") or "").lower()
        try:
            tahun = int(d.get("tahun") or 0)
        except (TypeError, ValueError):
            tahun = 0
        rec = by_pemda.setdefault(
            pid,
            {
                "pemda_id": pid,
                "tingkat": tk,
                "nama_resmi": nama,
                "is_dki": pid == "PROV_DKI_JAKARTA",
                "nppn_wilayah": resolve_nppn_wilayah_kelompok(nama),
                "docs": [],
                "rates": {},  # tax_key -> dict
            },
        )
        rec["docs"].append((tahun, 1 if is_perub else 0, d["document_id"], d, is_perub))

    total_rate_items = 0
    tax_key_counts: Counter = Counter()
    pemda_with_rates = 0

    for pid, rec in by_pemda.items():
        # Proses Induk lebih dulu, baru Perubahan di tahun yang sama / lebih baru
        rec["docs"].sort(key=lambda x: (x[0], x[1], x[2]))
        for tahun, _, did, d, is_perub in rec["docs"]:
            # Urutkan berdasarkan lokasi pasal alami (`ord`), lalu di dalam tiap pasal dahulukan HURUF/ANGKA -> AYAT -> PASAL
            provs = d.get("provisions") or []
            prio = {"HURUF": 0, "ANGKA": 0, "ROMAN_ITEM": 0, "AYAT": 1, "PASAL": 2}
            ordered = []
            cur_pasal_ord = 0
            for idx_p, p in enumerate(provs):
                lvl = p.get("level")
                if lvl == "PASAL":
                    cur_pasal_ord = idx_p
                if lvl in prio:
                    ordered.append((cur_pasal_ord, prio[lvl], idx_p, p))
            ordered.sort(key=lambda x: (x[0], x[1], x[2]))

            doc_extracted_keys = set()
            for _, _, _, p in ordered:
                txt = re.sub(r"\s+", " ", (p.get("text") or "")).strip()
                if not txt:
                    continue
                for tax_key, unit, val, quote in _extract_rates_from_clause(txt):
                    if (did, tax_key) in doc_extracted_keys:
                        continue
                    doc_extracted_keys.add((did, tax_key))
                    rec["rates"][tax_key] = {
                        "tax_key": tax_key,
                        "unit": unit,
                        "value": val,
                        "document_id": did,
                        "tahun": tahun,
                        "is_perda_perubahan": is_perub,
                        "source_locator": p.get("locator") or did,
                        "source_quote": quote,
                    }

        if rec["rates"]:
            pemda_with_rates += 1
        for tk_key in rec["rates"]:
            tax_key_counts[tk_key] += 1
            total_rate_items += 1

    # Serialisasi RDF Turtle
    g = Graph()
    KBR = Namespace(BASE_IRI)
    g.bind("kbr", KBR)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    for pid, rec in sorted(by_pemda.items()):
        p_uri = KBR[f"Pemda_{pid}"]
        g.add((p_uri, RDF.type, KBR.PemdaDaerah))
        g.add((p_uri, KBR.hasPemdaId, Literal(pid, datatype=XSD.string)))
        g.add((p_uri, RDFS.label, Literal(rec["nama_resmi"], lang="id")))
        g.add((p_uri, KBR.hasTingkatPemda, Literal(rec["tingkat"], datatype=XSD.string)))
        g.add((p_uri, KBR.isDKIJakarta, Literal(rec["is_dki"], datatype=XSD.boolean)))
        g.add((p_uri, KBR.kelompokWilayahNPPN, Literal(rec["nppn_wilayah"], datatype=XSD.string)))
        for _, _, did, _, _ in rec["docs"]:
            g.add((p_uri, KBR.memilikiPerda, Literal(did, datatype=XSD.string)))

        for tax_key, rinfo in sorted(rec["rates"].items()):
            r_uri = KBR[f"TarifPerda_{pid}_{tax_key}"]
            g.add((r_uri, RDF.type, KBR.TarifPerdaItem))
            g.add((r_uri, KBR.untukPemda, p_uri))
            g.add((r_uri, KBR.hasJenisPajakDaerah, Literal(tax_key, datatype=XSD.string)))
            if rinfo["unit"] == "%":
                g.add((r_uri, KBR.hasTarifPersen, Literal(rinfo["value"], datatype=XSD.decimal)))
            else:
                g.add((r_uri, KBR.hasNominalRupiah, Literal(rinfo["value"], datatype=XSD.decimal)))
            g.add((r_uri, KBR.hasDocumentId, Literal(rinfo["document_id"], datatype=XSD.string)))
            g.add((r_uri, KBR.hasSourceLocator, Literal(rinfo["source_locator"], datatype=XSD.string)))
            g.add((r_uri, KBR.hasSourceQuote, Literal(rinfo["source_quote"], datatype=XSD.string)))
            g.add((r_uri, KBR.isPerdaPerubahan, Literal(rinfo["is_perda_perubahan"], datatype=XSD.boolean)))

    out_ttl.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(out_ttl), format="turtle")

    return {
        "total_perda_docs": len(perdas),
        "unique_pemda": len(by_pemda),
        "pemda_with_extracted_rates": pemda_with_rates,
        "total_rate_items": total_rate_items,
        "by_tax_key": dict(tax_key_counts.most_common()),
        "out_ttl": str(out_ttl),
    }
