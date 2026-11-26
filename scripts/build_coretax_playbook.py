# -*- coding: utf-8 -*-
"""Bangun playbook Coretax (B5) dari Buku Manual Coretax 2024 — Seri Pembayaran.

Sumber: `data/pph_op/full/PANDUAN_Coretax_2024_Seri_Pembayaran.json` (49 halaman, `raw_pages`).
Semua kode & langkah diambil verbatim dari panduan; bila tidak tercantum, ditandai null.

Menghasilkan `backend/coretax_playbook.json`.
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


SRC = _pick("data/pph_op/full", "knowledge_json/pph_op/full") / "PANDUAN_Coretax_2024_Seri_Pembayaran.json"
OUT = ROOT / "backend" / "coretax_playbook.json"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


CODE_RE = re.compile(r"(\d{6}-\d{3})\s+(.*?)(?=\s+\d{6}-\d{3}\s+|$)")


def _extract_codes(pages: List[dict]) -> List[dict]:
    out: List[dict] = []
    seen = set()
    for pg in pages:
        t = _norm(pg.get("content"))
        for m in CODE_RE.finditer(t):
            code, desc = m.group(1), m.group(2).strip()
            if code in seen:
                continue
            desc = re.sub(r"(Buku Manual|Coretax Administration System|Sistem Inti Administrasi Perpajakan|\d+ Pembayaran).*$", "", desc).strip()
            if not desc or desc.lower().startswith(("kode akun", "keterangan")):
                continue
            seen.add(code)
            out.append({
                "kap_kjs": code,
                "kap": code.split("-")[0],
                "kjs": code.split("-")[1],
                "keterangan": desc[:200],
                "halaman": pg.get("page_number"),
                "kutipan": _norm(f"{code} {desc}")[:300],
            })
    return out


def _steps(pages: List[dict], specs: List[tuple]) -> List[dict]:
    """Ambil langkah verbatim berdasarkan (halaman, kalimat awal)."""
    by_page = {p.get("page_number"): _norm(p.get("content")) for p in pages}
    out = []
    for page, start in specs:
        text = by_page.get(page, "")
        i = text.find(start)
        if i < 0:
            continue
        sentence = text[i : i + 220]
        out.append({"halaman": page, "teks": sentence, "kutipan": start})
    return out


def _pick(codes: List[dict], *needles: str) -> Optional[dict]:
    for c in codes:
        low = c["keterangan"].lower()
        if all(n.lower() in low for n in needles):
            return c
    return None


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    pages = data.get("raw_pages") or []
    codes = _extract_codes(pages)

    billing_steps = _steps(pages, [
        (23, "silakan pilih modul “Pembayaran”"),
        (24, "Silakan pilih Kode Akun Pajak dan Kode Jenis Setor"),
        (24, "Tekan tombol Lanjut"),
        (25, "Isikan Nilai"),
        (25, "Tekan tombol “Unduh Kode Billing"),
    ])
    tagihan_steps = _steps(pages, [
        (30, "silakan pilih modul “Pembayaran”"),
        (31, "Pilih tunggakan yang akan dibayar"),
        (31, "isikan nominal pembayaran"),
        (31, "Buat Kode Billing"),
    ])

    umkm = _pick(codes, "final umkm")
    sewa = _pick(codes, "sewa tanah")
    alih = _pick(codes, "pengalihan hak tanah")
    op29 = _pick(codes, "pasal 25/29 orang pribadi", "masa")
    badan29 = _pick(codes, "pasal 25/29 badan", "masa")
    ppn = _pick(codes, "ppn dalam negeri")
    pbb = _pick(codes, "pbb")
    konstruksi = _pick(codes, "jasa konstruksi")

    def entry(key: str, judul: str, code: Optional[dict], extra_catatan: Optional[str] = None) -> dict:
        return {
            "kode": key,
            "judul": judul,
            "kap_kjs": code["kap_kjs"] if code else None,
            "keterangan_kap_kjs": code["keterangan"] if code else None,
            "halaman_kap_kjs": code["halaman"] if code else None,
            "langkah": billing_steps,
            "dokumen": ["Kode Billing", "Bukti Penerimaan Negara (BPN)/NTPN"],
            "catatan": extra_catatan or (
                None if code else "KAP/KJS tidak tercantum pada Buku Manual Coretax 2024 Seri Pembayaran."
            ),
        }

    mapping = {
        "PLAYBOOK_KODE_BILLING": entry("PLAYBOOK_KODE_BILLING", "Pembuatan kode billing pembayaran mandiri", None),
        "PLAYBOOK_TAGIHAN": {
            "kode": "PLAYBOOK_TAGIHAN",
            "judul": "Pembayaran tagihan/ketetapan (STP/SKPKB)",
            "kap_kjs": None,
            "keterangan_kap_kjs": None,
            "halaman_kap_kjs": None,
            "langkah": tagihan_steps,
            "dokumen": ["Kode Billing atas Tagihan", "BPN/NTPN"],
            "catatan": "KAP/KJS mengikuti jenis tagihan yang tampil pada daftar tunggakan.",
        },
        "Kewajiban_LaporSPT": entry("Kewajiban_LaporSPT", "Penyetoran kurang bayar SPT Tahunan OP", op29),
        "Kewajiban_Tenggat_SPT_Tahunan_OP_3Bln": entry("Kewajiban_Tenggat_SPT_Tahunan_OP_3Bln", "Penyetoran PPh 29 Orang Pribadi", op29),
        "Kewajiban_Tenggat_SPT_Tahunan_Badan_4Bln": entry("Kewajiban_Tenggat_SPT_Tahunan_Badan_4Bln", "Penyetoran PPh 29 Badan", badan29),
        "Kewajiban_PotongSetor_SewaTanahBangunan": entry("Kewajiban_PotongSetor_SewaTanahBangunan", "Setor PPh Final sewa tanah/bangunan", sewa),
        "Kewajiban_SetorSSP_ValidasiKPP_SebelumAkta": entry("Kewajiban_SetorSSP_ValidasiKPP_SebelumAkta", "Setor PPh Final pengalihan hak atas tanah/bangunan", alih),
        "Kewajiban_PekerjaBebas_TarifUmum_NonPP55": entry("Kewajiban_PekerjaBebas_TarifUmum_NonPP55", "Setor PPh 25/29 Orang Pribadi", op29),
        "Kewajiban_Rekonsiliasi_MultiPemberiKerja": entry("Kewajiban_Rekonsiliasi_MultiPemberiKerja", "Setor kurang bayar PPh 29 Orang Pribadi", op29),
        "Kewajiban_DaftarPKP_PungutPPN": entry("Kewajiban_DaftarPKP_PungutPPN", "Setor PPN dalam negeri", ppn),
        "Kewajiban_LaporPBB": entry("Kewajiban_LaporPBB", "Setor PBB", pbb,
                                     "Kode PBB tidak tercantum pada panduan pembayaran ini; gunakan menu pembayaran daerah/MPN sesuai ketentuan."),
        "Kewajiban_PencatatanTerpisah_JasaKonstruksi": entry("Kewajiban_PencatatanTerpisah_JasaKonstruksi", "Setor PPh Final jasa konstruksi", konstruksi),
        "Fasilitas_PP55_Final_0_5Pct": entry("Fasilitas_PP55_Final_0_5Pct", "Setor PPh Final UMKM 0,5%", umkm),
    }

    menu = [
        {"nomor": "01", "nama": "Permohonan Pemindahbukuan"},
        {"nomor": "02", "nama": "Layanan Mandiri Kode Billing"},
        {"nomor": "03", "nama": "Pembuatan Kode Billing atas Tagihan Pajak"},
        {"nomor": "04", "nama": "Daftar Kode Billing Belum Dibayar"},
        {"nomor": "05", "nama": "Formulir Restitusi Pajak"},
    ]

    out = {
        "sumber": {
            "document_id": "PANDUAN-CORETAX-2024-PEMBAYARAN",
            "nama": data.get("metadata", {}).get("document_name"),
            "jenis_sumber": "panduan_djp",
            "total_halaman": data.get("metadata", {}).get("total_pages"),
            "catatan": "Bukan peraturan; jangan dipakai sebagai dasar hukum. Selalu tampilkan label 'panduan DJP'.",
        },
        "menu": menu,
        "kode": codes,
        "peta_kewajiban": mapping,
        "langkah_umum": billing_steps,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "kode_terekstrak": len(codes),
        "langkah_billing": len(billing_steps),
        "langkah_tagihan": len(tagihan_steps),
        "mapping_kewajiban": len(mapping),
        "out": str(OUT),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
