# -*- coding: utf-8 -*-
"""S6 — pendeteksi lubang (gap detector).

Mengumpulkan kutipan peraturan dari semua teks tersimpan (judul, Menimbang,
Mengingat, batang tubuh, penjelasan), menormalkan ke ``document_id`` kanonik,
lalu mencocokkan dengan registry dokumen.

Status kutipan (spec 8.6):
  RESOLVED              dokumen ada di registry
  RESOLVED_EQUIVALENT   digantikan dokumen lain yang ada di registry
                        (mis. UU Cipta Kerja -> UU 6/2023 Penetapan Perpu)
  IGNORED_OUT_OF_SCOPE  jenis/topik di luar fokus pipeline (dengan alasan)
  NOT_FOUND_AT_SOURCE   sudah dicari di BPK, tidak ditemukan
  UNRESOLVED            kandidat untuk putaran crawl berikutnya

Semua keputusan berbasis RULE + daftar eksplisit; tidak ada tebakan diam-diam.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from src.ids import parse_document_ref

# ---------------------------------------------------------------------------
# Pola kutipan
# ---------------------------------------------------------------------------

FULL_RE = re.compile(
    r"(?i)(?P<jenis>"
    r"Peraturan\s+Pemerintah\s+Pengganti\s+Undang[\s-]Undang|"
    r"Peraturan\s+Pemerintah|Peraturan\s+Presiden|Peraturan\s+Menteri\s+Keuangan|"
    r"Peraturan\s+Direktur\s+Jenderal\s+Pajak|Peraturan\s+Dirjen\s+Pajak|"
    r"Keputusan\s+Menteri\s+Keuangan|"
    r"Surat\s+Edaran\s+(?:Direktur\s+Jenderal\s+Pajak|Dirjen\s+Pajak)|"
    r"Undang[\s-]Undang)"
    r"\s+(?:Republik\s+Indonesia\s+)?(?:Nomor|No\.?)\s+"
    r"(?P<nomor>\d{1,4}[A-Za-z]?(?:\s*/\s*[A-Za-z0-9.]+)*)\s+"
    r"Tahun\s+(?P<tahun>\d{4})"
)

# Bentuk kode: PMK-81/PMK.03/2024, PER-14/PJ/2013, SE-29/PJ/2022, KMK-...
# Hindari salah tangkap bagian belakang angka-dulu ("253/PMK03/2008" -> jangan jadi PMK-2008-3).
SHORT_RE = re.compile(
    r"(?i)(?<!\d/)\b(?P<jenis>PERPU|PMK|PER|SE|KMK|PP|UU)"
    r"[\s\-/]*(?P<nomor>\d{1,4}[A-Za-z]?)"
    r"(?:\s*/\s*(?:[A-Z]{2,4}(?:\.?\d{2,4})?))?"
    r"\s*/\s*(?P<tahun>\d{4})\b"
)

# Bentuk angka-dulu: 112/PMK.03/2022, 463/KMK.04/2000, 253/PMK03/2008
NUM_SLASH_RE = re.compile(
    r"(?i)\b(?P<nomor>\d{1,4}[A-Za-z]?)\s*/\s*(?P<kode>PMK|KMK|PJ)"
    r"\s*\.?\s*(?:[A-Z]{2}|\d{2,3})\s*/\s*(?P<tahun>\d{4})\b"
)

JENIS_FROM_PHRASE = {
    "undang-undang": "UU",
    "undang undang": "UU",
    "peraturan pemerintah pengganti undang-undang": "PERPU",
    "peraturan pemerintah pengganti undang undang": "PERPU",
    "peraturan pemerintah": "PP",
    "peraturan presiden": "PERPRES",
    "peraturan menteri keuangan": "PMK",
    "peraturan direktur jenderal pajak": "PER-DJP",
    "peraturan dirjen pajak": "PER-DJP",
    "keputusan menteri keuangan": "KMK",
    "surat edaran direktur jenderal pajak": "SE-DJP",
    "surat edaran dirjen pajak": "SE-DJP",
}

SHORT_JENIS = {"UU": "UU", "PP": "PP", "PERPU": "PERPU", "PMK": "PMK",
               "PER": "PER-DJP", "SE": "SE-DJP", "KMK": "KMK"}

KODE_JENIS = {"PMK": "PMK", "KMK": "KMK", "PJ": "PER-DJP"}

# Jenis yang tidak dijadikan bahan ontology (tetap dilaporkan, bukan diabaikan)
IGNORED_JENIS = {
    "PUTUSAN-MK": "putusan MK bukan teks peraturan (bahan yurisprudensi, di luar pipeline)",
    "KMK": "Keputusan Menteri Keuangan bersifat administratif, di luar fokus korpus",
    "SE-DJP": "Surat Edaran DJP bukan peraturan, di luar fokus korpus",
    "PERPRES": "Peraturan Presiden di luar fokus domain A2/B/C/D",
}

# Kutipan yang sengaja TIDAK diambil: dasar hukum / di luar substansi pajak.
OUT_OF_SCOPE = {
    "UU-2011-12": "UU P3/PPP — dasar hukum pembentukan peraturan, bukan substansi pajak",
    "UU-2003-17": "UU Keuangan Negara — dasar hukum pengelolaan keuangan, bukan substansi pajak",
    "UU-2004-1": "UU Perbendaharaan Negara — dasar hukum, bukan substansi pajak",
    "UU-2002-14": "UU Pengadilan Pajak — sengketa/peradilan di luar task D (administrasi & sanksi)",
    "UU-1950-1": "UU dasar (dasar hukum lama), bukan substansi pajak",
    "UU-1981-8": "KUHAP — hukum acara pidana, bukan substansi pajak",
    "UU-1995-8": "UU Pasar Modal — sektor keuangan, di luar domain",
    "UU-2023-4": "UU P2SK — sektor keuangan, di luar domain",
    "UU-2016-11": "UU Pengampunan Pajak — kebijakan sekali jalan, di luar task",
    "UU-1995-11": "UU Cukai — bea cukai, di luar domain",
    "UU-1995-10": "UU Kepabeanan — di luar domain",
    "UU-1985-13": "UU Bea Meterai — di luar domain",
    "UU-1981-2": "UU Metrologi — bukan pajak",
    "UU-1959-19": "hukum historis (penagihan pajak 1959), sudah tidak berlaku",
    "UU-1967-1": "hukum historis (PMA), sudah dicabut/diganti",
    "UU-1967-5": "hukum historis (PMDN), sudah dicabut/diganti",
    "UU-1967-8": "hukum historis, sudah dicabut/diganti",
    "PP-1967-11": "hukum historis (tata cara pemungutan pajak 1967), bukan rezim terkini",
    "PP-1980-30": "PP Disiplin PNS — bukan pajak",
    "UU-2004-32": "UU Pemerintahan Daerah — bukan substansi pajak",
    "UU-2004-33": "UU Perimbangan Keuangan Pusat-Daerah — teknis transfer, bukan kewajiban pajak",
    "UU-2008-12": "UU Pemerintahan Daerah (perubahan) — bukan substansi pajak",
    "PP-2018-24": "PP OSS — perizinan berusaha, bukan pajak",
    "PP-2023-12": "PP Perizinan Berusaha/OSS — fasilitas pajak diatur terpisah",
    "PP-2024-29": "PP Perizinan Berusaha/OSS (perubahan) — bukan substansi pajak",
    "PP-2016-34": "PP PPh final pengalihan tanah/bangunan — di luar task A2",
    "PP-2016-40": "PP PPh real estat kontrak investasi kolektif — di luar task A2",
    "PP-1994-48": "PP PPh final pengalihan tanah/bangunan — di luar task A2",
    "PP-2008-71": "PP PPh final pengalihan tanah/bangunan — di luar task A2",
    "PMK-2024-65": "PMK Peta Kapasitas Fiskal Daerah — teknis transfer, bukan kewajiban pajak",
    "PMK-2015-70": "PMK PPh migas — di luar domain",
    "PP-2021-86": "PP Pengadaan/Pengelolaan/Penjualan Meterai — Bea Meterai, di luar domain",
    "UU-1999-38": "UU Pengelolaan Zakat — hanya rujukan, bukan substansi pajak",
    "UU-2009-32": "UU Lingkungan Hidup — hanya rujukan, bukan substansi pajak",
    "PP-2021-40": "PP Penyelenggaraan KEK — aspek non-pajak dominan; fasilitas pajak di PMK",
    "UU-2007-25": "UU Penanaman Modal — hukum investasi, bukan substansi pajak",
    "PP-1994-10": "PP Penyertaan Modal Negara — bukan substansi pajak",
    "UU-1992-7": "UU Perbankan — sektor keuangan, rujukan akses data/penagihan",
    "UU-1998-10": "UU Perubahan UU Perbankan — sektor keuangan, bukan substansi pajak",
    "UU-2008-21": "UU Perbankan Syariah — sektor keuangan, bukan substansi pajak",
    "UU-1997-32": "UU Perdagangan Berjangka Komoditi — sektor keuangan/komoditi, bukan pajak",
    "UU-1992-9": "UU Keimigrasian — rujukan pencegahan ke luar negeri di PPSP, bukan pajak",
    "UU-1995-1": "UU Perseroan Terbatas — hukum korporasi, bukan substansi pajak",
    "UU-1996-4": "UU Hak Tanggungan — hukum jaminan perdata, bukan substansi pajak",
    "UU-1997-17": "UU BPSP (sengketa pajak lama, diganti UU 14/2002 Pengadilan Pajak — di luar fokus)",
    "UU-1999-22": "UU Pemerintahan Daerah (historis) — bukan substansi pajak",
    "UU-1999-25": "UU Perimbangan Keuangan (historis) — bukan substansi pajak",
    "UU-2014-23": "UU Pemerintahan Daerah — bukan substansi pajak",
    "UU-2001-21": "UU Otonomi Khusus Papua — tata kelola daerah, bukan pajak inti",
    "UU-2006-11": "UU Pemerintahan Aceh — tata kelola daerah, bukan pajak inti",
    "UU-2003-27": "UU Panas Bumi — sektor energi, bukan pajak",
    "UU-2001-22": "UU Minyak dan Gas Bumi — regulasi sektor migas, bukan tarif/kewajiban pajak",
    "UU-2009-4": "UU Pertambangan Minerba — regulasi sektor pertambangan, bukan pajak",
    "UU-2020-3": "UU Perubahan UU Minerba — regulasi sektor pertambangan, bukan pajak",
    "UU-2025-2": "UU Perubahan Keempat UU Minerba — regulasi sektor pertambangan, bukan pajak",
    "UU-2008-41": "UU APBN Tahun Anggaran 2009 — dasar anggaran, bukan substansi pajak",
    "UU-2008-39": "UU Kementerian Negara — dasar kelembagaan, bukan pajak",
    "UU-1994-7": "UU Pengesahan Agreement Establishing WTO — perjanjian dagang internasional",
    "UU-1985-14": "UU Mahkamah Agung — kelembagaan peradilan umum",
    "UU-1970-14": "UU Pokok-Pokok Kekuasaan Kehakiman (diganti UU Kekuasaan Kehakiman)",
    "UU-1999-35": "UU Perubahan UU Kekuasaan Kehakiman — kelembagaan peradilan",
    "PMK-2021-118": "PMK Organisasi dan Tata Kerja Kementerian Keuangan — kelembagaan internal, bukan pajak",
    "PMK-2024-124": "PMK Organisasi dan Tata Kerja Kementerian Keuangan — kelembagaan internal, bukan pajak",
    "PMK-2025-117": "PMK Perubahan Ortaker Kementerian Keuangan — kelembagaan internal, bukan pajak",
    "PMK-2022-141": "PMK Perubahan Ortaker Kementerian Keuangan — kelembagaan internal, bukan pajak",
    "PMK-2023-135": "PMK Perubahan Kedua Ortaker Kementerian Keuangan — kelembagaan internal, bukan pajak",
    "UU-2023-19": "UU APBN Tahun Anggaran 2024 — dasar anggaran, bukan substansi kewajiban WP",
    "PMK-2023-92": "PMK Mekanisme Pelaksanaan & Pertanggungjawaban APBN atas Pajak DTP — teknis anggaran",
    "UU-1992-11": "UU Dana Pensiun — sektor keuangan non-pajak",
    "PP-2024-49": "PP Peralihan Pengawasan Aset Keuangan Digital — kelembagaan OJK, bukan substansi pajak",
}

# Kutipan yang sudah terwakili dokumen lain di registry.
EQUIVALENT = {
    "UU-2020-11": ("UU-2023-6", "UU Cipta Kerja; teks terbaru = UU 6/2023 (Penetapan Perpu 2/2022)"),
    "PERPU-2022-2": ("UU-2023-6", "Perpu Cipta Kerja ditetapkan menjadi UU 6/2023"),
    "PERPU-2020-1": ("UU-2023-6", "Perppu 1/2020 Cipta Kerja -> UU 11/2020 -> UU 6/2023"),
    "PP-2018-23": ("PP-2022-55", "PP 23/2018 (PPh final UMKM) dicabut PP 55/2022"),
    "PP-2013-46": ("PP-2022-55", "PP 46/2013 (PPh UMKM 1%) dicabut PP 23/2018 -> PP 55/2022"),
    "UU-1997-18": ("UU-2009-28", "UU 18/1997 PDRD dicabut UU 28/2009 (kini UU 1/2022)"),
    "UU-1997-21": ("UU-2009-28", "BPHTB dialihkan ke UU 28/2009 PDRD (kini UU 1/2022)"),
    "UU-2000-20": ("UU-2009-28", "UU 20/2000 mengubah UU 21/1997 BPHTB; rezim diganti UU 28/2009"),
    "UU-2000-34": ("UU-2009-28", "UU 34/2000 mengubah UU 18/1997 PDRD; dicabut UU 28/2009"),
    "UU-1968-2": ("UU-1983-8", "UU 2/1968 pajak penjualan dicabut UU 8/1983 PPN"),
    "PP-2012-1": ("PP-2022-44", "PP 1/2012 dicabut PP 44/2022"),
    "PP-2010-91": ("PP-2016-55", "PP 91/2010 dicabut PP 55/2016 (tata cara pemungutan pajak daerah)"),
    "PP-2007-1": ("PP-2019-78", "PP 1/2007 (fasilitas PPh) dicabut PP 18/2015 -> diganti PP 78/2019"),
    "PP-2008-62": ("PP-2019-78", "PP 62/2008 mengubah PP 1/2007 -> diganti PP 78/2019"),
    "PP-2011-52": ("PP-2019-78", "PP 52/2011 mengubah PP 1/2007 -> diganti PP 78/2019"),
    "PP-2001-12": ("PP-2022-49", "PP 12/2001 (BKP strategis PPN) dicabut PP 81/2015 -> dicabut PP 49/2022"),
    "PP-2007-31": ("PP-2022-49", "PP 31/2007 mengubah PP 12/2001 -> diganti PP 49/2022"),
    "PP-2000-138": ("PP-2010-94", "PP 138/2000 dicabut PP 94/2010 Pasal 34"),
    "UU-1988-7": ("UU-1983-7", "salah ketik/OCR di Penjelasan PP 147/2000 ('UU 7/1988 PPh' = UU 7/1983)"),
    "PP-2011-74": ("PP-2022-50", "PP 74/2011 dicabut PP 50/2022 Pasal 74 huruf a"),
    "PP-2009-19": ("PP-2021-9", "PP 19/2009 (PPh dividen OP) dicabut PP 9/2021 Pasal 10"),
    "UU-2021-11": ("UU-2023-6", "artefak footer halaman pada PP 9/2021 memutus 'UU 11 Tahun ... 2020' (Cipta Kerja)"),
    "PMK-2024-119": ("PMK-2026-28", "PMK 119/2024 (perubahan PMK 39/2018) dicabut PMK 28/2026"),
    "PER-DJP-2008-24": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2009-7": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2009-21": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2009-34": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2009-39": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2009-66": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2010-34": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2010-45": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2013-10": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2013-26": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2014-5": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2014-19": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2015-29": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2015-36": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2017-30": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2019-2": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2019-17": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2021-16": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2021-17": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2021-24": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2022-3": ("PER-DJP-2025-11", "PER-03/PJ/2022 (Faktur Pajak) dicabut PER-11/PJ/2025"),
    "PER-DJP-2022-11": ("PER-DJP-2025-11", "PER-11/PJ/2022 (perubahan PER-03/PJ/2022) dicabut PER-11/PJ/2025"),
    "PER-DJP-2022-14": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2024-2": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2024-5": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PER-DJP-2024-13": ("PER-DJP-2025-11", "dicabut PER-11/PJ/2025 (konsolidasi pelaporan/faktur Coretax)"),
    "PP-2003-38": ("PP-2022-49", "PP 38/2003 dicabut PP 49/2022"),
    "PP-2019-50": ("PP-2022-49", "PP 50/2019 dicabut PP 49/2022"),
    "PP-2027-9": ("PP-2021-9", "OCR di PP 50/2022 Pasal 74b ('Tahun 2027' seharusnya PP 9/2021)"),
    "UU-2009-2A": ("UU-2009-28", "OCR di PP 35/2023 ('Nomor 2A Tahun 2009' seharusnya UU 28/2009)"),
    "PER-DJP-2011-44": ("PMK-2020-130", "ketentuan peralihan tax holiday lama (rezim terkini di PMK 130/2020 jo. PMK 69/2024)"),
    "PER-DJP-2011-45": ("PMK-2020-130", "ketentuan peralihan tax holiday lama (rezim terkini di PMK 130/2020 jo. PMK 69/2024)"),
    "PP-2020-12": ("PP-2021-40", "PP 12/2020 (KEK) dicabut PP 40/2021"),
    "PP-2015-96": ("PP-2021-40", "PP 96/2015 (KEK lama) dicabut PP 12/2020 -> PP 40/2021"),
    "PERPU-2000-1": ("UU-2000-36", "Perppu 1/2000 KPBPB ditetapkan menjadi UU 36/2000"),
    "PMK-2009-96": ("PMK-2023-72", "PMK 96/PMK.03/2009 (penyusutan) dicabut PMK 72/2023"),
    "PP-2000-140": ("PP-2008-51", "PP 140/2000 (jasa konstruksi) dicabut PP 51/2008"),
    "PP-2009-16": ("PP-2021-91", "PP 16/2009 (bunga obligasi) dicabut PP 91/2021"),
    "PP-1996-33": ("PP-2009-32", "PP 33/1996 (TPB) dicabut PP 32/2009"),
    "PP-1997-43": ("PP-2009-32", "PP 43/1997 (perubahan PP 33/1996 TPB) dicabut PP 32/2009"),
    "PP-1996-22": ("PP-2008-28", "PP 22/1996 (sanksi kepabeanan) dicabut PP 28/2008"),
    "PP-1994-42": ("PP-2000-132", "PP 42/1994 (hadiah undian) dicabut PP 132/2000"),
    "UU-1970-3": ("UU-2000-36", "UU 3/1970 dicabut Perppu 1/2000 -> UU 36/2000 KPBPB"),
    "PMK-2014-1": ("PMK-2014-111", "OCR/spasi pada 'Nomor 1 1 1/PMK.03/2014' (Konsultan Pajak)"),
    "PMK-2014-11": ("PMK-2014-111", "OCR pada 'Nomor l 11/PMK.03/2014' (Konsultan Pajak)"),
    "PMK-2017-35": ("PMK-2021-96", "PMK 35/PMK.010/2017 dicabut PMK 96/PMK.03/2021"),
    "PMK-2019-86": ("PMK-2021-96", "PMK 86/PMK.010/2019 dicabut PMK 96/PMK.03/2021"),
    "PMK-2016-104": ("PMK-2020-237", "PMK 104/PMK.010/2016 (KEK) dicabut PMK 237/PMK.010/2020"),
    "PMK-2008-244": ("PMK-2015-141", "PMK 244/PMK.03/2008 (jasa lain PPh 23) dicabut PMK 141/PMK.03/2015"),
    "PMK-2015-122": ("PMK-2016-101", "PMK 122/PMK.010/2015 (PTKP) diganti PMK 101/PMK.010/2016"),
    "PMK-2008-22": ("PMK-2014-111", "PMK 22/PMK.03/2008 (kuasa WP) dicabut/diganti PMK 111/2014 & PMK 81/2024"),
    "PMK-2018-35": ("PMK-2020-130", "rezim tax holiday lama; peralihan diatur PMK 130/PMK.010/2020"),
    "PMK-2011-130": ("PMK-2020-130", "rezim tax holiday lama; peralihan diatur PMK 130/PMK.010/2020"),
    "PMK-2014-192": ("PMK-2020-130", "perubahan PMK 130/2011; peralihan diatur PMK 130/PMK.010/2020"),
    "PMK-2015-159": ("PMK-2020-130", "rezim tax holiday lama; peralihan diatur PMK 130/PMK.010/2020"),
    "PMK-2016-103": ("PMK-2020-130", "perubahan PMK 159/2015; peralihan diatur PMK 130/PMK.010/2020"),
    "PP-2000-145": ("PP-2020-61", "PP 145/2000 (PPnBM lama) dicabut PP 61/2020"),
    "PP-2006-12": ("PP-2020-61", "perubahan PP 145/2000; diganti PP 61/2020"),
    "PP-2006-72": ("PP-2020-61", "perubahan PP 145/2000; diganti PP 61/2020"),
    "PMK-2010-75": ("PMK-2025-11", "PMK 75/2010 (nilai lain DPP PPN) dicabut PMK 2022-71 / diganti PMK 11/2025"),
    "PMK-2015-121": ("PMK-2025-11", "perubahan PMK 75/2010; diganti PMK 11/2025"),
    "PMK-2011-102": ("PMK-2025-11", "PMK 102/2011 (nilai lain film impor) diselaraskan ke PMK 11/2025"),
    "PMK-2021-6": ("PMK-2022-71", "dicabut sebagian oleh PMK 71/PMK.03/2022"),
    "PMK-2020-92": ("PMK-2022-71", "dicabut sebagian oleh PMK 71/PMK.03/2022"),
    "PMK-2021-173": ("PMK-2025-11", "PPN/PPnBM kawasan tertentu disesuaikan PMK 11/2025 & PMK 81/2024"),
    "PMK-2022-62": ("PMK-2025-11", "PPN LPG tertentu disesuaikan PMK 11/2025"),
    "PMK-2022-63": ("PMK-2025-11", "PPN hasil tembakau dicabut PMK 81/2024 & disesuaikan PMK 11/2025"),
    "PMK-2022-64": ("PMK-2025-11", "PPN hasil pertanian tertentu disesuaikan PMK 11/2025"),
    "PMK-2022-65": ("PMK-2025-11", "PPN kendaraan bekas dicabut PMK 81/2024 & disesuaikan PMK 11/2025"),
    "PMK-2022-66": ("PMK-2025-11", "PPN pupuk bersubsidi disesuaikan PMK 11/2025"),
    "PMK-2018-65": ("PMK-2024-81", "PMK tercantum di daftar pencabutan Pasal 483 PMK 81/2024"),
    "PMK-2013-226": ("PMK-2024-81", "PMK tercantum di daftar pencabutan Pasal 483 PMK 81/2024"),
    "PMK-2009-104": ("PMK-2010-2", "PMK 104/PMK.03/2009 (biaya promosi) dicabut PMK 02/PMK.03/2010"),
    "PERPU-2023-2": ("UU-2023-6", "salah ketik tahun pada PMK 118/2024 ('Perpu 2/2023' LN 2022/238 = Perpu 2/2022 -> UU 6/2023)"),
    "UU-2017-9": ("PERPU-2017-1", "UU Penetapan Perppu 1/2017 tentang Akses Informasi Keuangan (AEoI)"),
    "PMK-2016-26": ("PMK-2018-212", "perubahan KMK 51/2001 bunga deposito; dicabut/diganti PMK 212/PMK.03/2018"),
    "PMK-2018-167": ("PMK-2023-66", "PMK 167/PMK.03/2018 (natura daerah terpencil) dicabut PMK 66/2023"),
    "PP-1994-51": ("PP-2000-131", "PP 51/1994 (bunga deposito) dicabut PP 131/2000"),
    "PP-1996-29": ("PP-2017-34", "PP 29/1996 (sewa tanah/bangunan) dicabut PP 34/2017"),
    "PP-2002-5": ("PP-2017-34", "PP 5/2002 mengubah PP 29/1996; dicabut PP 34/2017"),
    "PMK-2023-38": ("PMK-2024-8", "PPN DTP KBLBB TA 2023; rezim TA 2024 dilanjutkan PMK 8/2024"),
    "PMK-2023-116": ("PMK-2024-8", "perubahan PMK 38/2023; rezim TA 2024 dilanjutkan PMK 8/2024"),
}

CONTEXT_SEGMENTS = ("JUDUL", "MENIMBANG", "MENGINGAT", "BATANG_TUBUH", "PENJELASAN")


def _norm_nomor(raw: str) -> Optional[str]:
    """Normalisasi nomor; hilangkan nol di depan ('03'->'3') & perbaiki suffix OCR ('2l'->'21', '4O'->'40')."""
    m = re.match(r"\s*(\d{1,4})([A-Za-z]?)", raw or "")
    if not m:
        return None
    num, suf = str(int(m.group(1))), m.group(2)
    if suf in ("l", "I"):
        suf = "1"
    elif suf == "O":
        suf = "0"
    return num + suf


def _segments_of(doc: dict) -> Iterable[tuple]:
    """Pecah dokumen menjadi segmen ber-konteks untuk ekstraksi kutipan."""
    yield "JUDUL", doc.get("judul") or ""
    pre = doc.get("preamble") or ""
    m = re.search(r"(?i)\bMengingat\b", pre)
    if m:
        yield "MENIMBANG", pre[:m.start()]
        yield "MENGINGAT", pre[m.start():]
    else:
        yield "MENIMBANG", pre
    body = "\n".join(p.get("text") or "" for p in (doc.get("provisions") or []))
    if not body.strip():
        body = "\n".join(a.get("text") or "" for a in (doc.get("articles") or []))
    yield "BATANG_TUBUH", body
    yield "PENJELASAN", doc.get("penjelasan") or ""


def _role_before(text: str, start: int) -> str:
    before = text[max(0, start - 90):start]
    if re.search(r"(?i)(?:telah\s+)?(?:diubah|ditambah|dicabut|diganti|ditetapkan)"
                 r"(?:\s+dan\s+\w+)?\s+dengan\s*$", before):
        return "AMENDMENT"
    if re.search(r"(?i)perubahan\s+(?:pertama|kedua|ketiga|keempat|kelima|keenam|"
                 r"ketujuh|kedelapan|kesembilan|kesepuluh)?\s*atas\s*$", before):
        return "TITLE_AMENDMENT"
    if re.search(r"(?i)\b(?:mencabut|dicabut)\s*$", before):
        return "REPEAL"
    return "REFERENCE"


def _spans_overlap(a: tuple, spans: List[tuple]) -> bool:
    return any(not (a[1] <= s[0] or a[0] >= s[1]) for s in spans)


def extract_citations(doc: dict) -> List[dict]:
    """Ambil semua kutipan peraturan dari satu dokumen kanonik."""
    doc_id = doc.get("document_id") or "?"
    out: List[dict] = []
    seen = set()
    for seg_name, text in _segments_of(doc):
        if not text:
            continue
        full_spans: List[tuple] = []
        for m in FULL_RE.finditer(text):
            jenis_phrase = re.sub(r"\s+", " ", m.group("jenis").lower().strip())
            jenis = JENIS_FROM_PHRASE.get(jenis_phrase)
            nomor = _norm_nomor(m.group("nomor"))
            tahun = int(m.group("tahun"))
            if not jenis or not nomor:
                continue
            cited = f"{jenis}-{tahun}-{nomor}"
            role = _role_before(text, m.start())
            key = (cited, seg_name, role, m.start() // 120)
            if key in seen:
                continue
            seen.add(key)
            full_spans.append((m.start(), m.end()))
            out.append(_record(doc_id, cited, jenis, nomor, tahun, seg_name, role,
                               m.group(0)))
        for regex, jenis_map in ((SHORT_RE, SHORT_JENIS), (NUM_SLASH_RE, KODE_JENIS)):
            for m in regex.finditer(text):
                if _spans_overlap((m.start(), m.end()), full_spans):
                    continue
                jenis = jenis_map.get(m.group("jenis") if "jenis" in m.groupdict()
                                      else m.group("kode"))
                nomor = _norm_nomor(m.group("nomor"))
                tahun = int(m.group("tahun"))
                if not jenis or not nomor:
                    continue
                cited = f"{jenis}-{tahun}-{nomor}"
                role = _role_before(text, m.start())
                key = (cited, seg_name, role, m.start() // 120)
                if key in seen:
                    continue
                seen.add(key)
                out.append(_record(doc_id, cited, jenis, nomor, tahun, seg_name,
                                   role, m.group(0)))
    return out


def _record(doc_id, cited, jenis, nomor, tahun, seg, role, raw) -> dict:
    cid = hashlib.sha1(f"{doc_id}|{cited}|{seg}|{role}|{raw}".encode()).hexdigest()[:12]
    return {
        "citation_id": cid,
        "in_document_id": doc_id,
        "context_type": seg,
        "citation_role": role,
        "raw_text": raw[:200],
        "parsed_jenis": jenis,
        "parsed_nomor": nomor,
        "parsed_tahun": tahun,
        "resolved_document_id": cited,
        "status": None,
        "reason": None,
    }


def revocations_from_corpus(docs: List[dict]) -> Dict[str, tuple]:
    """Deteksi otomatis peraturan yang dicabut di pasal penutup korpus."""
    rev: Dict[str, tuple] = {}
    for d in docs:
        did = d.get("document_id")
        if not did or d.get("jenis") in ("MANUAL", "LAMPIRAN"):
            continue
        pasals = [p for p in d.get("provisions", []) if p.get("level") == "PASAL"]
        if not pasals and d.get("articles"):
            pasals = d["articles"]
        for p in pasals:
            txt = p.get("text") or ""
            low = txt.lower()
            if "dicabut dan dinyatakan tidak berlaku" not in low:
                continue
            if "pada saat" not in low[:450] and "mulai berlaku" not in low[:450]:
                continue
            head_part = txt[:low.rfind("dicabut") + 60]
            pno = p.get("nomor", "?")
            for regex, jmap in (
                (FULL_RE, JENIS_FROM_PHRASE),
                (SHORT_RE, SHORT_JENIS),
                (NUM_SLASH_RE, KODE_JENIS),
            ):
                for m in regex.finditer(head_part):
                    if "jenis" in m.groupdict():
                        raw_j = re.sub(r"\s+", " ", m.group("jenis").lower().strip())
                        jenis = jmap.get(raw_j) or jmap.get(raw_j.upper())
                    else:
                        jenis = jmap.get(m.group("kode").upper())
                    nomor = _norm_nomor(m.group("nomor"))
                    tahun = int(m.group("tahun"))
                    if not jenis or not nomor:
                        continue
                    target = f"{jenis}-{tahun}-{nomor}"
                    if target != did and target not in rev:
                        rev[target] = (did, f"dicabut eksplisit oleh {did} Pasal {pno}")
    return rev


def aggregate(citations: List[dict], registry: Dict[str, dict],
              attempts: Optional[Dict[str, dict]] = None,
              revocations: Optional[Dict[str, tuple]] = None) -> Dict[str, dict]:
    """Gabungkan kutipan per dokumen yang dikutip + tentukan status."""
    attempts = attempts or {}
    revocations = revocations or {}
    agg: Dict[str, dict] = {}
    for c in citations:
        did = c["resolved_document_id"]
        a = agg.setdefault(did, {
            "document_id": did,
            "jenis": c["parsed_jenis"],
            "tahun": c["parsed_tahun"],
            "nomor": c["parsed_nomor"],
            "occurrences": 0,
            "cited_by": set(),
            "contexts": set(),
            "roles": set(),
            "status": None,
            "reason": None,
        })
        a["occurrences"] += 1
        a["cited_by"].add(c["in_document_id"])
        a["contexts"].add(c["context_type"])
        a["roles"].add(c["citation_role"])

    for did, a in agg.items():
        if did in registry:
            a["status"] = "RESOLVED"
        elif did in EQUIVALENT:
            target, why = EQUIVALENT[did]
            a["status"] = "RESOLVED_EQUIVALENT"
            a["equivalent_document_id"] = target
            a["reason"] = why
        elif did in revocations:
            target, why = revocations[did]
            a["status"] = "RESOLVED_EQUIVALENT"
            a["equivalent_document_id"] = target
            a["reason"] = why
        elif did in OUT_OF_SCOPE:
            a["status"] = "IGNORED_OUT_OF_SCOPE"
            a["reason"] = OUT_OF_SCOPE[did]
        elif a["jenis"] in IGNORED_JENIS:
            a["status"] = "IGNORED_OUT_OF_SCOPE"
            a["reason"] = IGNORED_JENIS[a["jenis"]]
        elif a["cited_by"] == {"UU-2023-6"}:
            a["status"] = "DEFERRED_CK"
            a["reason"] = ("hanya dikutip oleh UU 6/2023 (omnibus Cipta Kerja); "
                           "lapisan CK ditunda")
        else:
            a["status"] = "UNRESOLVED"

        # Percobaan crawl yang gagal: ubah status terminal + simpan jejak.
        if a["status"] == "UNRESOLVED" and did in attempts:
            a["status"] = "NOT_FOUND_AT_SOURCE"
            a["reason"] = attempts[did].get("reason", "tidak ditemukan di sumber")
            a["attempts"] = attempts[did].get("attempts", [])

        a["cited_by"] = sorted(a["cited_by"])
        a["contexts"] = sorted(a["contexts"])
        a["roles"] = sorted(a["roles"])
        a["citation_count"] = len(a["cited_by"])
    return agg


def priority(a: dict) -> tuple:
    """Skor prioritas crawl: makin sering & makin banyak dokumen mengutip."""
    jenis_boost = {"UU": 3, "PERPU": 3, "PP": 2, "PMK": 2, "PER-DJP": 1}.get(a["jenis"], 0)
    return (a["citation_count"] * 2 + a["occurrences"] + jenis_boost, a["document_id"])


def load_registry(docs_dir: Path) -> Dict[str, dict]:
    reg = {}
    for f in sorted(docs_dir.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        did = d.get("document_id")
        if did:
            reg[did] = {"judul": d.get("judul") or "", "jenis": d.get("jenis")}
    return reg


def collect(docs: List[dict], registry: Dict[str, dict],
            attempts: Optional[Dict[str, dict]] = None) -> tuple:
    citations: List[dict] = []
    for d in docs:
        if d.get("jenis") in ("MANUAL", "LAMPIRAN"):
            continue
        did = d.get("document_id")
        for c in extract_citations(d):
            if c["resolved_document_id"] != did:  # abaikan kutipan diri sendiri (judul/menimbang)
                citations.append(c)
    revs = revocations_from_corpus(docs)
    agg = aggregate(citations, registry, attempts, revs)
    for c in citations:
        a = agg[c["resolved_document_id"]]
        c["status"] = a["status"]
        c["reason"] = a.get("reason")
    return citations, agg


# ---------------------------------------------------------------------------
# Relasi dari judul ("Perubahan atas X") — origin=TEXT_PATTERN
# ---------------------------------------------------------------------------

TITLE_AMEND_RE = re.compile(r"(?i)perubahan\s+(?:pertama|kedua|ketiga|keempat|kelima|"
                            r"keenam|ketujuh|kedelapan|kesembilan|kesepuluh)?\s*atas\s+(.+)")


def relations_from_titles(docs: List[dict], registry: Dict[str, dict]) -> List[dict]:
    rels = []
    for d in docs:
        judul = d.get("judul") or ""
        m = TITLE_AMEND_RE.search(judul)
        if not m:
            continue
        ref = parse_document_ref(m.group(1)[:160])
        if not ref:
            continue
        target = ref["document_id"]
        if target == d.get("document_id"):
            continue
        rels.append({
            "from": d.get("document_id"),
            "to": target,
            "type": "MENGUBAH",
            "origin": "TEXT_PATTERN",
            "target_in_registry": target in registry,
            "source_quote": judul[:180],
        })
    return rels


def write_outputs(citations: List[dict], agg: Dict[str, dict], rels: List[dict],
                  out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "citations.jsonl").open("w", encoding="utf-8") as f:
        for c in citations:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    gaps = {
        "summary": _summary(agg),
        "documents": sorted(agg.values(), key=lambda a: (
            {"UNRESOLVED": 0, "NOT_FOUND_AT_SOURCE": 1, "DEFERRED_CK": 2,
             "IGNORED_OUT_OF_SCOPE": 3, "RESOLVED_EQUIVALENT": 4,
             "RESOLVED": 5}.get(a["status"], 9),
            -a["citation_count"], a["document_id"])),
        "relations": rels,
    }
    (out_dir / "gaps.json").write_text(
        json.dumps(gaps, ensure_ascii=False, indent=2), encoding="utf-8")
    unresolved = [a for a in agg.values() if a["status"] == "UNRESOLVED"]
    (out_dir / "unresolved_citations.json").write_text(
        json.dumps(sorted(unresolved, key=priority, reverse=True),
                   ensure_ascii=False, indent=2), encoding="utf-8")


def _summary(agg: Dict[str, dict]) -> dict:
    s = {"total_cited_documents": len(agg), "total_citations": 0, "by_status": {}}
    for a in agg.values():
        s["total_citations"] += a["occurrences"]
        s["by_status"][a["status"]] = s["by_status"].get(a["status"], 0) + 1
    return s
