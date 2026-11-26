# -*- coding: utf-8 -*-
"""Bangun katalog risiko RP-01..RP-10 & indeks CBR 284 putusan (B3/B4 tahap 1).

Menghasilkan:
- `backend/risk_patterns.json`  : 10 pola + dasar hukum (rule_id terverifikasi)
- `backend/cbr_index.json`      : indeks ringkas 284 putusan untuk similarity tahap 1

Jalankan:
    python3 scripts/build_risk_cbr.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]

def _pick(*rels: str) -> Path:
    for r in rels:
        p = ROOT / r
        if p.exists():
            return p
    return ROOT / rels[0]


RULES = ROOT / "data" / "legal_rules.jsonl"
JURIS = _pick("data/jurisprudence", "knowledge_json/jurisprudence")
OUT_RISK = ROOT / "backend" / "risk_patterns.json"
OUT_CBR = ROOT / "backend" / "cbr_index.json"
ANNOTATIONS = _pick("data/jurisprudence", "knowledge_json/jurisprudence") / "annotations" / "annotations_v1.json"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


# (pola, nama, tingkat, indikator, rekomendasi, [(document_id, locator_prefix, keyword)])
RISK_SPECS = [
    ("RP-01", "Omzet Lewat Batas Tanpa Lapor PKP", "TINGGI",
     "Peredaran bruto > Rp4,8 Miliar tetapi status belum dikukuhkan sebagai PKP.",
     "Laporkan pengukuhan PKP sebelum akhir bulan berikutnya; pisahkan pencatatan faktur.",
     [("PMK-2010-68", "PMK-2010-68#BT/4", "pengusaha kecil"),
      ("UU-1983-6", "UU-1983-6#BT/13", "Surat Ketetapan Pajak Kurang Bayar")]),
    ("RP-02", "Pekerjaan Bebas Keliru Memakai PPh Final", "TINGGI",
     "Wajib Pajak orang pribadi dengan penghasilan pekerjaan bebas menyetor PPh Final 0,5%.",
     "Hentikan penyetoran final; gunakan NPPN atau pembukuan; ajukan pemindahbukuan bila perlu.",
     [("PP-2022-55", "PP-2022-55#BT/56", "pekerjaan bebas")]),
    ("RP-03", "NPPN Tanpa Pemberitahuan Resmi", "SEDANG",
     "Menggunakan NPPN tanpa menyampaikan pemberitahuan dalam 3 bulan pertama tahun pajak.",
     "Sampaikan pemberitahuan NPPN; siapkan catatan peredaran bruto harian.",
     [("UU-1983-7", "UU-1983-7#BT/14", "pemberitahuan")]),
    ("RP-04", "Badan Melewati Masa Berlaku PPh Final", "TINGGI",
     "Badan (CV/PT/koperasi) menerapkan PPh Final padahal tidak lagi memenuhi Pasal 57(1) atau telah melewati masa peralihan.",
     "Beralih ke tarif umum; siapkan pembukuan; pertimbangkan Pasal 31E bila omzet ≤ Rp50 M.",
     [("PP-2026-20", "PP-2026-20#BT/I", "koperasi"),
      ("PP-2026-20", "PP-2026-20#BT/I", "tidak dapat dikenai Pajak Penghasilan")]),
    ("RP-05", "Pelanggaran Ambang Omzet Grup OP + PT Perorangan", "TINGGI",
     "Omzet gabungan OP beserta seluruh PT Perorangan miliknya melebihi Rp4,8 Miliar.",
     "Konsolidasikan pemantauan omzet grup; siapkan transisi pembukuan.",
     [("PP-2026-20", "PP-2026-20#BT/I", "seluruh Wajib Pajak badan berbentuk perseroan perorangan")]),
    ("RP-06", "Pemisahan Omzet Suami-Istri Keliru", "SEDANG",
     "Suami-istri dengan perjanjian pisah harta menghitung ambang Rp4,8 M secara terpisah.",
     "Hitung ambang kelayakan secara gabungan sesuai Pasal 58 PP 55/2022 jo. PP 20/2026.",
     [("PP-2026-20", "PP-2026-20#BT/I", "suami-istri"),
      ("PP-2022-55", "PP-2022-55#BT/58", "penggabungan peredaran bruto")]),
    ("RP-07", "Pembebanan Biaya Suap/Gratifikasi", "TINGGI",
     "Membebankan pengeluaran suap/gratifikasi sebagai biaya pengurang penghasilan bruto.",
     "Koreksi fiskal positif; pisahkan biaya yang memenuhi syarat 3M.",
     [("PP-2026-20", "PP-2026-20#BT/I", "suap, gratifikasi")]),
    ("RP-08", "Keterlambatan Penyetoran dan Pelaporan", "SEDANG",
     "Penyetoran melewati jatuh tempo atau SPT Masa terlambat dilaporkan.",
     "Buat kode billing, setor, dan laporkan; simpan Bukti Penerimaan Negara.",
     [("UU-1983-6", "UU-1983-6#BT/7", "denda"),
      ("PMK-2024-81", "PMK-2024-81#BT/94", "jatuh tempo")]),
    ("RP-09", "Sengketa Ekualisasi Omzet SPT vs Arus Uang", "TINGGI",
     "Terdapat selisih antara peredaran bruto dalam SPT dan mutasi rekening/SPT PPN.",
     "Susun kertas kerja ekualisasi dan rekonsiliasi fiskal; gunakan preseden CBR.",
     [("PP-2022-55", "PP-2022-55#BT/58", "peredaran bruto")]),
    ("RP-10", "Kelalaian Pemotongan PPh Pihak Ketiga", "SEDANG",
     "Membayar jasa kepada pihak lain tanpa memotong PPh Pasal 23/Pasal 21.",
     "Terbitkan bukti potong unifikasi dan setor pemotongan tepat waktu.",
     [("UU-1983-7", "UU-1983-7#BT/23", "2% (dua persen)")]),
]


def _load_rules() -> List[dict]:
    return [json.loads(l) for l in RULES.read_text(encoding="utf-8").splitlines() if l.strip()]


def _resolve(rules: List[dict], doc: str, locator_prefix: str, keyword: str) -> Optional[dict]:
    kw = keyword.lower()
    candidates = [
        r for r in rules
        if r.get("document_id") == doc and (r.get("source_locator") or "").startswith(locator_prefix)
    ]
    for r in candidates:
        if kw in (r.get("source_quote") or "").lower():
            return r
    return candidates[0] if candidates else None


def build_risk_catalog(rules: List[dict]) -> dict:
    items = []
    for pola, nama, tingkat, indikator, rekomendasi, refs in RISK_SPECS:
        dasar = []
        for doc, loc, kw in refs:
            r = _resolve(rules, doc, loc, kw)
            if r is None:
                continue
            dasar.append({
                "rule_id": r["rule_id"],
                "document_id": r["document_id"],
                "source_locator": r["source_locator"],
                "source_quote": _norm(r.get("source_quote"))[:400],
                "validation_status": r.get("validation_status"),
            })
        items.append({
            "pola_id": pola,
            "nama": nama,
            "tingkat_risiko": tingkat,
            "indikator": indikator,
            "rekomendasi": rekomendasi,
            "grounding_status": "LENGKAP" if len(dasar) == len(refs) else "PARSIAL",
            "dasar_hukum": dasar,
        })
    return {"total": len(items), "items": items}


def build_cbr_index() -> dict:
    annotations = {}
    if ANNOTATIONS.exists():
        annotations = json.loads(ANNOTATIONS.read_text(encoding="utf-8")).get("annotations") or {}
    cases = []
    for p in sorted(JURIS.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        ann = annotations.get(d.get("case_id")) or {}
        cases.append({
            "case_id": d.get("case_id"),
            "putusan_nomor": d.get("putusan_nomor"),
            "klaster": d.get("klaster"),
            "jenis_pajak": d.get("jenis_pajak"),
            "tahun_pajak": d.get("tahun_pajak"),
            "tahun_putusan": d.get("tahun_putusan"),
            "amar_kategori": d.get("amar_kategori"),
            "pokok_sengketa": _norm(d.get("pokok_sengketa"))[:1500],
            "pertimbangan_majelis": _norm(d.get("pertimbangan_majelis"))[:800],
            "cited_regulations": d.get("cited_regulations") or [],
            "source_url": (d.get("source") or {}).get("url"),
            "jenis_koreksi": ann.get("jenis_koreksi") or [],
            "fakta_kunci": ann.get("fakta_kunci") or [],
            "rasio_decidendi": ann.get("rasio_decidendi") or "",
            "argumen_menang": ann.get("argumen_menang") or "",
            "bukti_penentu": ann.get("bukti_penentu") or [],
            "annotated": bool(ann),
        })
    annotated = sum(1 for c in cases if c["annotated"])
    return {
        "total": len(cases),
        "annotated_cases": annotated,
        "metode": "tahap-1: 0.70 BM25(pokok_sengketa) + 0.20 klaster + 0.10 Jaccard(regulasi)",
        "catatan": "Formula penuh PRD §8 memakai jenis_koreksi/fakta_kunci bila kasus sudah dianotasi (lihat docs/CBR_ANNOTATION_GUIDE.md).",
        "cases": cases,
    }


def main() -> int:
    rules = _load_rules()
    risk = build_risk_catalog(rules)
    OUT_RISK.write_text(json.dumps(risk, ensure_ascii=False, indent=2), encoding="utf-8")

    cbr = build_cbr_index()
    OUT_CBR.write_text(json.dumps(cbr, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print(json.dumps({
        "risk_patterns": risk["total"],
        "grounding_lengkap": sum(1 for i in risk["items"] if i["grounding_status"] == "LENGKAP"),
        "cbr_cases": cbr["total"],
        "risk_out": str(OUT_RISK),
        "cbr_out": str(OUT_CBR),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
