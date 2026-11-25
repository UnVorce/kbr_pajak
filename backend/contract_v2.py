# -*- coding: utf-8 -*-
"""Kontrak API v2.0.0 — adaptor schema PRD §9.3 <-> engine internal.

PRD memakai payload snake_case bersarang (`pekerjaan_utama`, `pekerjaan_sekunder`,
`penghasilan_final`). Engine internal memakai properti OWL camelCase. Modul ini
menerjemahkan keduanya dan membentuk respons sesuai PRD §9.3.4 — tanpa menaruh
logika tarif di Python: seluruh tarif dibaca dari ontologi (`hasTarifPersen`).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

_NPPN_KELOMPOK_PATH = Path(__file__).with_name("nppn_kelompok.json")


def _load_nppn_kelompok() -> Dict[str, dict]:
    if not _NPPN_KELOMPOK_PATH.exists():
        return {}
    data = json.loads(_NPPN_KELOMPOK_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


_NPPN_KELOMPOK = _load_nppn_kelompok()

WP_KIND = Literal["OrangPribadi", "PT", "CV", "Koperasi", "Yayasan", "BadanUsahaTetap", "BUT", "Badan"]
JENIS_PEKERJAAN = Literal[
    "PEGAWAI_TETAP", "PEGAWAI_TIDAK_TETAP", "PESERTA_KEGIATAN", "PEKERJA_BEBAS", "USAHA_UMKM",
]
STATUS_PTKP = Literal["TK/0", "TK/1", "TK/2", "TK/3", "K/0", "K/1", "K/2", "K/3"]
ZONA_NPPN = Literal["10_IBU_KOTA_PROVINSI", "IBU_KOTA_PROVINSI_LAINNYA", "DAERAH_LAINNYA"]

_ZONA_TO_INTERNAL = {
    "10_IBU_KOTA_PROVINSI": "10_IbuKota_Provinsi",
    "IBU_KOTA_PROVINSI_LAINNYA": "IbuKota_Provinsi_Lain",
    "DAERAH_LAINNYA": "Daerah_Lain",
}
_JENIS_TO_JOB = {
    "PEGAWAI_TETAP": "PegawaiTetap_Swasta",
    "PEGAWAI_TIDAK_TETAP": "Pegawai_Tidak_Tetap_Harian",
    "PESERTA_KEGIATAN": "Peserta_Kegiatan_Lomba_Seminar_Magang",
    "PEKERJA_BEBAS": "PekerjaBebas_Umum",
    "USAHA_UMKM": "PelakuUsaha_Umum",
}
_KONSTRUKSI_TO_JENIS = {
    "KECIL_SBU": "Jenis_JasaKonstruksi_Kecil_SBU",
    "NON_KECIL_SBU": "Jenis_JasaKonstruksi_NonKecil_SBU",
    "TERINTEGRASI_SBU": "Jenis_JasaKonstruksi_Terintegrasi_SBU",
    "TANPA_SBU": "Jenis_JasaKonstruksi_TanpaSBU",
    "TERINTEGRASI_TANPA_SBU": "Jenis_JasaKonstruksi_Terintegrasi_TanpaSBU",
    "KONSULTANSI_SBU": "Jenis_JasaKonstruksi_Konsultansi_SBU",
    "KONSULTANSI_TANPA_SBU": "Jenis_JasaKonstruksi_Konsultansi_TanpaSBU",
}
_PENGALIHAN_TO_JENIS = {
    "UMUM": "Jenis_PengalihanTanahBangunan_Umum",
    "RUMAH_SEDERHANA": "Jenis_PengalihanRumahSederhana",
    "PEMERINTAH": "Jenis_PengalihanKepadaPemerintah",
}


class PekerjaanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nama: str = Field(min_length=1, max_length=160)
    jenis: JENIS_PEKERJAAN
    kbli: Optional[str] = Field(default=None, max_length=10)
    gaji_bulanan: Optional[float] = Field(default=None, ge=0)
    omzet_tahunan: Optional[float] = Field(default=None, ge=0)
    hpp_tahunan: Optional[float] = Field(default=None, ge=0)
    biaya_operasional_tahunan: Optional[float] = Field(default=None, ge=0)


class JasaKonstruksiInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jenis: Literal[
        "KECIL_SBU", "NON_KECIL_SBU", "TERINTEGRASI_SBU", "TANPA_SBU",
        "TERINTEGRASI_TANPA_SBU", "KONSULTANSI_SBU", "KONSULTANSI_TANPA_SBU",
    ]
    nilai_bruto: float = Field(ge=0)


class PengalihanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jenis: Literal["UMUM", "RUMAH_SEDERHANA", "PEMERINTAH"]
    nilai: float = Field(ge=0)


class PenghasilanFinalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sewa_tanah_bangunan: float = Field(default=0, ge=0)
    bunga_deposito: float = Field(default=0, ge=0)
    pokok_deposito: float = Field(default=0, ge=0)
    jasa_konstruksi: Optional[JasaKonstruksiInput] = None
    pengalihan_tanah_bangunan: Optional[PengalihanInput] = None
    is_jasa_akomodasi_penginapan: bool = False
    is_penghasilan_dibawah_ptkp: bool = False


class ReasonRequest(BaseModel):
    """Payload PRD §9.3.3 (field di root, bukan di dalam `properties`)."""

    model_config = ConfigDict(extra="forbid")

    wp_id: str = Field(default="WP_SESSI_001", min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    wp_kind: WP_KIND = "OrangPribadi"
    tahun_pajak: int = Field(default=2026, ge=2000, le=2100)

    # Domisili & zona NPPN
    pemda_id: Optional[str] = Field(default=None, max_length=80)
    kelompok_wilayah_nppn: Optional[ZONA_NPPN] = None
    kode_kbli: Optional[str] = Field(default=None, max_length=10, description="KBLI utama (wajib untuk Badan)")
    lokasi_provinsi_tax_allowance: Optional[str] = Field(default=None, max_length=80)

    # Multi-stream income
    pekerjaan_utama: Optional[PekerjaanInput] = None
    pekerjaan_sekunder: Optional[PekerjaanInput] = None

    # Orang pribadi
    is_kawin: bool = False
    has_jumlah_tanggungan: int = Field(default=0, ge=0, le=10)
    status_ptkp: Optional[STATUS_PTKP] = None
    is_pemberitahuan_nppn_tepat_waktu: bool = True
    is_penduduk_indonesia: bool = True
    is_subjek_luar_negeri: bool = False

    # Objek PBB-P2
    is_memiliki_objek_pbb: bool = False
    has_nilai_njop: float = Field(default=0, ge=0)
    has_njoptkp_pbb: Optional[float] = Field(default=None, ge=0)
    has_persentase_njop_pbb: Optional[float] = Field(default=None, ge=0, le=100)

    # Badan
    is_perseroan_terbuka: bool = False
    has_persentase_saham_publik: float = Field(default=0, ge=0, le=100)
    has_jumlah_pemegang_saham_publik: Optional[int] = Field(default=None, ge=0)
    has_hari_terpenuhi_tbk: Optional[int] = Field(default=None, ge=0, le=366)
    is_industri_pionir: bool = False
    is_penanaman_modal_baru: bool = False
    has_surat_keterangan_fiskal: bool = False
    is_belum_pernah_putus_tax_holiday: bool = False
    has_nilai_investasi: float = Field(default=0, ge=0)
    is_bidang_usaha_tax_allowance: bool = False
    is_lokasi_provinsi_memenuhi_tax_allowance: bool = False
    is_industri_padat_karya: bool = False

    # Umum
    has_omzet_tahunan: Optional[float] = Field(default=None, ge=0)
    has_penghasilan_kena_pajak_tahunan: Optional[float] = Field(default=None, ge=0)
    has_penghasilan_bruto_bulanan: Optional[float] = Field(default=None, ge=0)
    is_umkm_pp55: bool = False
    tahun_mulai_pp55: Optional[int] = Field(default=None, ge=2000, le=2100)
    is_milik_pribadi: bool = False
    has_jumlah_kendaraan: int = Field(default=0, ge=0)
    has_kapasitas_mesin_cc: Optional[int] = Field(default=None, ge=0)
    is_domisili_dki: bool = False
    is_usaha_spa_kesehatan_tradisional: bool = False
    is_usaha_hiburan_spa_umum: bool = False
    is_penerima_penghasilan_pph23_jasa_sewa: bool = False
    is_penerima_penghasilan_pph23_modal: bool = False
    is_bank_penerima_penghasilan: bool = False

    # PPN
    has_dpp_ppn: Optional[float] = Field(default=None, ge=0)
    is_penyerahan_bkp_mewah: bool = False
    is_penyerahan_non_mewah_ppn: bool = False
    is_penyerahan_bkp_strategis: bool = False

    # Kredit pajak
    kredit_pajak_1721a1: float = Field(default=0, ge=0)
    jumlah_bukti_potong: Optional[int] = Field(default=None, ge=0)

    # Kepatuhan / sanksi
    is_terlambat_lapor_spt: bool = False
    is_terlambat_lapor_spt_masa_ppn: bool = False
    is_kurang_bayar_skpkb: bool = False
    is_tidak_setor_pajak_dipungut: bool = False
    is_keberatan_ditolak: bool = False
    is_banding_ditolak: bool = False
    is_dikecualikan_denda_spt: bool = False

    # PPh Final Pasal 4(2)
    penghasilan_final: Optional[PenghasilanFinalInput] = None

    # Override NPPN (dipakai bila KBLI tidak punya tarif norma)
    persentase_nppn: Optional[float] = Field(default=None, ge=0, le=100)


# --------------------------------------------------------------------------------------
# Request -> internal properties (camelCase untuk engine/ontology)
# --------------------------------------------------------------------------------------
def _job_for(engine, pekerjaan: Optional[PekerjaanInput]) -> Optional[str]:
    if pekerjaan is None:
        return None
    if pekerjaan.kbli:
        info = engine.lookup_kbli(pekerjaan.kbli)
        if info and info.get("terkait_jenis_pekerjaan"):
            return info["terkait_jenis_pekerjaan"]
    return _JENIS_TO_JOB[pekerjaan.jenis]


def _is_employee(p: Optional[PekerjaanInput]) -> bool:
    return p is not None and p.jenis in ("PEGAWAI_TETAP", "PEGAWAI_TIDAK_TETAP", "PESERTA_KEGIATAN")


def _annual_gross(p: Optional[PekerjaanInput]) -> float:
    if p is None:
        return 0.0
    if p.gaji_bulanan:
        return float(p.gaji_bulanan) * 12.0
    return float(p.omzet_tahunan or 0.0)


def _biaya_jabatan(gross_annual: float) -> float:
    """Biaya jabatan 5% dari bruto, maksimum Rp6.000.000/tahun (UU PPh Pasal 21)."""
    return min(gross_annual * 0.05, 6_000_000.0)


def resolve_ptkp_status(req: ReasonRequest) -> str:
    if req.status_ptkp:
        return req.status_ptkp
    tanggungan = min(max(req.has_jumlah_tanggungan, 0), 3)
    return f"{'K' if req.is_kawin else 'TK'}/{tanggungan}"


def to_internal(engine, req: ReasonRequest) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """Kembalikan (wp_kind, props_internal, ctx) — ctx dipakai untuk menyusun respons v2."""
    props: Dict[str, Any] = {}

    zona_internal: Optional[str] = None
    if req.kelompok_wilayah_nppn:
        zona_internal = _ZONA_TO_INTERNAL[req.kelompok_wilayah_nppn]
    elif req.pemda_id:
        try:
            info = engine.lookup_pemda(req.pemda_id)
            if info:
                zona_internal = info.get("nppn_wilayah_kelompok")
        except FileNotFoundError:
            zona_internal = None

    if req.pemda_id:
        props["pemdaId"] = req.pemda_id
    if zona_internal and req.wp_kind == "OrangPribadi":
        props["kelompokWilayahNPPN"] = zona_internal

    # Pekerjaan: kumpulkan seluruh jenis pekerjaan (multi-peran aman di OWL)
    jobs: List[str] = []
    for p in (req.pekerjaan_utama, req.pekerjaan_sekunder):
        job = _job_for(engine, p)
        if job and job not in jobs:
            jobs.append(job)
    if jobs and req.wp_kind == "OrangPribadi":
        props["memilikiPekerjaan"] = jobs

    kbli_utama = req.kode_kbli or (req.pekerjaan_utama.kbli if req.pekerjaan_utama else None)
    if kbli_utama:
        props["kodeKBLI"] = kbli_utama
    if req.lokasi_provinsi_tax_allowance:
        props["lokasiProvinsiTaxAllowance"] = req.lokasi_provinsi_tax_allowance

    utama, sekunder = req.pekerjaan_utama, req.pekerjaan_sekunder
    omzet_bisnis = 0.0
    if utama is not None and (not _is_employee(utama) or req.wp_kind != "OrangPribadi"):
        omzet_bisnis += float(utama.omzet_tahunan or 0.0)
    if sekunder is not None:
        omzet_bisnis += float(sekunder.omzet_tahunan or 0.0)
    omzet_total = float(req.has_omzet_tahunan) if req.has_omzet_tahunan is not None else omzet_bisnis
    if omzet_total > 0:
        props["hasOmzetTahunan"] = omzet_total

    bruto_bulanan = req.has_penghasilan_bruto_bulanan
    if bruto_bulanan is None and utama is not None and utama.gaji_bulanan:
        bruto_bulanan = float(utama.gaji_bulanan)
    if bruto_bulanan:
        if req.wp_kind == "OrangPribadi":
            props["hasPenghasilanBrutoBulanan"] = bruto_bulanan

    # PTKP & neto (dipakai untuk PKP agar klasifikasi lapisan Pasal 17 ikut aktif)
    ptkp_status = resolve_ptkp_status(req) if req.wp_kind == "OrangPribadi" else None
    ptkp_table = engine.get_ptkp_table() if req.wp_kind == "OrangPribadi" else {}
    ptkp_nominal = float((ptkp_table.get(ptkp_status or "") or {}).get("nominal") or 0.0)

    neto_utama_benar, neto_utama_prd = _neto_utama(utama, req.wp_kind)
    if req.has_penghasilan_kena_pajak_tahunan is not None:
        props["hasPenghasilanKenaPajakTahunan"] = float(req.has_penghasilan_kena_pajak_tahunan)

    # Bendera & angka umum (dipisah per domain properti agar tidak melanggar disjointness OWL)
    props.update({
        "isUMKM_PP55": bool(req.is_umkm_pp55),
        "hasNPWP": True,
        "isMilikPribadi": bool(req.is_milik_pribadi),
        "hasJumlahKendaraan": int(req.has_jumlah_kendaraan),
        "isPenyerahanBKP_Mewah": bool(req.is_penyerahan_bkp_mewah),
        "isPenyerahanNonMewahPPN": bool(req.is_penyerahan_non_mewah_ppn),
        "isPenyerahanBKPStrategis": bool(req.is_penyerahan_bkp_strategis),
        "isTerlambatLaporSPT": bool(req.is_terlambat_lapor_spt),
        "isTerlambatLaporSPTMasaPPN": bool(req.is_terlambat_lapor_spt_masa_ppn),
        "isKurangBayarSKPKB": bool(req.is_kurang_bayar_skpkb),
        "isTidakSetorPajakDipungut": bool(req.is_tidak_setor_pajak_dipungut),
        "isKeberatanDitolak": bool(req.is_keberatan_ditolak),
        "isBandingDitolak": bool(req.is_banding_ditolak),
        "isDikecualikanDendaSPT": bool(req.is_dikecualikan_denda_spt),
        "isMemilikiObjekPBB": bool(req.is_memiliki_objek_pbb),
        "hasNilaiNJOP": float(req.has_nilai_njop),
        "isDomisiliDKI": bool(req.is_domisili_dki),
        "isUsahaSpaKesehatanTradisional": bool(req.is_usaha_spa_kesehatan_tradisional),
        "isUsahaHiburanSpaUmum": bool(req.is_usaha_hiburan_spa_umum),
        "isPenerimaPenghasilanPPh23_JasaSewa": bool(req.is_penerima_penghasilan_pph23_jasa_sewa),
        "isPenerimaPenghasilanPPh23_Modal": bool(req.is_penerima_penghasilan_pph23_modal),
        "isBankPenerimaPenghasilan": bool(req.is_bank_penerima_penghasilan),
    })
    if req.wp_kind == "OrangPribadi":
        props.update({
            "isSubjekLuarNegeri": bool(req.is_subjek_luar_negeri),
            "isPendudukIndonesia": bool(req.is_penduduk_indonesia),
            "isKawin": bool(req.is_kawin),
            "hasJumlahTanggungan": int(req.has_jumlah_tanggungan),
            "isPemberitahuanNPPNTepatWaktu": bool(req.is_pemberitahuan_nppn_tepat_waktu),
        })
    else:
        props.update({
            "isPerseroanTerbuka": bool(req.is_perseroan_terbuka),
            "hasPersentaseSahamPublik": float(req.has_persentase_saham_publik),
        })
        # Flag yang punya deteksi otomatis dari KBLI hanya dikirim bila True,
        # agar engine dapat menyimpulkannya dari kodeKBLI (bukan terkunci False).
        for key, val in (
            ("isIndustriPionir", req.is_industri_pionir),
            ("isPenanamanModalBaru", req.is_penanaman_modal_baru),
            ("hasSuratKeteranganFiskal", req.has_surat_keterangan_fiskal),
            ("isBelumPernahPutusTaxHoliday", req.is_belum_pernah_putus_tax_holiday),
            ("isBidangUsahaTaxAllowance", req.is_bidang_usaha_tax_allowance),
            ("isLokasiProvinsiMemenuhiTaxAllowance", req.is_lokasi_provinsi_memenuhi_tax_allowance),
            ("isIndustriPadatKarya", req.is_industri_padat_karya),
        ):
            if not val:
                continue
            if req.wp_kind in ("BUT", "BadanUsahaTetap") and key in (
                "isBidangUsahaTaxAllowance",
                "isLokasiProvinsiMemenuhiTaxAllowance",
                "isIndustriPadatKarya",
            ):
                continue  # domain BadanDalamNegeri -> BUT disjoint (cegah kontradiksi)
            props[key] = True
        if req.has_nilai_investasi:
            props["hasNilaiInvestasi"] = float(req.has_nilai_investasi)
    if req.has_njoptkp_pbb is not None:
        props["hasNJOPTKP_PBB"] = float(req.has_njoptkp_pbb)
    if req.has_persentase_njop_pbb is not None:
        props["hasPersentaseNJOP_PBB"] = float(req.has_persentase_njop_pbb)
    if req.has_kapasitas_mesin_cc is not None:
        props["hasKapasitasMesinCC"] = int(req.has_kapasitas_mesin_cc)
    if req.wp_kind != "OrangPribadi" and req.has_jumlah_pemegang_saham_publik is not None:
        props["hasJumlahPemegangSahamPublik"] = int(req.has_jumlah_pemegang_saham_publik)
    if req.wp_kind != "OrangPribadi" and req.has_hari_terpenuhi_tbk is not None:
        props["hasHariTerpenuhiTbk"] = int(req.has_hari_terpenuhi_tbk)
    if req.has_dpp_ppn is not None:
        props["hasDPP_PPN"] = float(req.has_dpp_ppn)

    if req.penghasilan_final:
        pf = req.penghasilan_final
        finals: List[str] = []
        if pf.sewa_tanah_bangunan > 0:
            finals.append("Jenis_SewaTanahBangunan")
            props["hasNilaiSewaTanahBangunanTahunan"] = pf.sewa_tanah_bangunan
        if pf.bunga_deposito > 0:
            finals.append("Jenis_BungaDepositoTabungan")
            props["hasBungaDepositoTabunganTahunan"] = pf.bunga_deposito
        if pf.pokok_deposito > 0:
            props["hasPokokDepositoTabungan"] = pf.pokok_deposito
        if pf.jasa_konstruksi:
            finals.append(_KONSTRUKSI_TO_JENIS[pf.jasa_konstruksi.jenis])
            props["hasNilaiBrutoJasaKonstruksi"] = pf.jasa_konstruksi.nilai_bruto
        if pf.pengalihan_tanah_bangunan:
            finals.append(_PENGALIHAN_TO_JENIS[pf.pengalihan_tanah_bangunan.jenis])
            props["hasNilaiPengalihanTanahBangunan"] = pf.pengalihan_tanah_bangunan.nilai
        props["isJasaAkomodasiPenginapan"] = bool(pf.is_jasa_akomodasi_penginapan)
        if req.wp_kind == "OrangPribadi":
            props["isPenghasilanDibawahPTKP"] = bool(pf.is_penghasilan_dibawah_ptkp)
        if finals:
            props["memilikiPenghasilanFinal"] = finals

    ctx = {
        "ptkp_status": ptkp_status,
        "ptkp_nominal": ptkp_nominal,
        "neto_utama_benar": neto_utama_benar,
        "neto_utama_prd": neto_utama_prd,
        "omzet_bisnis": omzet_bisnis,
        "utama": utama,
        "sekunder": sekunder,
        "zona_nppn": zona_internal,
        "gaji_bruto_bulanan": float(bruto_bulanan) if bruto_bulanan else None,
    }

    # Estimasi awal dipakai untuk mengaktifkan klasifikasi lapisan Pasal 17 di ontologi.
    pp55 = _pp55_eligibility(req, sekunder)
    komparasi = _komparasi(engine, req, sekunder, zona_internal, pp55)
    ctx["pp55"] = pp55
    ctx["komparasi"] = komparasi
    rekonsiliasi = _rekonsiliasi(engine, req, ctx, komparasi, mode="benar")
    ctx["rekonsiliasi"] = rekonsiliasi
    ctx["rekonsiliasi_prd"] = _rekonsiliasi(engine, req, ctx, komparasi, mode="prd")
    if (
        rekonsiliasi is not None
        and req.has_penghasilan_kena_pajak_tahunan is None
        and rekonsiliasi["penghasilan_kena_pajak_pkp"] > 0
    ):
        props["hasPenghasilanKenaPajakTahunan"] = rekonsiliasi["penghasilan_kena_pajak_pkp"]

    return req.wp_kind, props, ctx


def _neto_utama(p: Optional[PekerjaanInput], wp_kind: str) -> Tuple[float, float]:
    """(neto mode benar, neto mode PRD) untuk penghasilan utama."""
    if p is None:
        return 0.0, 0.0
    if _is_employee(p):
        gross = _annual_gross(p)
        return max(0.0, gross - _biaya_jabatan(gross)), gross
    omzet = float(p.omzet_tahunan or 0.0)
    neto = max(0.0, omzet - float(p.hpp_tahunan or 0.0) - float(p.biaya_operasional_tahunan or 0.0))
    return neto, neto


# --------------------------------------------------------------------------------------
# Perhitungan komparasi 3 skema & rekonsiliasi
# --------------------------------------------------------------------------------------
_PP55_LIMIT = {"OrangPribadi": 7, "CV": 4, "Firma": 4, "Koperasi": 4, "PT": 3, "BadanUsahaTetap": 0, "Badan": 4}


def _pp55_eligibility(req: ReasonRequest, sekunder: Optional[PekerjaanInput]) -> dict:
    p = sekunder
    if p is None:
        return {"status": "TIDAK_RELEVAN", "alasan": "Tidak ada penghasilan sekunder dari usaha."}
    if p.jenis == "PEKERJA_BEBAS":
        return {
            "status": "DISKUALIFIKASI",
            "alasan": "PP 55/2022 Pasal 56(3)-(4) mengecualikan penghasilan pekerjaan bebas dari PPh Final 0,5%.",
        }
    if p.jenis != "USAHA_UMKM":
        return {"status": "TIDAK_RELEVAN", "alasan": "Bukan penghasilan usaha."}
    omzet = float(p.omzet_tahunan or 0.0)
    if omzet > 4_800_000_000.0:
        return {"status": "DISKUALIFIKASI", "alasan": "Peredaran bruto melebihi Rp4,8 miliar (PP 55/2022 Pasal 57)."}
    limit = _PP55_LIMIT.get(req.wp_kind)
    if req.tahun_mulai_pp55 is not None and limit:
        if req.tahun_pajak - req.tahun_mulai_pp55 >= limit:
            return {
                "status": "DISKUALIFIKASI",
                "alasan": f"Masa berlaku PPh Final PP 55/2022 ({limit} Tahun Pajak) telah berakhir.",
            }
    if req.tahun_mulai_pp55 is None:
        return {
            "status": "LAYAK",
            "alasan": "Memenuhi syarat omzet; masa berlaku belum diverifikasi (tahun_mulai_pp55 kosong).",
            "catatan": "Isi tahun_mulai_pp55 agar masa berlaku 7/4/3 Tahun Pajak dapat diuji.",
        }
    return {"status": "LAYAK", "alasan": "Memenuhi syarat omzet dan masih dalam masa berlaku."}


def _nppn_for(engine, sekunder: Optional[PekerjaanInput], zona: Optional[str], override: Optional[float]) -> dict:
    if sekunder is None or not sekunder.omzet_tahunan:
        return {"status": "TIDAK_RELEVAN"}
    if override is not None:
        return {
            "status": "TERSEDIA",
            "persentase_norma": float(override),
            "sumber_norma": "input_pengguna",
        }
    if not sekunder.kbli:
        return {"status": "TIDAK_TERSEDIA", "alasan": "KBLI pekerjaan sekunder belum diisi."}
    info = engine.lookup_kbli(sekunder.kbli)
    if not info:
        return {"status": "TIDAK_TERSEDIA", "alasan": f"KBLI {sekunder.kbli} tidak ditemukan di katalog SKOS."}
    pct = (info.get("nppn_op") or {}).get(zona or "Daerah_Lain")
    if pct is None:
        mapping = _NPPN_KELOMPOK.get(str(sekunder.kbli).strip())
        if mapping:
            grup = engine.lookup_kbli(mapping["kelompok"])
            pct_grup = ((grup or {}).get("nppn_op") or {}).get(zona or "Daerah_Lain")
            if pct_grup is not None:
                return {
                    "status": "TERSEDIA",
                    "persentase_norma": float(pct_grup),
                    "sumber_norma": f"kelompok {mapping['kelompok']} (dipetakan dari KBLI {sekunder.kbli})",
                    "catatan": mapping.get("catatan"),
                }
        return {
            "status": "TIDAK_TERSEDIA",
            "alasan": (
                f"Lampiran NPPN tidak memuat persentase untuk KBLI {sekunder.kbli} "
                f"pada zona {zona or 'Daerah_Lain'}. Isi `persentase_nppn` secara manual."
            ),
        }
    return {"status": "TERSEDIA", "persentase_norma": float(pct), "sumber_norma": f"KBLI {sekunder.kbli} ({zona})"}


def _komparasi(engine, req: ReasonRequest, sekunder: Optional[PekerjaanInput], zona: Optional[str], pp55: dict) -> dict:
    if sekunder is None:
        return {"objek_komparasi": "penghasilan_sekunder", "status": "TIDAK_RELEVAN"}

    omzet = float(sekunder.omzet_tahunan or 0.0)
    hpp = float(sekunder.hpp_tahunan or 0.0)
    biaya = float(sekunder.biaya_operasional_tahunan or 0.0)
    neto_pembukuan = max(0.0, omzet - hpp - biaya)
    pph_pembukuan, _ = engine.progressive_pph17(neto_pembukuan)

    nppn = _nppn_for(engine, sekunder, zona, req.persentase_nppn)
    neto_nppn = None
    pph_nppn = None
    if nppn["status"] == "TERSEDIA":
        neto_nppn = round(omzet * (nppn["persentase_norma"] / 100.0), 2)
        pph_nppn, _ = engine.progressive_pph17(neto_nppn)

    tarif_pp55 = _tarif_persen(engine, "Fasilitas_PP55_Final_0_5Pct")
    pph_pp55 = round(omzet * (tarif_pp55 / 100.0), 2) if pp55["status"] == "LAYAK" else None

    skema = {
        "skema_pp55_final": {
            "status": pp55["status"],
            "alasan": pp55.get("alasan"),
            "omzet": omzet,
            "tarif_persen": tarif_pp55 if pp55["status"] == "LAYAK" else None,
            "pph_idr": pph_pp55,
        },
        "skema_pembukuan": {
            "status": "TERSEDIA",
            "omzet": omzet,
            "hpp_tahunan": hpp,
            "biaya_operasional_tahunan": biaya,
            "penghasilan_neto": round(neto_pembukuan, 2),
            "estimasi_pph_idr": pph_pembukuan,
            "catatan": "Estimasi PPh atas penghasilan sekunder saja (sebelum PTKP).",
        },
        "skema_norma_nppn": {
            "status": nppn["status"],
            "alasan": nppn.get("alasan"),
            "omzet": omzet,
            "persentase_norma": nppn.get("persentase_norma"),
            "sumber_norma": nppn.get("sumber_norma"),
            "penghasilan_neto": neto_nppn,
            "estimasi_pph_idr": pph_nppn,
            "catatan": "Estimasi PPh atas penghasilan sekunder saja (sebelum PTKP).",
        },
    }

    kandidat: List[Tuple[float, str, str]] = []
    if pph_pp55 is not None:
        kandidat.append((pph_pp55, "skema_pp55_final", "PPh Final UMKM 0,5%"))
    if pph_nppn is not None:
        kandidat.append((pph_nppn, "skema_norma_nppn", "Norma Penghitungan Penghasilan Neto (NPPN)"))
    kandidat.append((pph_pembukuan, "skema_pembukuan", "Pembukuan tarif umum Pasal 17"))

    # Tie-break: PP 55 -> NPPN -> pembukuan (urutan kandidat sudah mencerminkan prioritas)
    kandidat.sort(key=lambda x: (x[0], ["skema_pp55_final", "skema_norma_nppn", "skema_pembukuan"].index(x[1])))
    pph_terpilih, kode_terpilih, label_terpilih = kandidat[0]

    neto_terpilih = neto_pembukuan
    if kode_terpilih == "skema_norma_nppn" and neto_nppn is not None:
        neto_terpilih = neto_nppn
    elif kode_terpilih == "skema_pp55_final":
        neto_terpilih = omzet

    return {
        "objek_komparasi": "penghasilan_sekunder",
        "omzet_sekunder": omzet,
        **skema,
        "rekomendasi_skema": {
            "skema_terpilih": kode_terpilih,
            "label": label_terpilih,
            "estimasi_pph_idr": pph_terpilih,
            "penghematan_pph_idr": round(pph_pembukuan - pph_terpilih, 2),
            "penghematan_dasar_kena_pajak": round(max(0.0, neto_pembukuan - neto_terpilih), 2),
            "alasan": _alasan_rekomendasi(kode_terpilih, neto_pembukuan, neto_nppn, omzet),
        },
    }


def _alasan_rekomendasi(kode: str, neto_pembukuan: float, neto_nppn: Optional[float], omzet: float) -> str:
    if kode == "skema_pp55_final":
        return f"PPh Final 0,5% atas omzet Rp{omzet:,.0f} paling kecil dibanding skema lain."
    if kode == "skema_norma_nppn" and neto_nppn is not None:
        return (
            f"NPPN menghasilkan neto Rp{neto_nppn:,.0f} vs pembukuan Rp{neto_pembukuan:,.0f}, "
            "sehingga PPh Pasal 17 lebih kecil."
        )
    return "Pembukuan menghasilkan beban pajak terkecil di antara skema yang tersedia."


_TARIF_CACHE: Dict[str, float] = {}


def _tarif_persen(engine, katalog_id: str) -> float:
    """Ambil tarif dari ontologi (0% hardcode)."""
    if katalog_id in _TARIF_CACHE:
        return _TARIF_CACHE[katalog_id]
    g = engine.get_ontology_graph()
    q = f"""
    PREFIX kbr: <http://www.semanticweb.org/ontology/kbr_pajak#>
    SELECT ?pct WHERE {{ kbr:{katalog_id} kbr:hasTarifPersen ?pct . }}
    """
    for row in g.query(q):
        _TARIF_CACHE[katalog_id] = float(row.pct)
        return _TARIF_CACHE[katalog_id]
    _TARIF_CACHE[katalog_id] = 0.5 if katalog_id.startswith("Fasilitas_PP55") else 0.0
    return _TARIF_CACHE[katalog_id]


def _rekonsiliasi(engine, req: ReasonRequest, ctx: dict, komparasi: dict, mode: str) -> Optional[dict]:
    if req.wp_kind != "OrangPribadi":
        return None
    neto_utama = ctx["neto_utama_benar"] if mode == "benar" else ctx["neto_utama_prd"]
    neto_sekunder = 0.0
    pph_final_terpisah = 0.0
    if komparasi.get("status") != "TIDAK_RELEVAN":
        pilih = (komparasi.get("rekomendasi_skema") or {}).get("skema_terpilih")
        if pilih == "skema_pp55_final":
            pph_final_terpisah = float((komparasi.get("skema_pp55_final") or {}).get("pph_idr") or 0.0)
            neto_sekunder = 0.0  # final, tidak masuk PKP
        elif pilih == "skema_norma_nppn":
            neto_sekunder = float((komparasi.get("skema_norma_nppn") or {}).get("penghasilan_neto") or 0.0)
        else:
            neto_sekunder = float((komparasi.get("skema_pembukuan") or {}).get("penghasilan_neto") or 0.0)

    total_neto = round(neto_utama + neto_sekunder, 2)
    pkp = max(0.0, total_neto - ctx["ptkp_nominal"])
    pph17, lapisan = engine.progressive_pph17(pkp)
    kredit = float(req.kredit_pajak_1721a1 or 0.0)
    kurang = round(max(0.0, pph17 - kredit), 2)
    lebih = round(max(0.0, kredit - pph17), 2)
    return {
        "mode": "perhitungan_benar" if mode == "benar" else "mode_prd",
        "penghasilan_neto_utama": round(neto_utama, 2),
        "penghasilan_neto_sekunder": round(neto_sekunder, 2),
        "total_penghasilan_neto_gabungan": total_neto,
        "ptkp_status": ctx["ptkp_status"],
        "ptkp_idr": ctx["ptkp_nominal"],
        "penghasilan_kena_pajak_pkp": round(pkp, 2),
        "pph_terutang_pasal_17_idr": pph17,
        "lapisan_pasal_17": lapisan,
        "pph_final_terpisah_idr": pph_final_terpisah,
        "kredit_pajak_1721a1_idr": kredit,
        "jumlah_bukti_potong": req.jumlah_bukti_potong,
        "pph_pasal_29_kurang_bayar_idr": kurang,
        "pph_lebih_bayar_idr": lebih,
    }


# --------------------------------------------------------------------------------------
# Respons PRD §9.3.4
# --------------------------------------------------------------------------------------
_KLASTER = {
    "WPOP_MULTI_STREAM": "WPOP Multi-Stream Income (Pegawai Tetap + Pekerjaan Bebas/Usaha)",
    "WPOP_UMKM": "WPOP UMKM (PPh Final PP 55/2022)",
    "WPOP_PEGAWAI": "WPOP Pegawai Tetap",
    "WPOP_PEKERJA_BEBAS": "WPOP Pekerja Bebas / Tenaga Ahli",
    "WPOP_USAHA": "WPOP Pelaku Usaha",
    "BADAN_UMKM": "Badan Usaha UMKM",
    "BADAN_UMUM": "Badan Usaha Non-UMKM",
    "BUT": "Bentuk Usaha Tetap (BUT)",
}


def _klaster_subjek(req: ReasonRequest, inferred: List[str], ctx: dict) -> dict:
    if req.wp_kind in ("BadanUsahaTetap", "BUT"):
        kode = "BUT"
    elif req.wp_kind != "OrangPribadi":
        kode = "BADAN_UMKM" if "BadanUMKM" in inferred else "BADAN_UMUM"
    else:
        multi = req.pekerjaan_sekunder is not None or len(set(inferred) & {
            "OP_PekerjaBebas", "OP_PelakuUsahaNonProfesi", "OP_PenerimaPPh21_PegawaiTetap",
        }) >= 2
        if multi:
            kode = "WPOP_MULTI_STREAM"
        elif "OP_UMKM_Final_PP55" in inferred or "OP_UMKM_Bebas_500Jt" in inferred:
            kode = "WPOP_UMKM"
        elif "OP_PekerjaBebas" in inferred:
            kode = "WPOP_PEKERJA_BEBAS"
        elif "OP_PelakuUsahaNonProfesi" in inferred:
            kode = "WPOP_USAHA"
        else:
            kode = "WPOP_PEGAWAI"
    return {"kode": kode, "label": _KLASTER[kode]}


_DEADLINE_MAP = {
    "Kewajiban_Tenggat_SPT_Tahunan_OP_3Bln": ("31 Maret {tahun}", "3 bulan setelah akhir Tahun Pajak"),
    "Kewajiban_Tenggat_SPT_Tahunan_Badan_4Bln": ("30 April {tahun}", "4 bulan setelah akhir Tahun Pajak"),
}
_RISIKO_MAP = {
    "Sanksi_Denda_KUP_SPT_OP_100Rb": "SEDANG",
    "Sanksi_Denda_KUP_SPT_Badan_1Jt": "SEDANG",
    "Sanksi_Denda_KUP_SPT_MasaPPN_500Rb": "SEDANG",
    "Sanksi_Bunga_SKPKB_Pasal13_2": "TINGGI",
    "Sanksi_Kenaikan_75Pct_TidakSetor_Pasal13_3": "TINGGI",
    "Sanksi_PPh23_Kenaikan100Pct_NonNPWP": "SEDANG",
    "Sanksi_Keberatan_30Pct": "SEDANG",
    "Sanksi_Banding_60Pct": "SEDANG",
    "Sanksi_NPPN_Norma_Pemeriksaan_Pasal14_5": "SEDANG",
}
_MITIGASI_MAP = {
    "Sanksi_Denda_KUP_SPT_OP_100Rb": "Sampaikan SPT Tahunan OP sebelum 31 Maret; simpan bukti penerimaan elektronik.",
    "Sanksi_Denda_KUP_SPT_Badan_1Jt": "Sampaikan SPT Tahunan Badan sebelum 30 April; kunci e-FIN/portal Coretax.",
    "Sanksi_Denda_KUP_SPT_MasaPPN_500Rb": "Laporkan SPT Masa PPN paling lambat akhir bulan berikutnya.",
    "Sanksi_Bunga_SKPKB_Pasal13_2": "Bayar kurang bayar sebelum diperiksa; ajukan angsuran bila arus kas terbatas.",
    "Sanksi_Kenaikan_75Pct_TidakSetor_Pasal13_3": "Setorkan PPN/PPh potput yang telah dipungut tepat waktu.",
    "Sanksi_PPh23_Kenaikan100Pct_NonNPWP": "Lengkapi NPWP/NIK penerima penghasilan sebelum pemotongan.",
    "Sanksi_Keberatan_30Pct": "Siapkan bukti dan kertas kerja sebelum mengajukan keberatan.",
    "Sanksi_Banding_60Pct": "Evaluasi kekuatan bukti sebelum banding; pertimbangkan CBR preseden.",
    "Sanksi_NPPN_Norma_Pemeriksaan_Pasal14_5": "Selenggarakan pembukuan/pencatatan dan sampaikan pemberitahuan NPPN tepat waktu.",
}


def _tipe_tarif(catalog: Dict[str, dict], cat_id: str) -> str:
    cls = (catalog.get(cat_id) or {}).get("catalog_class", "")
    if cls == "TarifFinal" or cat_id.startswith("Tarif_PPhFinal") or cat_id.startswith("Tarif_PPh26"):
        return "FINAL"
    if cls == "TarifProgresif":
        return "PROGRESIF"
    return "UMUM"


def _formulir_spt(req: ReasonRequest, ctx: dict) -> Tuple[Optional[str], str, Optional[str]]:
    """(formulir, status, catatan). 1770 S/1770 SS belum punya dasar hukum di korpus."""
    if req.wp_kind != "OrangPribadi":
        return "1771", "TERVERIFIKASI", None
    punya_usaha = bool(
        (req.pekerjaan_utama and not _is_employee(req.pekerjaan_utama))
        or req.pekerjaan_sekunder
        or req.penghasilan_final
    )
    if punya_usaha:
        return "1770", "TERVERIFIKASI", None
    return (
        None,
        "PERLU_VERIFIKASI",
        "Formulir 1770 S / 1770 SS memerlukan dasar hukum bentuk SPT Tahunan yang belum tersedia di korpus.",
    )


def build_response(engine, req: ReasonRequest, v1: dict, ctx: dict) -> dict:
    catalog = engine.get_catalog()
    tahun = req.tahun_pajak + 1
    inferred = v1.get("inferred_classes") or []

    tipe_map = {t["id"]: _tipe_tarif(catalog, t["id"]) for t in v1.get("tarif") or []}
    tarif = [
        {
            "id": t["id"],
            "label_resmi": t["label"],
            "tarif_persen": t.get("tarif_persen"),
            "tipe": tipe_map.get(t["id"], "UMUM"),
            "dasar_hukum": t["justifikasi"][0] if t["justifikasi"] else None,
            "justifikasi": t["justifikasi"],
        }
        for t in v1.get("tarif") or []
    ]

    formulir, status_formulir, catatan_formulir = _formulir_spt(req, ctx)
    kewajiban = []
    for k in v1.get("kewajiban") or []:
        tgl, dasar_tenggat = _DEADLINE_MAP.get(k["id"], (None, None))
        kewajiban.append({
            "id": k["id"],
            "nama_kewajiban": k["label"],
            "tenggat_waktu": tgl.format(tahun=tahun) if tgl else None,
            "dasar_tenggat": dasar_tenggat,
            "formulir_spt": formulir if k["id"].startswith("Kewajiban_Tenggat_SPT_Tahunan") else None,
            "status_formulir": status_formulir if k["id"].startswith("Kewajiban_Tenggat_SPT_Tahunan") else None,
            "catatan_formulir": catatan_formulir if k["id"].startswith("Kewajiban_Tenggat_SPT_Tahunan") else None,
            "dasar_hukum": k["justifikasi"][0] if k["justifikasi"] else None,
            "justifikasi": k["justifikasi"],
        })

    sanksi = [
        {
            "id": s["id"],
            "nama_sanksi": s["label"],
            "tingkat_risiko": _RISIKO_MAP.get(s["id"], "SEDANG"),
            "nominal_estimasi_idr": s.get("nominal_idr"),
            "langkah_mitigasi": _MITIGASI_MAP.get(s["id"]),
            "dasar_hukum": s["justifikasi"][0] if s["justifikasi"] else None,
            "justifikasi": s["justifikasi"],
        }
        for s in v1.get("sanksi") or []
    ]

    perda = v1.get("perda_info") or {}
    region = None
    if req.pemda_id:
        try:
            region = next((r for r in engine.list_regions() if r["pemda_id"] == req.pemda_id.upper()), None)
        except FileNotFoundError:
            region = None
    perda_info = None
    if perda or region:
        perda_info = {
            "pemda_id": (perda or {}).get("pemda_id") or (region or {}).get("pemda_id"),
            "nama_daerah": (perda or {}).get("nama_resmi") or (region or {}).get("nama_daerah"),
            "zona_nppn": (region or {}).get("zona_nppn") or (perda or {}).get("nppn_wilayah_kelompok"),
            "tarif_pbb_persen": (region or {}).get("tarif_pbb_persen"),
            "njoptkp": (region or {}).get("njoptkp"),
            "jumlah_perda": (region or {}).get("jumlah_perda"),
            "catatan_pbb": (region or {}).get("catatan_pbb"),
        }

    zona_internal = ctx.get("zona_nppn")
    pp55 = ctx.get("pp55") or _pp55_eligibility(req, ctx["sekunder"])
    komparasi = ctx.get("komparasi") or _komparasi(engine, req, ctx["sekunder"], zona_internal, pp55)
    rekonsiliasi = ctx.get("rekonsiliasi")
    if rekonsiliasi is None and req.wp_kind == "OrangPribadi":
        rekonsiliasi = _rekonsiliasi(engine, req, ctx, komparasi, mode="benar")
    rekonsiliasi_prd = ctx.get("rekonsiliasi_prd")
    if rekonsiliasi_prd is None and req.wp_kind == "OrangPribadi":
        rekonsiliasi_prd = _rekonsiliasi(engine, req, ctx, komparasi, mode="prd")

    rincian = (v1.get("estimasi_pajak") or {}).get("rincian") or {}
    ter_bulanan = None
    if rincian.get("pph21_ter_kategori"):
        per_bulan = rincian.get("pph21_ter_bulanan_idr")
        ter_bulanan = {
            "kategori": str(rincian["pph21_ter_kategori"]).replace("TER_", ""),
            "gaji_bruto": ctx.get("gaji_bruto_bulanan"),
            "tarif_ter_persen": rincian.get("pph21_ter_persen"),
            "potongan_per_bulan": per_bulan,
            "total_potongan_setahun": round(per_bulan * 12, 2) if per_bulan is not None else None,
            "bracket_order": rincian.get("pph21_ter_bracket_order"),
        }

    pekerjaan_info = {
        "multi_stream": req.pekerjaan_sekunder is not None,
        "utama": req.pekerjaan_utama.model_dump() if req.pekerjaan_utama else None,
        "sekunder": req.pekerjaan_sekunder.model_dump() if req.pekerjaan_sekunder else None,
        "neto_utama_idr": round(ctx["neto_utama_benar"], 2),
        "neto_utama_mode_prd_idr": round(ctx["neto_utama_prd"], 2),
        "catatan": (
            "Multi-stream income terdeteksi; perhitungan benar memakai biaya jabatan 5% (maks Rp6 jt/tahun)."
            if req.pekerjaan_sekunder else None
        ),
    }

    provenance: List[dict] = []
    seen = set()
    for kategori, items in (
        ("tarif", tarif), ("fasilitas", v1.get("fasilitas") or []),
        ("kewajiban", kewajiban), ("sanksi", sanksi),
    ):
        for item in items:
            for j in item.get("justifikasi") or []:
                rid = j.get("rule_id")
                if not rid or rid in seen:
                    continue
                seen.add(rid)
                provenance.append({"kategori": kategori, "katalog_id": item.get("id"), **j})

    return {
        "wp_id": req.wp_id,
        "wp_kind": req.wp_kind,
        "tahun_pajak": req.tahun_pajak,
        "klaster_subjek": _klaster_subjek(req, inferred, ctx),
        "inferred_classes": inferred,
        "direct_classes": v1.get("direct_classes") or [],
        "tarif": tarif,
        "fasilitas": v1.get("fasilitas") or [],
        "kewajiban": kewajiban,
        "sanksi": sanksi,
        "perda_info": perda_info,
        "pekerjaan_info": pekerjaan_info,
        "estimasi_pajak": {
            "ter_bulanan": ter_bulanan,
            "komparasi_skema": komparasi,
            "rekonsiliasi_spt_tahunan": rekonsiliasi,
            "rekonsiliasi_mode_prd": rekonsiliasi_prd,
            "pbb_p2_terutang_idr": rincian.get("pbb_terutang_idr"),
            "pbb_status": rincian.get("pbb_status"),
            "pph_final_pasal4_2": {
                k: rincian.get(k) for k in (
                    "pph_final_sewa_tanah_bangunan_idr",
                    "pph_final_bunga_deposito_idr",
                    "pph_final_jasa_konstruksi_idr",
                    "pph_final_pengalihan_tanah_bangunan_idr",
                    "total_pph_final_pasal4_2_idr",
                ) if k in rincian
            },
            "rincian": rincian,
            "catatan": "Estimasi indikatif, bukan pengganti perhitungan SPT resmi.",
        },
        "cbr_matches": [],
        "playbook_coretax": [],
        "provenance": provenance,
        "reasoner": v1.get("reasoner"),
        "elapsed_ms": v1.get("elapsed_ms"),
        "cache_hit": v1.get("cache_hit", False),
    }
