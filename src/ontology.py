# -*- coding: utf-8 -*-
"""Fase 5 & 6 — Builder Ontologi KBR Pajak SROIQ(D) + SWRL + ABox + Reasoning HermiT + SPARQL.

Menghasilkan:
- ontology/kbr_pajak_tbox.owl & .ttl   (TBox SROIQ(D) + aturan SWRL DL-safe)
- ontology/kbr_pajak_reasoning.owl     (TBox + SWRL + ~200 individu inti + skenario uji TK-*)
- ontology/rule_map.json               (pemetaan konsep reasoning -> rule_id & pasal sumber)
- data/export/kbr_pajak_full.ttl       (ekspor RDF penuh seluruh 12.907 aturan legal_rules.jsonl)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import owlready2
from owlready2 import (
    AllDisjoint,
    AsymmetricProperty,
    DataProperty,
    FunctionalProperty,
    Imp,
    IrreflexiveProperty,
    Not,
    ObjectProperty,
    OneOf,
    Or,
    PropertyChain,
    Thing,
    ThingClass,
    TransitiveProperty,
    World,
    destroy_entity,
    sync_reasoner_hermit,
)
from owlready2.class_construct import ConstrainedDatatype
from rdflib import Graph, Literal, Namespace, RDF, RDFS, XSD

BASE_IRI = "http://www.semanticweb.org/ontology/kbr_pajak#"
ONTO_IRI = "http://www.semanticweb.org/ontology/kbr_pajak"

# Daftar aturan inti dari legal_rules.jsonl yang langsung menopang katalog Tarif/Fasilitas/Sanksi/Kewajiban
CORE_RULE_SPECS = [
    # (catalog_type, catalog_id, label, tarif_pct_or_val, rule_id, fallback_doc, fallback_loc)
    ("TarifPajak", "Tarif_PPhBadan_22Pct", "Tarif PPh Badan Umum 22% (Pasal 17 ayat (1) huruf b UU PPh)", 22.0, "R-UU-1983-7-fcd99f0036", "UU-1983-7", "UU-1983-7#BT/17/1..3"),
    ("TarifPajak", "Tarif_PPhBadan_Tbk_19Pct", "Tarif PPh Badan Perseroan Terbuka 19% (diskon 3%, >=40% publik, >=300 pihak, >=183 hari, Pasal 17 ayat (2b) UU PPh)", 19.0, "R-UU-1983-7-795d9e9140", "UU-1983-7", "UU-1983-7#BT/17/1..3"),
    ("TarifFinal", "Tarif_PPh26_4_BUT_BranchProfit_20Pct", "Tarif PPh Pasal 26 ayat (4) Branch Profit Tax 20% atas Laba Setelah Pajak BUT (UU PPh Pasal 26(4))", 20.0, "R-UU-1983-7-fc3e7c4953", "UU-1983-7", "UU-1983-7#BT/26/3..5"),
    ("TarifFinal", "Tarif_PPhFinal_SewaTanahBangunan_10Pct", "Tarif PPh Final 10% atas Persewaan Tanah dan/atau Bangunan (PP 34/2017 Pasal 4(1))", 10.0, "R-PP-2017-34-a11ca8c4a6", "PP-2017-34", "PP-2017-34#BT/4"),
    ("TarifFinal", "Tarif_PPhFinal_BungaDepositoTabungan_20Pct", "Tarif PPh Final 20% atas Bunga Tabungan, Diskonto SBI, dan Deposito Umum Non-DHE (PP 131/2000 jo. PP 123/2015 Pasal 2 huruf c)", 20.0, "R-PP-2000-131-fc05ed2fb9", "PP-2000-131", "PP-2000-131#BT/2"),
    ("TarifFinal", "Tarif_PPhFinal_DepositoDHE_USD_Bertingkat", "Tarif PPh Final Deposito DHE USD (10% 1 bln, 7,5% 3 bln, 2,5% 6 bln, 0% >6 bln; PP 131/2000 jo. PP 123/2015 Pasal 2 huruf a)", None, "R-PP-2000-131-c9221e0b78", "PP-2000-131", "PP-2000-131#BT/2"),
    ("TarifFinal", "Tarif_PPhFinal_Konstruksi_KecilSBU_1_75Pct", "Tarif PPh Final Jasa Konstruksi 1,75% Pekerjaan Konstruksi Kualifikasi Kecil / SKK Perseorangan (PP 51/2008 jo. PP 9/2022 Pasal 3(1)a)", 1.75, "R-PP-2008-51-bd43270f8a", "PP-2008-51", "PP-2008-51#BT/3"),
    ("TarifFinal", "Tarif_PPhFinal_Konstruksi_NonKecilSBU_2_65Pct", "Tarif PPh Final Jasa Konstruksi 2,65% Pekerjaan Konstruksi Menengah/Besar Bersertifikat (PP 51/2008 jo. PP 9/2022 Pasal 3(1)c)", 2.65, "R-PP-2008-51-77cd2d02ee", "PP-2008-51", "PP-2008-51#BT/3"),
    ("TarifFinal", "Tarif_PPhFinal_Konstruksi_TerintegrasiSBU_2_65Pct", "Tarif PPh Final Jasa Konstruksi 2,65% Pekerjaan Konstruksi Terintegrasi Bersertifikat SBU (PP 51/2008 jo. PP 9/2022 Pasal 3(1)d)", 2.65, "R-PP-2008-51-59116f2a02", "PP-2008-51", "PP-2008-51#BT/3"),
    ("TarifFinal", "Tarif_PPhFinal_Konstruksi_TanpaSBU_4Pct", "Tarif PPh Final Jasa Konstruksi 4% Pekerjaan Konstruksi Tanpa Sertifikat SBU/SKK (PP 51/2008 jo. PP 9/2022 Pasal 3(1)b)", 4.0, "R-PP-2008-51-fc527468d8", "PP-2008-51", "PP-2008-51#BT/3"),
    ("TarifFinal", "Tarif_PPhFinal_Konstruksi_TerintegrasiTanpaSBU_4Pct", "Tarif PPh Final Jasa Konstruksi 4% Pekerjaan Konstruksi Terintegrasi Tanpa SBU (PP 51/2008 jo. PP 9/2022 Pasal 3(1)e)", 4.0, "R-PP-2008-51-fe99b15648", "PP-2008-51", "PP-2008-51#BT/3"),
    ("TarifFinal", "Tarif_PPhFinal_Konstruksi_KonsultansiSBU_3_5Pct", "Tarif PPh Final Jasa Konstruksi 3,5% Jasa Konsultansi Konstruksi Bersertifikat SBU/SKK (PP 51/2008 jo. PP 9/2022 Pasal 3(1)f)", 3.5, "R-PP-2008-51-ee380105e4", "PP-2008-51", "PP-2008-51#BT/3"),
    ("TarifFinal", "Tarif_PPhFinal_Konstruksi_KonsultansiTanpaSBU_6Pct", "Tarif PPh Final Jasa Konstruksi 6% Jasa Konsultansi Konstruksi Tanpa Sertifikat SBU/SKK (PP 51/2008 jo. PP 9/2022 Pasal 3(1)g)", 6.0, "R-PP-2008-51-631d959451", "PP-2008-51", "PP-2008-51#BT/3"),
    ("TarifFinal", "Tarif_PPhFinal_PengalihanTanahBangunan_2_5Pct", "Tarif PPh Final 2,5% atas Pengalihan Hak atas Tanah dan/atau Bangunan Umum (PP 34/2016 Pasal 2(1)a)", 2.5, "R-PP-2016-34-7c066787f5", "PP-2016-34", "PP-2016-34#BT/2/1"),
    ("TarifFinal", "Tarif_PPhFinal_PengalihanRumahSederhana_1Pct", "Tarif PPh Final 1% Pengalihan Rumah Sederhana/Rusunami oleh Developer Usaha Pokok Properti (PP 34/2016 Pasal 2(1)b)", 1.0, "R-PP-2016-34-9fdb5292bd", "PP-2016-34", "PP-2016-34#BT/2/1"),
    ("TarifFinal", "Tarif_PPhFinal_PengalihanKepadaPemerintah_0Pct", "Tarif PPh Final 0% Pengalihan Tanah/Bangunan kepada Pemerintah atau BUMN/BUMD Penugasan Khusus (PP 34/2016 Pasal 2(1)c)", 0.0, "R-PP-2016-34-2c3484ea65", "PP-2016-34", "PP-2016-34#BT/2/1"),
    ("TarifPajak", "Tarif_PPh23_JasaSewa_2Pct", "Tarif Pemotongan PPh Pasal 23 sebesar 2% atas Sewa Harta Selain Tanah/Bangunan & Jasa Lain (UU PPh Pasal 23(1)c)", 2.0, "R-UU-1983-7-1afe13bff6", "UU-1983-7", "UU-1983-7#BT/23/1..4"),
    ("TarifPajak", "Tarif_PPh23_Modal_15Pct", "Tarif Pemotongan PPh Pasal 23 sebesar 15% atas Dividen, Bunga, Royalti & Hadiah (UU PPh Pasal 23(1)a)", 15.0, "R-UU-1983-7-ab2ba6ed43", "UU-1983-7", "UU-1983-7#BT/23/1..4"),
    ("TarifProgresif", "Tarif_PPhOP_Layer1_5Pct", "Tarif PPh Orang Pribadi Lapisan 1: 5% s.d. PKP Rp60 Juta (UU HPP Pasal 17(1)a)", 5.0, "R-UU-1983-7-8cffee614e", "UU-1983-7", "UU-1983-7#BT/17/1..3"),
    ("TarifProgresif", "Tarif_PPhOP_Layer2_15Pct", "Tarif PPh Orang Pribadi Lapisan 2: 15% > Rp60 Juta s.d. Rp250 Juta (UU HPP Pasal 17(1)a)", 15.0, "R-UU-1983-7-ec277b63c2", "UU-1983-7", "UU-1983-7#BT/17/1..3"),
    ("TarifProgresif", "Tarif_PPhOP_Layer3_25Pct", "Tarif PPh Orang Pribadi Lapisan 3: 25% > Rp250 Juta s.d. Rp500 Juta (UU HPP Pasal 17(1)a)", 25.0, "R-UU-1983-7-803278852d", "UU-1983-7", "UU-1983-7#BT/17/1..3"),
    ("TarifProgresif", "Tarif_PPhOP_Layer4_30Pct", "Tarif PPh Orang Pribadi Lapisan 4: 30% > Rp500 Juta s.d. Rp5 Miliar (UU HPP Pasal 17(1)a)", 30.0, "R-UU-1983-7-e6d7634cf6", "UU-1983-7", "UU-1983-7#BT/17/1..3"),
    ("TarifProgresif", "Tarif_PPhOP_Layer5_35Pct", "Tarif PPh Orang Pribadi Lapisan 5: 35% > Rp5 Miliar (UU HPP Pasal 17(1)a)", 35.0, "R-UU-1983-7-ae85d34163", "UU-1983-7", "UU-1983-7#BT/17/1..3"),
    ("TarifPajak", "Tarif_PPh21_TER_Bulanan_Kategori_A", "Tarif Efektif Bulanan PPh 21 Kategori A (TK/0, TK/1, K/0) Jan-Nov + Rekonsiliasi Pasal 17 Des (PP 58/2023 Pasal 2(4)a)", None, "R-PP-2023-58-1986e73145", "PP-2023-58", "PP-2023-58#BT/2/1..5"),
    ("TarifPajak", "Tarif_PPh21_TER_Bulanan_Kategori_B", "Tarif Efektif Bulanan PPh 21 Kategori B (TK/2, TK/3, K/1, K/2) Jan-Nov + Rekonsiliasi Pasal 17 Des (PP 58/2023 Pasal 2(4)b)", None, "R-PP-2023-58-1986e73145", "PP-2023-58", "PP-2023-58#BT/2/1..5"),
    ("TarifPajak", "Tarif_PPh21_TER_Bulanan_Kategori_C", "Tarif Efektif Bulanan PPh 21 Kategori C (K/3) Jan-Nov + Rekonsiliasi Pasal 17 Des (PP 58/2023 Pasal 2(4)c)", None, "R-PP-2023-58-1986e73145", "PP-2023-58", "PP-2023-58#BT/2/1..5"),
    ("TarifPajak", "Tarif_PPh21_PegawaiTidakTetap_Harian", "Pemotongan PPh 21 Pegawai Tidak Tetap/Harian (TER Harian s.d. Rp2,5jt/hari atau 50% bruto > Rp2,5jt/hari, PMK 168/2023 Pasal 12)", None, "R-PMK-2023-168-1e176ea4e4", "PMK-2023-168", "PMK-2023-168#BT/12/2..3"),
    ("TarifPajak", "Tarif_PPh21_BukanPegawai_DPP50Pct", "Pemotongan PPh 21 Bukan Pegawai / Pekerja Bebas: DPP 50% x Penghasilan Bruto x Tarif Pasal 17(1)a (PMK 168/2023 Pasal 12)", None, "R-PMK-2023-168-2db4c48fb5", "PMK-2023-168", "PMK-2023-168#BT/12/2..3"),
    ("TarifFinal", "Tarif_PPh26_OP_LuarNegeri_20Pct", "Tarif Pemotongan PPh Pasal 26 Final 20% bagi OP Subjek Pajak Luar Negeri (kecuali P3B, PMK 168/2023 Pasal 14)", 20.0, "R-PMK-2023-168-da9f28546f", "PMK-2023-168", "PMK-2023-168#BT/14"),
    ("TarifPajak", "Tarif_PPN_12Pct", "Tarif PPN 12% (PMK-2024-131 Pasal 2 & UU HPP)", 12.0, "R-PMK-2024-131-43f37b0b3b", "PMK-2024-131", "PMK-2024-131#BT/2"),
    ("TarifPajak", "Tarif_PPN_Efektif_11Pct", "Tarif PPN Efektif 11% (12% x DPP 11/12 Nilai Lain, PMK-2024-131 Pasal 3)", 11.0, "R-PMK-2024-131-2315c9737b", "PMK-2024-131", "PMK-2024-131#BT/3"),
    ("TarifProgresif", "Tarif_PKB_DKI_Ke1_2Pct", "Tarif PKB Progresif Kendaraan ke-1 DKI Jakarta 2% (Perda DKI 1/2024 Pasal 7(1)a)", 2.0, "R-PERDA-PROV-DKI-JAKARTA-2024-1-c608641ee1", "PERDA-PROV-DKI-JAKARTA-2024-1", "PERDA-PROV-DKI-JAKARTA-2024-1#BT/7"),
    ("TarifProgresif", "Tarif_PKB_DKI_Ke2_3Pct", "Tarif PKB Progresif Kendaraan ke-2 DKI Jakarta 3% (Perda DKI 1/2024 Pasal 7(1)b)", 3.0, "R-PERDA-PROV-DKI-JAKARTA-2024-1-2227d61ab1", "PERDA-PROV-DKI-JAKARTA-2024-1", "PERDA-PROV-DKI-JAKARTA-2024-1#BT/7"),
    ("TarifProgresif", "Tarif_PKB_DKI_Ke3_4Pct", "Tarif PKB Progresif Kendaraan ke-3 DKI Jakarta 4% (Perda DKI 1/2024 Pasal 7(1)c)", 4.0, "R-PERDA-PROV-DKI-JAKARTA-2024-1-4c659d6976", "PERDA-PROV-DKI-JAKARTA-2024-1", "PERDA-PROV-DKI-JAKARTA-2024-1#BT/7"),
    ("TarifProgresif", "Tarif_PKB_DKI_Ke4_5Pct", "Tarif PKB Progresif Kendaraan ke-4 DKI Jakarta 5% (Perda DKI 1/2024 Pasal 7(1)d)", 5.0, "R-PERDA-PROV-DKI-JAKARTA-2024-1-45be6103f6", "PERDA-PROV-DKI-JAKARTA-2024-1", "PERDA-PROV-DKI-JAKARTA-2024-1#BT/7"),
    ("TarifProgresif", "Tarif_PKB_DKI_Ke5Plus_6Pct", "Tarif PKB Progresif Kendaraan ke-5+ DKI Jakarta 6% (Perda DKI 1/2024 Pasal 7(1)e)", 6.0, "R-PERDA-PROV-DKI-JAKARTA-2024-1-3c423034aa", "PERDA-PROV-DKI-JAKARTA-2024-1", "PERDA-PROV-DKI-JAKARTA-2024-1#BT/7"),
    ("TarifPajak", "Tarif_PBB_DKI_0_5Pct", "Tarif PBB-P2 Umum DKI Jakarta 0,5% (Perda DKI 1/2024 Pasal 34(1))", 0.5, "R-PERDA-PROV-DKI-JAKARTA-2024-1-a04b748190", "PERDA-PROV-DKI-JAKARTA-2024-1", "PERDA-PROV-DKI-JAKARTA-2024-1#BT/34"),
    ("TarifPajak", "Tarif_PKB_DKI_Badan_2Pct", "Tarif PKB Kepemilikan Badan di DKI Jakarta Flat 2% Non-Progresif (Perda DKI 1/2024 Pasal 7)", 2.0, "R-PERDA-PROV-DKI-JAKARTA-2024-1-e6317eaef8", "PERDA-PROV-DKI-JAKARTA-2024-1", "PERDA-PROV-DKI-JAKARTA-2024-1#BT/7"),
    ("TarifProgresif", "Tarif_PKB_Jabar_Ke1_1_12Pct", "Tarif PKB Kendaraan ke-1 Jawa Barat 1,12% + Opsen PKB Kab/Kota (Perda Jabar 9/2023 Pasal 7)", 1.12, "R-PERDA-PROV-JAWA-BARAT-2023-9-4a130f377e", "PERDA-PROV-JAWA-BARAT-2023-9", "PERDA-PROV-JAWA-BARAT-2023-9#BT/7"),
    ("TarifProgresif", "Tarif_PKB_Jabar_Ke2_1_62Pct", "Tarif PKB Progresif Kendaraan ke-2 Jawa Barat 1,62% + Opsen PKB (Perda Jabar 9/2023 Pasal 7)", 1.62, "R-PERDA-PROV-JAWA-BARAT-2023-9-7a43c53d18", "PERDA-PROV-JAWA-BARAT-2023-9", "PERDA-PROV-JAWA-BARAT-2023-9#BT/7"),
    ("TarifProgresif", "Tarif_PKB_Jabar_Ke3_2_12Pct", "Tarif PKB Progresif Kendaraan ke-3 Jawa Barat 2,12% + Opsen PKB (Perda Jabar 9/2023 Pasal 7)", 2.12, "R-PERDA-PROV-JAWA-BARAT-2023-9-3d735ac8b6", "PERDA-PROV-JAWA-BARAT-2023-9", "PERDA-PROV-JAWA-BARAT-2023-9#BT/7"),
    ("TarifProgresif", "Tarif_PKB_Jabar_Ke4_2_62Pct", "Tarif PKB Progresif Kendaraan ke-4 Jawa Barat 2,62% + Opsen PKB (Perda Jabar 9/2023 Pasal 7)", 2.62, "R-PERDA-PROV-JAWA-BARAT-2023-9-d172166c99", "PERDA-PROV-JAWA-BARAT-2023-9", "PERDA-PROV-JAWA-BARAT-2023-9#BT/7"),
    ("TarifProgresif", "Tarif_PKB_Jabar_Ke5Plus_3_12Pct", "Tarif PKB Progresif Kendaraan ke-5+ Jawa Barat 3,12% + Opsen PKB (Perda Jabar 9/2023 Pasal 7)", 3.12, "R-PERDA-PROV-JAWA-BARAT-2023-9-ab7af0b378", "PERDA-PROV-JAWA-BARAT-2023-9", "PERDA-PROV-JAWA-BARAT-2023-9#BT/7"),
    ("TarifPajak", "Tarif_PKB_Jabar_Badan_NonProgresif", "PKB Kendaraan Badan di Jawa Barat Tidak Dikenakan Tarif Progresif (Perda Jabar 9/2023 Pasal 7)", None, "R-PERDA-PROV-JAWA-BARAT-2023-9-76647784d3", "PERDA-PROV-JAWA-BARAT-2023-9", "PERDA-PROV-JAWA-BARAT-2023-9#BT/7"),
    ("TarifProgresif", "Tarif_PBB_Surabaya_L1_0_05Pct", "Tarif PBB-P2 Surabaya 0,05% (NJOP Rp100jt s.d. Rp200jt, Perda Surabaya 7/2023 Pasal 8a)", 0.05, "R-PERDA-KOTA-SURABAYA-2023-7-d8a9126d1b", "PERDA-KOTA-SURABAYA-2023-7", "PERDA-KOTA-SURABAYA-2023-7#BT/8"),
    ("TarifProgresif", "Tarif_PBB_Surabaya_L2_0_10Pct", "Tarif PBB-P2 Surabaya 0,10% (NJOP > Rp200jt s.d. Rp1M, Perda Surabaya 7/2023 Pasal 8b)", 0.10, "R-PERDA-KOTA-SURABAYA-2023-7-54a0fbef6d", "PERDA-KOTA-SURABAYA-2023-7", "PERDA-KOTA-SURABAYA-2023-7#BT/8"),
    ("TarifProgresif", "Tarif_PBB_Surabaya_L3_0_15Pct", "Tarif PBB-P2 Surabaya 0,15% (NJOP > Rp1M s.d. Rp2M, Perda Surabaya 7/2023 Pasal 8c)", 0.15, "R-PERDA-KOTA-SURABAYA-2023-7-907231590b", "PERDA-KOTA-SURABAYA-2023-7", "PERDA-KOTA-SURABAYA-2023-7#BT/8"),
    ("TarifProgresif", "Tarif_PBB_Surabaya_L4_0_20Pct", "Tarif PBB-P2 Surabaya 0,20% (NJOP > Rp2M s.d. Rp10M, Perda Surabaya 7/2023 Pasal 8d)", 0.20, "R-PERDA-KOTA-SURABAYA-2023-7-e8674344f9", "PERDA-KOTA-SURABAYA-2023-7", "PERDA-KOTA-SURABAYA-2023-7#BT/8"),
    ("TarifProgresif", "Tarif_PBB_Surabaya_L5_0_25Pct", "Tarif PBB-P2 Surabaya 0,25% (NJOP > Rp10M s.d. Rp50M, Perda Surabaya 7/2023 Pasal 8e)", 0.25, "R-PERDA-KOTA-SURABAYA-2023-7-67c5517889", "PERDA-KOTA-SURABAYA-2023-7", "PERDA-KOTA-SURABAYA-2023-7#BT/8"),
    ("TarifProgresif", "Tarif_PBB_Surabaya_L6_0_30Pct", "Tarif PBB-P2 Surabaya 0,30% (NJOP > Rp50M, Perda Surabaya 7/2023 Pasal 8f)", 0.30, "R-PERDA-KOTA-SURABAYA-2023-7-c0f40915bd", "PERDA-KOTA-SURABAYA-2023-7", "PERDA-KOTA-SURABAYA-2023-7#BT/8"),
    ("TarifPajak", "Tarif_PBJT_Hiburan_Surabaya_50Pct", "Tarif PBJT Jasa Hiburan Khusus (Diskotek/Kelab/Bar/Spa) Surabaya 50% (Perda Surabaya 7/2023 Pasal 27(3))", 50.0, "R-PERDA-KOTA-SURABAYA-2023-7-cc13cd7fa2", "PERDA-KOTA-SURABAYA-2023-7", "PERDA-KOTA-SURABAYA-2023-7#BT/27"),
    ("TarifPajak", "Tarif_PBB_Semarang_0_3Pct", "Tarif PBB-P2 Umum Kota Semarang 0,3% (Perda Semarang 10/2023 Pasal 8)", 0.3, "R-PERDA-KOTA-SEMARANG-2023-10-476854207a", "PERDA-KOTA-SEMARANG-2023-10", "PERDA-KOTA-SEMARANG-2023-10#BT/8"),
    ("TarifPajak", "Tarif_PKB_Bali_Max200cc_1_055Pct", "Tarif PKB Provinsi Bali Kendaraan <= 200cc sebesar 1,055% + Opsen (Perda Bali 1/2024 Pasal 8a)", 1.055, "R-PERDA-PROV-BALI-2024-1-7f80545176", "PERDA-PROV-BALI-2024-1", "PERDA-PROV-BALI-2024-1#BT/8"),
    ("TarifPajak", "Tarif_PKB_Bali_Over200cc_1_2Pct", "Tarif PKB Provinsi Bali Kendaraan > 200cc sebesar 1,2% + Opsen (Perda Bali 1/2024 Pasal 8b)", 1.2, "R-PERDA-PROV-BALI-2024-1-fd40ec084a", "PERDA-PROV-BALI-2024-1", "PERDA-PROV-BALI-2024-1#BT/8"),
    ("TarifPajak", "Tarif_PBJT_Hiburan_DKI_40Pct", "Tarif PBJT Jasa Hiburan Khusus DKI Jakarta 40% (Perda DKI 1/2024 Pasal 53(2))", 40.0, "R-PERDA-PROV-DKI-JAKARTA-2024-1-0117748e9b", "PERDA-PROV-DKI-JAKARTA-2024-1", "PERDA-PROV-DKI-JAKARTA-2024-1#BT/53"),
    ("PP55UMKM", "Fasilitas_PP55_Final_0_5Pct", "Fasilitas PPh Final UMKM 0,5% (omzet <= Rp4,8M/tahun, PP 55/2022 Pasal 56(2))", 0.5, "R-PP-2022-55-a9963cde88", "PP-2022-55", "PP-2022-55#BT/56"),
    ("FasilitasPerpajakan", "Fasilitas_OP_UMKM_BebasPPh_500Jt", "Pembebasan PPh OP UMKM atas Bagian Peredaran Bruto s.d. Rp500 Juta/Tahun (0%, UU HPP Pasal 7(2a))", 0.0, "R-UU-1983-7-33044e4b12", "UU-1983-7", "UU-1983-7#BT/7"),
    ("FasilitasPerpajakan", "Fasilitas_PTKP_Dasar_Keluarga", "Pengurang Penghasilan Tidak Kena Pajak (PTKP: Rp54jt WP + Rp4,5jt Kawin + Rp4,5jt/Tanggungan maks 3 + Rp54jt Istri Digabung, UU PPh Pasal 7(1))", None, "R-UU-1983-7-01c5a8a1bf", "UU-1983-7", "UU-1983-7#BT/7"),
    ("FasilitasPerpajakan", "Fasilitas_NPPN_OP_Dibawah_4_8M", "Hak Menggunakan Norma Penghitungan Penghasilan Neto (NPPN) bagi OP Usaha/Pekerjaan Bebas Omzet < Rp4,8M (UU PPh Pasal 14(2)-(3))", None, "R-UU-1983-7-df018b5a7f", "UU-1983-7", "UU-1983-7#BT/14"),
    ("FasilitasPerpajakan", "Fasilitas_PPN_Dibebaskan_Strategis", "Pembebasan PPN atas Barang Kena Pajak Tertentu yang Bersifat Strategis (PP 49/2022 Pasal 6)", 0.0, "R-PP-2022-49-27f724ae54", "PP-2022-49", "PP-2022-49#BT/6"),
    ("FasilitasPerpajakan", "Fasilitas_TaxHoliday_50Pct_5Thn", "Tax Holiday Pengurangan PPh Badan 50% selama 5 Tahun Pajak (investasi Rp100M s.d. <Rp500M, PMK 130/2020)", 50.0, "R-PMK-2020-130-a3c9ffdaa5", "PMK-2020-130", "PMK-2020-130#BT/2/1..3"),
    ("FasilitasPerpajakan", "Fasilitas_TaxHoliday_100Pct_5Thn", "Tax Holiday Pengurangan PPh Badan 100% selama 5 Tahun Pajak (investasi Rp500M s.d. <Rp1T, PMK 130/2020)", 100.0, "R-PMK-2020-130-ded6b8c866", "PMK-2020-130", "PMK-2020-130#BT/2/4..6"),
    ("FasilitasPerpajakan", "Fasilitas_TaxHoliday_100Pct_7Thn", "Tax Holiday Pengurangan PPh Badan 100% selama 7 Tahun Pajak (investasi Rp1T s.d. <Rp5T, PMK 130/2020)", 100.0, "R-PMK-2020-130-3feb2730e9", "PMK-2020-130", "PMK-2020-130#BT/2/4..6"),
    ("FasilitasPerpajakan", "Fasilitas_TaxHoliday_100Pct_10Thn", "Tax Holiday Pengurangan PPh Badan 100% selama 10 Tahun Pajak (investasi Rp5T s.d. <Rp15T, PMK 130/2020)", 100.0, "R-PMK-2020-130-dec1450db6", "PMK-2020-130", "PMK-2020-130#BT/2/4..6"),
    ("FasilitasPerpajakan", "Fasilitas_TaxHoliday_100Pct_15Thn", "Tax Holiday Pengurangan PPh Badan 100% selama 15 Tahun Pajak (investasi Rp15T s.d. <Rp30T, PMK 130/2020)", 100.0, "R-PMK-2020-130-b00c31f6b5", "PMK-2020-130", "PMK-2020-130#BT/2/4..6"),
    ("FasilitasPerpajakan", "Fasilitas_TaxHoliday_100Pct_20Thn", "Tax Holiday Pengurangan PPh Badan 100% selama 20 Tahun Pajak (investasi >= Rp30T, PMK 130/2020)", 100.0, "R-PMK-2020-130-4777afbb39", "PMK-2020-130", "PMK-2020-130#BT/2/4..6"),
    ("FasilitasPerpajakan", "Fasilitas_Pasal31E_Diskon50Pct_11Pct", "Fasilitas Pengurangan Tarif PPh Badan 50% (efektif 11%) atas PKP Bagian Omzet s.d. Rp4,8M bagi Badan Dalam Negeri Omzet <= Rp50M (UU PPh Pasal 31E)", 11.0, "R-UU-1983-7-7432ceabb5", "UU-1983-7", "UU-1983-7#BT/31E"),
    ("FasilitasPerpajakan", "Fasilitas_TaxHoliday_Transisi_50Pct_2Thn", "Transisi Tax Holiday Pengurangan PPh Badan 50% Selama 2 Tahun Pajak Berikutnya (PMK 130/2020 Pasal 2(4)a)", 50.0, "R-PMK-2020-130-3f8c73eabe", "PMK-2020-130", "PMK-2020-130#BT/2/4..6"),
    ("FasilitasPerpajakan", "Fasilitas_TaxHoliday_Transisi_25Pct_2Thn", "Transisi Tax Holiday Pengurangan PPh Badan 25% Selama 2 Tahun Pajak Berikutnya (PMK 130/2020 Pasal 2(4)b)", 25.0, "R-PMK-2020-130-1d570586a5", "PMK-2020-130", "PMK-2020-130#BT/2/4..6"),
    ("FasilitasPerpajakan", "Fasilitas_TaxAllowance_PP78_30Pct", "Tax Allowance Pengurangan Penghasilan Neto 30% (5%/tahun selama 6 tahun) Bidang/Daerah Tertentu (PP 78/2019 Pasal 3(1)a)", 30.0, "R-PP-2019-78-17ae360038", "PP-2019-78", "PP-2019-78#BT/3/1/a"),
    ("FasilitasPerpajakan", "Fasilitas_PadatKarya_PMK81_60Pct", "Fasilitas Industri Padat Karya Pengurangan Penghasilan Neto 60% atas Aktiva Tetap Berwujud Baru (PMK 81/2024 Pasal 423)", 60.0, "R-PMK-2024-81-10955d1fd9", "PMK-2024-81", "PMK-2024-81#BT/423"),
    ("FasilitasPerpajakan", "Fasilitas_Pengecualian_SpaKesehatanTradisional_MK", "Pengecualian PBJT Hiburan 40-50% untuk Mandi Uap/Spa Bagian Pelayanan Kesehatan Tradisional (Putusan MK-2024-19-PUU-XXII)", 10.0, "R-PERDA-PROV-DKI-JAKARTA-2024-1-0117748e9b", "PERDA-PROV-DKI-JAKARTA-2024-1", "PERDA-PROV-DKI-JAKARTA-2024-1#BT/53"),
    ("FasilitasPerpajakan", "Fasilitas_Pengecualian_PPh23_Bank", "Pengecualian Pemotongan PPh Pasal 23 atas Penghasilan yang Dibayar/Terutang kepada Bank (Pasal 23 ayat (4) huruf a UU PPh)", 0.0, "R-UU-1983-7-03505d13a1", "UU-1983-7", "UU-1983-7#BT/23/4"),
    ("FasilitasPerpajakan", "Fasilitas_Pengecualian_DendaSPT_Pasal7_2", "Pengecualian Pengenaan Sanksi Denda Keterlambatan SPT bagi WP Tutup Usaha/Meninggal/WNA Keluar/Bencana (UU KUP Pasal 7(2))", 0.0, "R-UU-1983-6-a86dd99b6a", "UU-1983-6", "UU-1983-6#BT/7"),
    ("FasilitasPerpajakan", "Fasilitas_Pengecualian_SewaPenginapan_PP34", "Pengecualian PPh Final Persewaan Tanah/Bangunan bagi Jasa Pelayanan Penginapan Beserta Akomodasinya (PP 34/2017 Pasal 2(3))", 0.0, "R-PP-2017-34-86e520fb7b", "PP-2017-34", "PP-2017-34#BT/2"),
    ("FasilitasPerpajakan", "Fasilitas_Pengecualian_Deposito_Dibawah_7_5Jt", "Pengecualian Pemotongan PPh Final atas Bunga Deposito/Tabungan/SBI dengan Pokok <= Rp7,5 Juta & Bukan Dipecah-pecah (PP 131/2000 Pasal 3(a))", 0.0, "R-PP-2000-131-df0f230457", "PP-2000-131", "PP-2000-131#BT/3"),
    ("FasilitasPerpajakan", "Fasilitas_Restitusi_BungaDeposito_DibawahPTKP", "Pengecualian/Hak Restitusi PPh Final Bunga Deposito bagi OP SPDN Total Penghasilan <= PTKP (PP 131/2000 Pasal 1(3)-(4))", 0.0, "R-PP-2000-131-d7e7a5e6ac", "PP-2000-131", "PP-2000-131#BT/1"),
    ("FasilitasPerpajakan", "Fasilitas_Pengecualian_Pengalihan_OP_Dibawah60Jt_PTKP", "Pengecualian PPh Final Pengalihan Tanah/Bangunan bagi OP Berpenghasilan < PTKP dengan Nilai Bruto < Rp60 Juta (PP 34/2016 Pasal 6 huruf a)", 0.0, "R-PP-2016-34-9bbd83e4c2", "PP-2016-34", "PP-2016-34#BT/6"),
    ("KewajibanPajak", "Kewajiban_DaftarPKP_PungutPPN", "Kewajiban Melaporkan Usaha untuk Dikukuhkan sebagai PKP & Memungut PPN (omzet > Rp4,8M, UU PPN Pasal 3A & PMK 164/2023)", None, "R-PMK-2023-164-706302d621", "PMK-2023-164", "PMK-2023-164#BT/17"),
    ("KewajibanPajak", "Kewajiban_PotongSetor_SewaTanahBangunan", "Kewajiban Pemotongan PPh Final Sewa Tanah/Bangunan oleh Penyewa Pemotong atau Penyetoran Sendiri bila Penyewa Non-Pemotong (PP 34/2017 Pasal 3)", None, "R-PP-2017-34-a465bbabaa", "PP-2017-34", "PP-2017-34#BT/3"),
    ("KewajibanPajak", "Kewajiban_PencatatanTerpisah_JasaKonstruksi", "Kewajiban Pencatatan Biaya Terpisah atas Penghasilan di Luar Usaha Jasa Konstruksi yang Dikenai Tarif Umum (PP 51/2008 Pasal 7(2) & Pasal 8)", None, "R-PP-2008-51-a8ec884e18", "PP-2008-51", "PP-2008-51#BT/8"),
    ("KewajibanPajak", "Kewajiban_SetorSSP_ValidasiKPP_SebelumAkta", "Kewajiban Menyerahkan SSP Tervalidasi KPP Sebelum Penandatanganan Akta PPAT/Risalah Lelang (PP 34/2016 Pasal 3(5))", None, "R-PP-2016-34-c396034237", "PP-2016-34", "PP-2016-34#BT/3/3..5"),
    ("KewajibanPajak", "Kewajiban_Opsen_PKB_66Pct", "Kewajiban Opsen PKB sebesar 66% dari PKB Terutang sesuai HKPD (Perda Kab/Kota & Prov Jabar/Surabaya/Bali)", None, "R-PERDA-KOTA-SURABAYA-2023-7-14b13617b1", "PERDA-KOTA-SURABAYA-2023-7", "PERDA-KOTA-SURABAYA-2023-7#BT/44"),
    ("KewajibanPajak", "Kewajiban_Peralihan_UMKM_Ke_KetentuanUmum", "Kewajiban Transisi WP UMKM yang Omzetnya Melebihi Rp4,8M ke Tarif Umum Tahun Pajak Berikutnya (PP 55/2022 Pasal 61 & PMK 164/2023 Pasal 5(5))", None, "R-PMK-2023-164-2ded388f17", "PMK-2023-164", "PMK-2023-164#BT/5"),
    ("KewajibanPajak", "Kewajiban_NPWP_NIK_OP", "Penggunaan NIK sebagai NPWP bagi Wajib Pajak Orang Pribadi Penduduk Indonesia (PMK 112/2022 Pasal 2(1)a)", None, "R-PMK-2022-112-a91070d05f", "PMK-2022-112", "PMK-2022-112#BT/2"),
    ("KewajibanPajak", "Kewajiban_LaporSPT", "Kewajiban Mengisi dan Menyampaikan SPT dengan Benar, Lengkap, dan Jelas (UU KUP Pasal 3(1))", None, "R-UU-1983-6-689d7b8926", "UU-1983-6", "UU-1983-6#BT/3/1..3b"),
    ("KewajibanPajak", "Kewajiban_Tenggat_SPT_Tahunan_OP_3Bln", "Batas Waktu Penyampaian SPT Tahunan PPh Orang Pribadi Paling Lama 3 Bulan Setelah Akhir Tahun Pajak (UU KUP Pasal 3(3)b)", None, "R-UU-1983-6-ec282e98db", "UU-1983-6", "UU-1983-6#BT/3/1..3b"),
    ("KewajibanPajak", "Kewajiban_Tenggat_SPT_Tahunan_Badan_4Bln", "Batas Waktu Penyampaian SPT Tahunan PPh Badan Paling Lama 4 Bulan Setelah Akhir Tahun Pajak (UU KUP Pasal 3(3)c)", None, "R-UU-1983-6-31abe376bc", "UU-1983-6", "UU-1983-6#BT/3/1..3b"),
    ("KewajibanPajak", "Kewajiban_LaporPBB", "Kewajiban Subjek/Wajib Pajak PBB-P2 atas Kepemilikan/Penguasaan Objek Bumi/Bangunan (Perda DKI 1/2024 Pasal 32 & 34)", None, "R-PERDA-PROV-DKI-JAKARTA-2024-1-675c47e425", "PERDA-PROV-DKI-JAKARTA-2024-1", "PERDA-PROV-DKI-JAKARTA-2024-1#BT/32"),
    ("KewajibanPajak", "Kewajiban_PekerjaBebas_TarifUmum_NonPP55", "Pekerja Bebas Dikecualikan dari PPh Final UMKM PP 55 (0,5%) dan Wajib Menghitung PPh dengan Tarif Umum Pasal 17 (PP 55/2022 Pasal 56(3)a)", None, "R-PP-2022-55-a9963cde88", "PP-2022-55", "PP-2022-55#BT/56"),
    ("KewajibanPajak", "Kewajiban_Pembukuan_OP_4_8M_KeAtas", "Kewajiban Menyelenggarakan Pembukuan bagi OP Usaha/Pekerjaan Bebas dengan Peredaran Bruto >= Rp4,8M (UU PPh Pasal 14(2))", None, "R-UU-1983-7-df018b5a7f", "UU-1983-7", "UU-1983-7#BT/14"),
    ("KewajibanPajak", "Kewajiban_LaporSPT_OP_LaporSeluruhPenghasilan", "Kewajiban OP Penerima Penghasilan Melaporkan Seluruh Penghasilan & Kredit Bukti Potong PPh 21 dalam SPT Tahunan (PMK 168/2023 Pasal 22(4))", None, "R-PMK-2023-168-7b71c91b55", "PMK-2023-168", "PMK-2023-168#BT/22"),
    ("KewajibanPajak", "Kewajiban_Rekonsiliasi_MultiPemberiKerja", "Kewajiban Hitung Ulang & Lapor Gabungan SPT Tahunan OP bagi Pegawai yang Menerima Penghasilan dari >1 Pemberi Kerja (PMK 168/2023 Pasal 22(4))", None, "R-PMK-2023-168-7b71c91b55", "PMK-2023-168", "PMK-2023-168#BT/22"),
    ("KewajibanPajak", "Kewajiban_Pembukuan_OP_NPPN_Terlambat", "Kewajiban Pembukuan bagi OP Usaha/Pekerjaan Bebas yang Tidak Memberitahukan Penggunaan NPPN Tepat Waktu (UU PPh Pasal 14(4))", None, "R-UU-1983-7-ae4471284f", "UU-1983-7", "UU-1983-7#BT/14"),
    ("SanksiAdministratif", "Sanksi_NPPN_Norma_Pemeriksaan_Pasal14_5", "Penghitungan Penghasilan Neto Menggunakan Norma Pemeriksaan Pasal 14(5) karena Tidak Menyelenggarakan Pembukuan/Pencatatan (UU PPh Pasal 14(5))", None, "R-UU-1983-7-d33a781efe", "UU-1983-7", "UU-1983-7#BT/14"),
    ("SanksiAdministratif", "Sanksi_Denda_KUP_SPT_OP_100Rb", "Sanksi Denda Keterlambatan Penyampaian SPT Tahunan PPh Orang Pribadi Rp100.000 (UU KUP Pasal 7(1))", None, "R-UU-1983-6-a86dd99b6a", "UU-1983-6", "UU-1983-6#BT/7"),
    ("SanksiAdministratif", "Sanksi_Denda_KUP_SPT_Badan_1Jt", "Sanksi Denda Keterlambatan Penyampaian SPT Tahunan PPh Badan Rp1.000.000 (UU KUP Pasal 7(1))", None, "R-UU-1983-6-a86dd99b6a", "UU-1983-6", "UU-1983-6#BT/7"),
    ("SanksiAdministratif", "Sanksi_Denda_KUP_SPT_MasaPPN_500Rb", "Sanksi Denda Keterlambatan Penyampaian SPT Masa PPN Rp500.000 (UU KUP Pasal 7(1))", None, "R-UU-1983-6-a86dd99b6a", "UU-1983-6", "UU-1983-6#BT/7"),
    ("SanksiAdministratif", "Sanksi_Bunga_SKPKB_Pasal13_2", "Sanksi Bunga Per Bulan SKPKB (Suku Bunga Acuan KMK + Uplift) Maksimal 24 Bulan atas Pajak Kurang Dibayar (UU KUP Pasal 13(2))", None, "R-UU-1983-6-b688396c60", "UU-1983-6", "UU-1983-6#BT/13/1..2"),
    ("SanksiAdministratif", "Sanksi_Kenaikan_75Pct_TidakSetor_Pasal13_3", "Sanksi Kenaikan 75% atas PPN/PPh Potput yang Tidak atau Kurang Disetor Hasil Pemeriksaan SKPKB (UU KUP Pasal 13(3)c-d)", 75.0, "R-UU-1983-6-288fec0fc6", "UU-1983-6", "UU-1983-6#BT/13/2a..3b"),
    ("SanksiAdministratif", "Sanksi_PPh23_Kenaikan100Pct_NonNPWP", "Kenaikan Tarif Pemotongan PPh Pasal 23 Lebih Tinggi 100% (2x Lipat) bagi Penerima Penghasilan Tanpa NPWP (UU PPh Pasal 23(1a))", 100.0, "R-UU-1983-7-22a9a1a1fa", "UU-1983-7", "UU-1983-7#BT/23/1..4"),
    ("SanksiAdministratif", "Sanksi_Keberatan_30Pct", "Sanksi Denda 30% bila Keberatan Ditolak atau Dikabulkan Sebagian (UU KUP Pasal 25(9))", 30.0, "R-UU-1983-6-c367eea7f6", "UU-1983-6", "UU-1983-6#BT/25/9..10"),
    ("SanksiAdministratif", "Sanksi_Banding_60Pct", "Sanksi Denda 60% bila Banding Ditolak atau Dikabulkan Sebagian (UU KUP Pasal 27(5d))", 60.0, "R-UU-1983-6-ad287a542a", "UU-1983-6", "UU-1983-6#BT/27/1..5d"),
]


def _safe_id(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", (s or "").strip()).strip("_") or "Unknown"


def _doc_subclass_name(doc_id: str) -> str:
    if doc_id.startswith("UU-") or doc_id.startswith("PERPU-"):
        return "UndangUndang"
    if doc_id.startswith("PP-"):
        return "PeraturanPemerintah"
    if doc_id.startswith("PMK-"):
        return "PeraturanMenteriKeuangan"
    if doc_id.startswith("PER-DJP-"):
        return "PeraturanDirjenPajak"
    if doc_id.startswith("PERDA-"):
        return "PeraturanDaerah"
    return "Regulasi"


def _rule_subclass_name(rtype: str) -> str:
    return {
        "obligation": "Kewajiban",
        "right": "Hak",
        "prohibition": "Larangan",
        "exception": "Pengecualian",
        "sanction": "Sanksi",
        "deadline": "BatasWaktu",
        "rate": "AturanTarif",
        "definition": "Definisi",
        "procedure": "Prosedur",
        "eligibility": "Kelayakan",
    }.get(rtype, "AturanHukum")


def build_tbox(world: Optional[World] = None) -> tuple:
    """Bangun TBox SROIQ(D) + aturan SWRL DL-safe pada World terisolasi."""
    w = world or World()
    onto = w.get_ontology(ONTO_IRI)

    with onto:
        # 1. Hirarki Kelas Inti (selaras dengan starter UC1 & UC2 tim)
        class WajibPajak(Thing): pass
        class OrangPribadi(WajibPajak): pass
        class Badan(WajibPajak): pass
        class BadanDalamNegeri(Badan): pass
        class BadanHukumIndonesia(BadanDalamNegeri): pass
        class PT(BadanHukumIndonesia): pass
        class Koperasi(BadanHukumIndonesia): pass
        class CV(BadanDalamNegeri): pass
        class Yayasan(BadanDalamNegeri): pass
        class BadanUsahaTetap(Badan): pass
        class UMKM(WajibPajak): pass
        class BUT(BadanUsahaTetap): pass
        class BadanTerbukaTbk(Badan): pass
        class BadanNonTbk(Badan): pass
        class PengusahaKenaPajak(WajibPajak): pass
        class WajibPajakUMKM(WajibPajak): pass
        class WajibPajakNonUMKM(WajibPajak): pass
        class SubjekPajakAktif(WajibPajak): pass

        # Kelas kelayakan fasilitas & wilayah/daerah (untuk klasifikasi SROIQ(D))
        class BadanLayakPasal31E(BadanDalamNegeri): pass
        class BadanLayakTaxAllowance(BadanDalamNegeri): pass
        class BadanLayakPadatKarya(BadanDalamNegeri): pass
        class LayakTaxHoliday(BadanDalamNegeri): pass
        class LayakTaxHoliday_50Pct_5Thn(LayakTaxHoliday): pass
        class LayakTaxHoliday_100Pct_5Thn(LayakTaxHoliday): pass
        class LayakTaxHoliday_100Pct_7Thn(LayakTaxHoliday): pass
        class LayakTaxHoliday_100Pct_10Thn(LayakTaxHoliday): pass
        class LayakTaxHoliday_100Pct_15Thn(LayakTaxHoliday): pass
        class LayakTaxHoliday_100Pct_20Thn(LayakTaxHoliday): pass

        class WilayahDaerah(Thing): pass
        class WP_Wilayah_DKI(WajibPajak): pass
        class WP_Wilayah_Jabar(WajibPajak): pass
        class WP_Wilayah_Surabaya(WajibPajak): pass
        class WP_Wilayah_Semarang(WajibPajak): pass
        class WP_Wilayah_Bali(WajibPajak): pass
        class WP_Wilayah_Nasional_NonDKI(WajibPajak): pass
        class WP_Wilayah_NonDKI_Kendaraan(WajibPajak): pass

        class Badan_PemilikKendaraanDKI(Badan): pass
        class OP_PemilikKendaraanDKI(OrangPribadi): pass
        class OP_KendaraanKe1_DKI(OP_PemilikKendaraanDKI): pass
        class OP_KendaraanKe2_DKI(OP_PemilikKendaraanDKI): pass
        class OP_KendaraanKe3_DKI(OP_PemilikKendaraanDKI): pass
        class OP_KendaraanKe4_DKI(OP_PemilikKendaraanDKI): pass
        class OP_KendaraanKe5Plus_DKI(OP_PemilikKendaraanDKI): pass

        class OP_KendaraanKe1_Jabar(OrangPribadi): pass
        class OP_KendaraanKe2_Jabar(OrangPribadi): pass
        class OP_KendaraanKe3_Jabar(OrangPribadi): pass
        class OP_KendaraanKe4_Jabar(OrangPribadi): pass
        class OP_KendaraanKe5Plus_Jabar(OrangPribadi): pass
        class Badan_PemilikKendaraanJabar(Badan): pass

        class WP_PBB_Surabaya_L1(WajibPajak): pass
        class WP_PBB_Surabaya_L2(WajibPajak): pass
        class WP_PBB_Surabaya_L3(WajibPajak): pass
        class WP_PBB_Surabaya_L4(WajibPajak): pass
        class WP_PBB_Surabaya_L5(WajibPajak): pass
        class WP_PBB_Surabaya_L6(WajibPajak): pass
        class OP_Kendaraan_Bali_Max200cc(OrangPribadi): pass
        class OP_Kendaraan_Bali_Over200cc(OrangPribadi): pass

        class PenerimaPPh23_NonBank_JasaSewa(WajibPajak): pass
        class PenerimaPPh23_NonBank_Modal(WajibPajak): pass
        class WP_PPh23_TanpaNPWP(WajibPajak): pass

        # Klasifikasi Rezim Pajak Orang Pribadi (PMK-2023-168, PP-2023-58, PP-2022-55, UU HPP)
        class JenisPekerjaan(Thing): pass
        class PekerjaanPegawai(JenisPekerjaan): pass
        class PekerjaanPegawaiTetap(PekerjaanPegawai): pass
        class PekerjaanPegawaiTidakTetap(PekerjaanPegawai): pass
        class PekerjaanPesertaKegiatan(PekerjaanPegawai): pass
        class PekerjaanBebas(JenisPekerjaan): pass
        class UsahaDagangJasa(JenisPekerjaan): pass

        class OP_SubjekDalamNegeri(OrangPribadi): pass
        class OP_SubjekLuarNegeri(OrangPribadi): pass
        class OP_PenerimaPPh21_PegawaiTetap(OrangPribadi): pass
        class OP_TER_Kategori_A(OP_PenerimaPPh21_PegawaiTetap): pass
        class OP_TER_Kategori_B(OP_PenerimaPPh21_PegawaiTetap): pass
        class OP_TER_Kategori_C(OP_PenerimaPPh21_PegawaiTetap): pass
        class OP_PenerimaPPh21_TidakTetap(OrangPribadi): pass
        class OP_PesertaKegiatan(OrangPribadi): pass
        class OP_PekerjaBebas(OrangPribadi): pass
        class OP_PekerjaBebas_LayakNPPN(OP_PekerjaBebas): pass
        class OP_NPPN_Gugur_TelatLapor(OP_PekerjaBebas_LayakNPPN): pass
        class WP_TidakSelenggarakanPembukuan(WajibPajak): pass
        class OP_PelakuUsahaNonProfesi(OrangPribadi): pass
        class OP_UMKM_Bebas_500Jt(OP_PelakuUsahaNonProfesi): pass
        class OP_UMKM_Final_PP55(OP_PelakuUsahaNonProfesi): pass
        class OP_WajibPembukuan(OrangPribadi): pass
        class OP_MultiPemberiKerja(OP_PenerimaPPh21_PegawaiTetap): pass
        class OP_PPh17_Layer1_5Pct(OrangPribadi): pass
        class OP_PPh17_Layer2_15Pct(OrangPribadi): pass
        class OP_PPh17_Layer3_25Pct(OrangPribadi): pass
        class OP_PPh17_Layer4_30Pct(OrangPribadi): pass
        class OP_PPh17_Layer5_35Pct(OrangPribadi): pass
        class BadanUMKM(Badan): pass

        # Katalog Pajak & Risiko
        class TarifPajak(Thing): pass
        class TarifProgresif(TarifPajak): pass
        class TarifFinal(TarifPajak): pass
        class FasilitasPerpajakan(Thing): pass
        class PP55UMKM(FasilitasPerpajakan): pass
        class KewajibanPajak(Thing): pass
        class SanksiAdministratif(Thing): pass
        class DomainPajak(Thing): pass
        class ObjekPajak(Thing): pass

        # Taksonomi Objek Penghasilan Final Pasal 4 ayat (2) (PP 34/2017, PP 131/2000, PP 51/2008 jo. PP 9/2022, PP 34/2016)
        class ObjekPenghasilanFinal(ObjekPajak): pass
        class SewaTanahDanBangunan(ObjekPenghasilanFinal): pass
        class BungaDepositoDanTabungan(ObjekPenghasilanFinal): pass
        class ObjekBungaDepositoTabunganUmum(BungaDepositoDanTabungan): pass
        class ObjekDepositoDHE_USD(BungaDepositoDanTabungan): pass
        class JasaKonstruksi(ObjekPenghasilanFinal): pass
        class JasaKonstruksiPekerjaanKecilSBU(JasaKonstruksi): pass
        class JasaKonstruksiPekerjaanNonKecilSBU(JasaKonstruksi): pass
        class JasaKonstruksiTerintegrasiSBU(JasaKonstruksi): pass
        class JasaKonstruksiPekerjaanTanpaSBU(JasaKonstruksi): pass
        class JasaKonstruksiTerintegrasiTanpaSBU(JasaKonstruksi): pass
        class JasaKonstruksiKonsultansiSBU(JasaKonstruksi): pass
        class JasaKonstruksiKonsultansiTanpaSBU(JasaKonstruksi): pass
        class PengalihanHakAtasTanahBangunan(ObjekPenghasilanFinal): pass
        class PengalihanTanahBangunanUmum(PengalihanHakAtasTanahBangunan): pass
        class PengalihanRumahSederhanaDeveloper(PengalihanHakAtasTanahBangunan): pass
        class PengalihanKepadaPemerintahPenugasan(PengalihanHakAtasTanahBangunan): pass

        # Kelas Rezim WajibPajak Penerima Penghasilan Final Pasal 4(2) (non-disjoint -> mendukung multi-sumber penghasilan)
        class WP_PenerimaSewaTanahBangunan(WajibPajak): pass
        class WP_Pengecualian_SewaPenginapan(WajibPajak): pass
        class WP_PenerimaBungaDeposito(WajibPajak): pass
        class WP_PenerimaBungaDepositoDHE_USD(WajibPajak): pass
        class WP_Pengecualian_Deposito_Max7_5Jt(WajibPajak): pass
        class WP_Pengecualian_Deposito_DibawahPTKP(OrangPribadi): pass
        class WP_PenyediaJasaKonstruksi(WajibPajak): pass
        class WP_JasaKonstruksi_Kecil_SBU(WP_PenyediaJasaKonstruksi): pass
        class WP_JasaKonstruksi_NonKecil_SBU(WP_PenyediaJasaKonstruksi): pass
        class WP_JasaKonstruksi_Terintegrasi_SBU(WP_PenyediaJasaKonstruksi): pass
        class WP_JasaKonstruksi_TanpaSBU(WP_PenyediaJasaKonstruksi): pass
        class WP_JasaKonstruksi_Terintegrasi_TanpaSBU(WP_PenyediaJasaKonstruksi): pass
        class WP_JasaKonstruksi_Konsultansi_SBU(WP_PenyediaJasaKonstruksi): pass
        class WP_JasaKonstruksi_Konsultansi_TanpaSBU(WP_PenyediaJasaKonstruksi): pass
        class WP_PengalihanTanahBangunan(WajibPajak): pass
        class WP_Pengalihan_Umum_2_5Pct(WP_PengalihanTanahBangunan): pass
        class WP_Pengalihan_RumahSederhana_1Pct(WP_PengalihanTanahBangunan): pass
        class WP_Pengalihan_Pemerintah_0Pct(WP_PengalihanTanahBangunan): pass
        class WP_Pengecualian_Pengalihan_OP_Dibawah60Jt(WP_PengalihanTanahBangunan): pass

        # Lapisan Hukum & Provenance
        class DokumenHukum(Thing): pass
        class Regulasi(DokumenHukum): pass
        class UndangUndang(Regulasi): pass
        class PeraturanPemerintah(Regulasi): pass
        class PeraturanMenteriKeuangan(Regulasi): pass
        class PeraturanDirjenPajak(Regulasi): pass
        class PeraturanDaerah(Regulasi): pass
        class Pasal(DokumenHukum): pass
        class PutusanMK(DokumenHukum): pass
        class SEMA_TUN(DokumenHukum): pass

        class AturanHukum(Thing): pass
        class Kewajiban(AturanHukum): pass
        class Hak(AturanHukum): pass
        class Larangan(AturanHukum): pass
        class Pengecualian(AturanHukum): pass
        class Sanksi(AturanHukum): pass
        class BatasWaktu(AturanHukum): pass
        class AturanTarif(AturanHukum): pass
        class Definisi(AturanHukum): pass
        class Prosedur(AturanHukum): pass
        class Kelayakan(AturanHukum): pass

        # 2. Object Properties (SROIQ: Transitive, Asymmetric, Irreflexive, PropertyChain, Inverse)
        class diaturDalam(AturanHukum >> Regulasi): pass
        class mengatur(Regulasi >> AturanHukum):
            inverse_property = diaturDalam
        class diaturDalamPasal(AturanHukum >> Pasal, AsymmetricProperty, IrreflexiveProperty): pass
        class memuatAturan(Pasal >> AturanHukum):
            inverse_property = diaturDalamPasal
        class bagianDariRegulasi(Pasal >> Regulasi, AsymmetricProperty, IrreflexiveProperty): pass
        class memilikiPasal(Regulasi >> Pasal):
            inverse_property = bagianDariRegulasi
        class merujukDokumen(DokumenHukum >> DokumenHukum, TransitiveProperty): pass

        # Property Chain (R): AturanHukum -> Pasal -> Regulasi => diaturDalam Regulasi
        diaturDalam.property_chain.append(PropertyChain([diaturDalamPasal, bagianDariRegulasi]))

        class didasarkanPadaAturan(Thing >> AturanHukum): pass
        class terdampakPutusanMK(AturanHukum >> PutusanMK): pass
        class merujukSEMA(AturanHukum >> SEMA_TUN): pass
        class termasukDomain(Thing >> DomainPajak): pass

        class dikenaiTarif(WajibPajak >> TarifPajak): pass
        class memilikiFasilitas(WajibPajak >> FasilitasPerpajakan): pass
        class memilikiKewajiban(WajibPajak >> KewajibanPajak): pass
        class berisikoSanksi(WajibPajak >> SanksiAdministratif): pass
        class memilikiPekerjaan(OrangPribadi >> JenisPekerjaan): pass
        class memilikiPenghasilanFinal(WajibPajak >> ObjekPenghasilanFinal): pass
        class berdomisiliDi(WajibPajak >> WilayahDaerah): pass

        # 3. Data Properties
        class hasOmzetTahunan(WajibPajak >> float, FunctionalProperty): pass
        class hasNilaiInvestasi(WajibPajak >> float, FunctionalProperty): pass
        class hasPersentaseSahamPublik(Badan >> float, FunctionalProperty): pass
        class hasJumlahKendaraan(WajibPajak >> int, FunctionalProperty): pass
        class isPerseroanTerbuka(Badan >> bool, FunctionalProperty): pass
        class isIndustriPionir(Badan >> bool, FunctionalProperty): pass
        class isPenanamanModalBaru(Badan >> bool, FunctionalProperty): pass
        class isUMKM_PP55(WajibPajak >> bool, FunctionalProperty): pass
        class hasNPWP(WajibPajak >> bool, FunctionalProperty): pass
        class isDomisiliDKI(WajibPajak >> bool, FunctionalProperty): pass
        class isMilikPribadi(WajibPajak >> bool, FunctionalProperty): pass
        class isMemilikiObjekPBB(WajibPajak >> bool, FunctionalProperty): pass
        class isTerlambatLaporSPT(WajibPajak >> bool, FunctionalProperty): pass
        class isKeberatanDitolak(WajibPajak >> bool, FunctionalProperty): pass
        class isBandingDitolak(WajibPajak >> bool, FunctionalProperty): pass
        class isUsahaSpaKesehatanTradisional(WajibPajak >> bool, FunctionalProperty): pass
        class isUsahaHiburanSpaUmum(WajibPajak >> bool, FunctionalProperty): pass
        class isPenyerahanNonMewahPPN(WajibPajak >> bool, FunctionalProperty): pass
        class isPenyerahanBKP_Mewah(WajibPajak >> bool, FunctionalProperty): pass
        class isPenyerahanBKPStrategis(WajibPajak >> bool, FunctionalProperty): pass
        class isPerseroanPerorangan(PT >> bool, FunctionalProperty): pass
        class hasJumlahPemegangSahamPublik(Badan >> int, FunctionalProperty): pass
        class hasHariTerpenuhiTbk(Badan >> int, FunctionalProperty): pass
        class hasSuratKeteranganFiskal(Badan >> bool, FunctionalProperty): pass
        class isBelumPernahPutusTaxHoliday(Badan >> bool, FunctionalProperty): pass
        class hasNilaiNJOP(WajibPajak >> float, FunctionalProperty): pass
        class hasKapasitasMesinCC(WajibPajak >> int, FunctionalProperty): pass
        class isPenerimaPenghasilanPPh23_JasaSewa(WajibPajak >> bool, FunctionalProperty): pass
        class isPenerimaPenghasilanPPh23_Modal(WajibPajak >> bool, FunctionalProperty): pass
        class isBankPenerimaPenghasilan(WajibPajak >> bool, FunctionalProperty): pass
        class isTerlambatLaporSPTMasaPPN(WajibPajak >> bool, FunctionalProperty): pass
        class isDikecualikanDendaSPT(WajibPajak >> bool, FunctionalProperty): pass
        class isKurangBayarSKPKB(WajibPajak >> bool, FunctionalProperty): pass
        class isTidakSetorPajakDipungut(WajibPajak >> bool, FunctionalProperty): pass
        class isPendudukIndonesia(OrangPribadi >> bool, FunctionalProperty): pass
        class isSubjekLuarNegeri(OrangPribadi >> bool, FunctionalProperty): pass
        class isKawin(OrangPribadi >> bool, FunctionalProperty): pass
        class hasJumlahTanggungan(OrangPribadi >> int, FunctionalProperty): pass
        class isPenghasilanIstriDigabung(OrangPribadi >> bool, FunctionalProperty): pass
        class hasPenghasilanKenaPajakTahunan(WajibPajak >> float, FunctionalProperty): pass
        class hasPenghasilanBrutoBulanan(OrangPribadi >> float, FunctionalProperty): pass
        class hasDPP_PPN(WajibPajak >> float, FunctionalProperty): pass
        class hasPersentaseNJOP_PBB(WajibPajak >> float, FunctionalProperty): pass
        class hasNJOPTKP_PBB(WajibPajak >> float, FunctionalProperty): pass
        class hasJumlahPemberiKerja(OrangPribadi >> int, FunctionalProperty): pass
        class isPemberitahuanNPPNTepatWaktu(OrangPribadi >> bool, FunctionalProperty): pass
        class isTidakMenyelenggarakanPembukuanPencatatan(WajibPajak >> bool, FunctionalProperty): pass
        class kelompokWilayahNPPN(OrangPribadi >> str, FunctionalProperty): pass
        class isBidangUsahaTaxAllowance(BadanDalamNegeri >> bool, FunctionalProperty): pass
        class isLokasiProvinsiMemenuhiTaxAllowance(BadanDalamNegeri >> bool, FunctionalProperty): pass
        class isIndustriPadatKarya(BadanDalamNegeri >> bool, FunctionalProperty): pass
        class hasNilaiSewaTanahBangunanTahunan(WajibPajak >> float, FunctionalProperty): pass
        class hasBungaDepositoTabunganTahunan(WajibPajak >> float, FunctionalProperty): pass
        class hasPokokDepositoTabungan(WajibPajak >> float, FunctionalProperty): pass
        class hasNilaiBrutoJasaKonstruksi(WajibPajak >> float, FunctionalProperty): pass
        class hasNilaiPengalihanTanahBangunan(WajibPajak >> float, FunctionalProperty): pass
        class isJasaAkomodasiPenginapan(WajibPajak >> bool, FunctionalProperty): pass
        class isPenghasilanDibawahPTKP(OrangPribadi >> bool, FunctionalProperty): pass

        class hasTarifPersen(TarifPajak >> float, FunctionalProperty): pass
        class hasNominalSanksi(SanksiAdministratif >> float, FunctionalProperty): pass
        class hasRuleId(AturanHukum >> str, FunctionalProperty): pass
        class hasSourceLocator(Thing >> str, FunctionalProperty): pass
        class hasSourceQuote(Thing >> str, FunctionalProperty): pass
        class hasStatusValidasi(AturanHukum >> str, FunctionalProperty): pass
        class hasCatatanMKSEMA(AturanHukum >> str, FunctionalProperty): pass
        class hasDocumentId(DokumenHukum >> str, FunctionalProperty): pass
        class hasJudul(DokumenHukum >> str, FunctionalProperty): pass
        class hasAmarKategori(PutusanMK >> str, FunctionalProperty): pass
        class hasKaidahStatus(SEMA_TUN >> str, FunctionalProperty): pass

        # 4. Disjointness (SROIQ)
        AllDisjoint([OrangPribadi, Badan])
        AllDisjoint([PT, CV, Koperasi, Yayasan, BadanUsahaTetap])
        AllDisjoint([Kewajiban, Hak, Larangan])
        AllDisjoint([UndangUndang, PeraturanPemerintah, PeraturanMenteriKeuangan, PeraturanDirjenPajak, PeraturanDaerah])
        AllDisjoint([TarifProgresif, TarifFinal])
        AllDisjoint([PekerjaanPegawai, PekerjaanBebas, UsahaDagangJasa])
        AllDisjoint([PekerjaanPegawaiTetap, PekerjaanPegawaiTidakTetap, PekerjaanPesertaKegiatan])
        AllDisjoint([OP_SubjekDalamNegeri, OP_SubjekLuarNegeri])
        AllDisjoint([OP_TER_Kategori_A, OP_TER_Kategori_B, OP_TER_Kategori_C])
        AllDisjoint([SewaTanahDanBangunan, BungaDepositoDanTabungan, JasaKonstruksi, PengalihanHakAtasTanahBangunan])
        AllDisjoint([ObjekBungaDepositoTabunganUmum, ObjekDepositoDHE_USD])
        AllDisjoint([
            JasaKonstruksiPekerjaanKecilSBU,
            JasaKonstruksiPekerjaanNonKecilSBU,
            JasaKonstruksiTerintegrasiSBU,
            JasaKonstruksiPekerjaanTanpaSBU,
            JasaKonstruksiTerintegrasiTanpaSBU,
            JasaKonstruksiKonsultansiSBU,
            JasaKonstruksiKonsultansiTanpaSBU,
        ])
        AllDisjoint([PengalihanTanahBangunanUmum, PengalihanRumahSederhanaDeveloper, PengalihanKepadaPemerintahPenugasan])
        AllDisjoint([WajibPajak, JenisPekerjaan, ObjekPajak, WilayahDaerah, Regulasi, Pasal, AturanHukum, TarifPajak, FasilitasPerpajakan, KewajibanPajak, SanksiAdministratif, DomainPajak])

        # 5. Nominals (OneOf DomainPajak & WilayahDaerah)
        dom_names = [
            "Domain_A2_PPhBadan", "Domain_B_PPN", "Domain_C_PBB_HKPD",
            "Domain_D_AdminSanksi", "Domain_Perda_PDRD", "Domain_Fasilitas_Sektor",
            "Domain_Kepabeanan_Cukai", "Domain_PPh_OP_Potput", "Domain_PPh_Final_Sektor",
        ]
        dom_inds = [DomainPajak(dn) for dn in dom_names]
        DomainPajak.equivalent_to.append(OneOf(dom_inds))

        w_dki = WilayahDaerah("Wilayah_DKI_Jakarta")
        w_jabar = WilayahDaerah("Wilayah_Jawa_Barat")
        w_sby = WilayahDaerah("Wilayah_Kota_Surabaya")
        w_smg = WilayahDaerah("Wilayah_Kota_Semarang")
        w_bali = WilayahDaerah("Wilayah_Prov_Bali")
        w_non_dki = WilayahDaerah("Wilayah_Nasional_NonDKI")
        WilayahDaerah.equivalent_to.append(OneOf([w_dki, w_jabar, w_sby, w_smg, w_bali, w_non_dki]))

        # 6. Disjunction, Complement & Qualified Cardinality (SROIQ)
        SubjekPajakAktif.equivalent_to.append(Or([OrangPribadi, Badan]))
        BadanDalamNegeri.equivalent_to.append(Badan & Not(BadanUsahaTetap))
        BadanNonTbk.equivalent_to.append(Badan & Not(BadanTerbukaTbk))
        WajibPajakNonUMKM.equivalent_to.append(WajibPajak & Not(WajibPajakUMKM))
        Pasal.is_a.append(bagianDariRegulasi.exactly(1, Regulasi))
        AturanHukum.is_a.append(diaturDalamPasal.min(1, Pasal))
        TarifPajak.is_a.append(didasarkanPadaAturan.min(1, AturanHukum))

        # 7. Datatype Restrictions (D) -> Klasifikasi otomatis berdasar ambang numerik
        PengusahaKenaPajak.equivalent_to.append(
            WajibPajak & hasOmzetTahunan.some(ConstrainedDatatype(float, min_exclusive=4800000000.0))
        )
        # PP 55/2022 Pasal 57(1)-(2): Badan UMKM = CV, Koperasi, atau PT Perorangan (BUT & Yayasan dikecualikan)
        BadanUMKM.equivalent_to.append(
            Or([CV, Koperasi, (PT & isPerseroanPerorangan.value(True))])
            & isUMKM_PP55.value(True)
            & hasOmzetTahunan.some(ConstrainedDatatype(float, max_inclusive=4800000000.0))
        )
        # UU PPh Pasal 31E: Badan Dalam Negeri non-UMKM omzet <= Rp50M mendapat diskon tarif 50% (11%)
        BadanLayakPasal31E.equivalent_to.append(
            BadanDalamNegeri & Not(BadanUMKM)
            & hasOmzetTahunan.some(ConstrainedDatatype(float, max_inclusive=50000000000.0))
        )
        # PP 78/2019 Tax Allowance (30% pengurangan neto) & PMK 81/2024 Pasal 423 Padat Karya (60%)
        BadanLayakTaxAllowance.equivalent_to.append(
            BadanDalamNegeri & isBidangUsahaTaxAllowance.value(True)
            & isLokasiProvinsiMemenuhiTaxAllowance.value(True) & isPenanamanModalBaru.value(True)
        )
        BadanLayakPadatKarya.equivalent_to.append(
            BadanDalamNegeri & isIndustriPadatKarya.value(True) & isPenanamanModalBaru.value(True)
        )
        OP_SubjekDalamNegeri.equivalent_to.append(OrangPribadi & isSubjekLuarNegeri.value(False))
        OP_SubjekLuarNegeri.equivalent_to.append(OrangPribadi & isSubjekLuarNegeri.value(True))
        OP_PenerimaPPh21_PegawaiTetap.equivalent_to.append(OrangPribadi & memilikiPekerjaan.some(PekerjaanPegawaiTetap))
        OP_PenerimaPPh21_TidakTetap.equivalent_to.append(OrangPribadi & memilikiPekerjaan.some(PekerjaanPegawaiTidakTetap))
        OP_PesertaKegiatan.equivalent_to.append(OrangPribadi & memilikiPekerjaan.some(PekerjaanPesertaKegiatan))
        OP_PekerjaBebas.equivalent_to.append(OrangPribadi & memilikiPekerjaan.some(PekerjaanBebas))
        OP_PekerjaBebas_LayakNPPN.equivalent_to.append(
            OP_PekerjaBebas & hasOmzetTahunan.some(ConstrainedDatatype(float, max_exclusive=4800000000.0))
        )
        OP_NPPN_Gugur_TelatLapor.equivalent_to.append(
            OP_PekerjaBebas_LayakNPPN & isPemberitahuanNPPNTepatWaktu.value(False)
        )
        WP_TidakSelenggarakanPembukuan.equivalent_to.append(
            WajibPajak & isTidakMenyelenggarakanPembukuanPencatatan.value(True)
        )
        OP_PelakuUsahaNonProfesi.equivalent_to.append(OrangPribadi & memilikiPekerjaan.some(UsahaDagangJasa))
        OP_UMKM_Bebas_500Jt.equivalent_to.append(
            OP_PelakuUsahaNonProfesi & isUMKM_PP55.value(True)
            & hasOmzetTahunan.some(ConstrainedDatatype(float, max_inclusive=500000000.0))
        )
        OP_UMKM_Final_PP55.equivalent_to.append(
            OP_PelakuUsahaNonProfesi & isUMKM_PP55.value(True)
            & hasOmzetTahunan.some(ConstrainedDatatype(float, min_exclusive=500000000.0, max_inclusive=4800000000.0))
        )
        OP_WajibPembukuan.equivalent_to.append(
            Or([OP_PekerjaBebas, OP_PelakuUsahaNonProfesi])
            & hasOmzetTahunan.some(ConstrainedDatatype(float, min_inclusive=4800000000.0))
        )
        OP_MultiPemberiKerja.equivalent_to.append(
            OP_PenerimaPPh21_PegawaiTetap & hasJumlahPemberiKerja.some(ConstrainedDatatype(int, min_inclusive=2))
        )
        WajibPajakUMKM.equivalent_to.append(Or([BadanUMKM, OP_UMKM_Final_PP55]))

        # Kategori TER Bulanan PPh 21 (PP 58/2023 Pasal 2 ayat 4)
        OP_TER_Kategori_A.equivalent_to.append(
            OP_PenerimaPPh21_PegawaiTetap & (
                (isKawin.value(False) & hasJumlahTanggungan.some(ConstrainedDatatype(int, min_inclusive=0, max_inclusive=1)))
                | (isKawin.value(True) & hasJumlahTanggungan.value(0))
            )
        )
        OP_TER_Kategori_B.equivalent_to.append(
            OP_PenerimaPPh21_PegawaiTetap & (
                (isKawin.value(False) & hasJumlahTanggungan.some(ConstrainedDatatype(int, min_inclusive=2, max_inclusive=3)))
                | (isKawin.value(True) & hasJumlahTanggungan.some(ConstrainedDatatype(int, min_inclusive=1, max_inclusive=2)))
            )
        )
        OP_TER_Kategori_C.equivalent_to.append(
            OP_PenerimaPPh21_PegawaiTetap & isKawin.value(True) & hasJumlahTanggungan.value(3)
        )

        # 5 Lapisan Tarif Progresif PPh OP Pasal 17 ayat (1) huruf a (UU 7/2021 HPP)
        OP_PPh17_Layer1_5Pct.equivalent_to.append(
            OrangPribadi & hasPenghasilanKenaPajakTahunan.some(ConstrainedDatatype(float, min_exclusive=0.0))
        )
        OP_PPh17_Layer2_15Pct.equivalent_to.append(
            OrangPribadi & hasPenghasilanKenaPajakTahunan.some(ConstrainedDatatype(float, min_exclusive=60000000.0))
        )
        OP_PPh17_Layer3_25Pct.equivalent_to.append(
            OrangPribadi & hasPenghasilanKenaPajakTahunan.some(ConstrainedDatatype(float, min_exclusive=250000000.0))
        )
        OP_PPh17_Layer4_30Pct.equivalent_to.append(
            OrangPribadi & hasPenghasilanKenaPajakTahunan.some(ConstrainedDatatype(float, min_exclusive=500000000.0))
        )
        OP_PPh17_Layer5_35Pct.equivalent_to.append(
            OrangPribadi & hasPenghasilanKenaPajakTahunan.some(ConstrainedDatatype(float, min_exclusive=5000000000.0))
        )

        # Syarat lengkap PT Tbk 19% (UU PPh Pasal 17(2b) & PP 30/2020)
        BadanTerbukaTbk.equivalent_to.append(
            PT & isPerseroanTerbuka.value(True)
            & hasPersentaseSahamPublik.some(ConstrainedDatatype(float, min_inclusive=40.0))
            & hasJumlahPemegangSahamPublik.some(ConstrainedDatatype(int, min_inclusive=300))
            & hasHariTerpenuhiTbk.some(ConstrainedDatatype(int, min_inclusive=183))
        )

        # Tax Holiday PMK-2020-130 (Pasal 2 & Pasal 3: Badan Hukum Indonesia PT/Koperasi + SKF + belum pernah putus)
        LayakTaxHoliday_50Pct_5Thn.equivalent_to.append(
            BadanHukumIndonesia & isIndustriPionir.value(True) & isPenanamanModalBaru.value(True)
            & hasSuratKeteranganFiskal.value(True) & isBelumPernahPutusTaxHoliday.value(True)
            & hasNilaiInvestasi.some(ConstrainedDatatype(float, min_inclusive=100000000000.0, max_exclusive=500000000000.0))
        )
        LayakTaxHoliday_100Pct_5Thn.equivalent_to.append(
            BadanHukumIndonesia & isIndustriPionir.value(True) & isPenanamanModalBaru.value(True)
            & hasSuratKeteranganFiskal.value(True) & isBelumPernahPutusTaxHoliday.value(True)
            & hasNilaiInvestasi.some(ConstrainedDatatype(float, min_inclusive=500000000000.0, max_exclusive=1000000000000.0))
        )
        LayakTaxHoliday_100Pct_7Thn.equivalent_to.append(
            BadanHukumIndonesia & isIndustriPionir.value(True) & isPenanamanModalBaru.value(True)
            & hasSuratKeteranganFiskal.value(True) & isBelumPernahPutusTaxHoliday.value(True)
            & hasNilaiInvestasi.some(ConstrainedDatatype(float, min_inclusive=1000000000000.0, max_exclusive=5000000000000.0))
        )
        LayakTaxHoliday_100Pct_10Thn.equivalent_to.append(
            BadanHukumIndonesia & isIndustriPionir.value(True) & isPenanamanModalBaru.value(True)
            & hasSuratKeteranganFiskal.value(True) & isBelumPernahPutusTaxHoliday.value(True)
            & hasNilaiInvestasi.some(ConstrainedDatatype(float, min_inclusive=5000000000000.0, max_exclusive=15000000000000.0))
        )
        LayakTaxHoliday_100Pct_15Thn.equivalent_to.append(
            BadanHukumIndonesia & isIndustriPionir.value(True) & isPenanamanModalBaru.value(True)
            & hasSuratKeteranganFiskal.value(True) & isBelumPernahPutusTaxHoliday.value(True)
            & hasNilaiInvestasi.some(ConstrainedDatatype(float, min_inclusive=15000000000000.0, max_exclusive=30000000000000.0))
        )
        LayakTaxHoliday_100Pct_20Thn.equivalent_to.append(
            BadanHukumIndonesia & isIndustriPionir.value(True) & isPenanamanModalBaru.value(True)
            & hasSuratKeteranganFiskal.value(True) & isBelumPernahPutusTaxHoliday.value(True)
            & hasNilaiInvestasi.some(ConstrainedDatatype(float, min_inclusive=30000000000000.0))
        )

        # Wilayah Pajak Daerah (5 Perda Pilot)
        WP_Wilayah_DKI.equivalent_to.append(WajibPajak & (berdomisiliDi.value(w_dki) | isDomisiliDKI.value(True)))
        WP_Wilayah_Jabar.equivalent_to.append(WajibPajak & berdomisiliDi.value(w_jabar))
        WP_Wilayah_Surabaya.equivalent_to.append(WajibPajak & berdomisiliDi.value(w_sby))
        WP_Wilayah_Semarang.equivalent_to.append(WajibPajak & berdomisiliDi.value(w_smg))
        WP_Wilayah_Bali.equivalent_to.append(WajibPajak & berdomisiliDi.value(w_bali))
        WP_Wilayah_Nasional_NonDKI.equivalent_to.append(WajibPajak & berdomisiliDi.value(w_non_dki))
        WP_Wilayah_NonDKI_Kendaraan.equivalent_to.append(
            Or([WP_Wilayah_Jabar, WP_Wilayah_Surabaya, WP_Wilayah_Semarang, WP_Wilayah_Bali, WP_Wilayah_Nasional_NonDKI])
            & hasJumlahKendaraan.some(ConstrainedDatatype(int, min_inclusive=1))
        )

        # PKB DKI Jakarta (Perda DKI 1/2024 Pasal 7): OP Progresif 2%-6%, Badan Flat 2%
        Badan_PemilikKendaraanDKI.equivalent_to.append(
            WP_Wilayah_DKI & Badan & hasJumlahKendaraan.some(ConstrainedDatatype(int, min_inclusive=1))
        )
        OP_KendaraanKe1_DKI.equivalent_to.append(
            WP_Wilayah_DKI & OrangPribadi & isMilikPribadi.value(True) & hasJumlahKendaraan.value(1)
        )
        OP_KendaraanKe2_DKI.equivalent_to.append(
            WP_Wilayah_DKI & OrangPribadi & isMilikPribadi.value(True) & hasJumlahKendaraan.value(2)
        )
        OP_KendaraanKe3_DKI.equivalent_to.append(
            WP_Wilayah_DKI & OrangPribadi & isMilikPribadi.value(True) & hasJumlahKendaraan.value(3)
        )
        OP_KendaraanKe4_DKI.equivalent_to.append(
            WP_Wilayah_DKI & OrangPribadi & isMilikPribadi.value(True) & hasJumlahKendaraan.value(4)
        )
        OP_KendaraanKe5Plus_DKI.equivalent_to.append(
            WP_Wilayah_DKI & OrangPribadi & isMilikPribadi.value(True)
            & hasJumlahKendaraan.some(ConstrainedDatatype(int, min_inclusive=5))
        )

        # PKB Jawa Barat (Perda Jabar 9/2023 Pasal 7) + Opsen PKB 66%
        Badan_PemilikKendaraanJabar.equivalent_to.append(
            WP_Wilayah_Jabar & Badan & hasJumlahKendaraan.some(ConstrainedDatatype(int, min_inclusive=1))
        )
        OP_KendaraanKe1_Jabar.equivalent_to.append(
            WP_Wilayah_Jabar & OrangPribadi & isMilikPribadi.value(True) & hasJumlahKendaraan.value(1)
        )
        OP_KendaraanKe2_Jabar.equivalent_to.append(
            WP_Wilayah_Jabar & OrangPribadi & isMilikPribadi.value(True) & hasJumlahKendaraan.value(2)
        )
        OP_KendaraanKe3_Jabar.equivalent_to.append(
            WP_Wilayah_Jabar & OrangPribadi & isMilikPribadi.value(True) & hasJumlahKendaraan.value(3)
        )
        OP_KendaraanKe4_Jabar.equivalent_to.append(
            WP_Wilayah_Jabar & OrangPribadi & isMilikPribadi.value(True) & hasJumlahKendaraan.value(4)
        )
        OP_KendaraanKe5Plus_Jabar.equivalent_to.append(
            WP_Wilayah_Jabar & OrangPribadi & isMilikPribadi.value(True)
            & hasJumlahKendaraan.some(ConstrainedDatatype(int, min_inclusive=5))
        )

        # PBB-P2 Progresif 6 Lapis Kota Surabaya (Perda Surabaya 7/2023 Pasal 8)
        WP_PBB_Surabaya_L1.equivalent_to.append(
            WP_Wilayah_Surabaya & isMemilikiObjekPBB.value(True)
            & hasNilaiNJOP.some(ConstrainedDatatype(float, min_inclusive=100000000.0, max_inclusive=200000000.0))
        )
        WP_PBB_Surabaya_L2.equivalent_to.append(
            WP_Wilayah_Surabaya & isMemilikiObjekPBB.value(True)
            & hasNilaiNJOP.some(ConstrainedDatatype(float, min_exclusive=200000000.0, max_inclusive=1000000000.0))
        )
        WP_PBB_Surabaya_L3.equivalent_to.append(
            WP_Wilayah_Surabaya & isMemilikiObjekPBB.value(True)
            & hasNilaiNJOP.some(ConstrainedDatatype(float, min_exclusive=1000000000.0, max_inclusive=2000000000.0))
        )
        WP_PBB_Surabaya_L4.equivalent_to.append(
            WP_Wilayah_Surabaya & isMemilikiObjekPBB.value(True)
            & hasNilaiNJOP.some(ConstrainedDatatype(float, min_exclusive=2000000000.0, max_inclusive=10000000000.0))
        )
        WP_PBB_Surabaya_L5.equivalent_to.append(
            WP_Wilayah_Surabaya & isMemilikiObjekPBB.value(True)
            & hasNilaiNJOP.some(ConstrainedDatatype(float, min_exclusive=10000000000.0, max_inclusive=50000000000.0))
        )
        WP_PBB_Surabaya_L6.equivalent_to.append(
            WP_Wilayah_Surabaya & isMemilikiObjekPBB.value(True)
            & hasNilaiNJOP.some(ConstrainedDatatype(float, min_exclusive=50000000000.0))
        )

        # PKB Provinsi Bali (Perda Bali 1/2024 Pasal 8: <=200cc vs >200cc)
        OP_Kendaraan_Bali_Max200cc.equivalent_to.append(
            WP_Wilayah_Bali & OrangPribadi & hasJumlahKendaraan.some(ConstrainedDatatype(int, min_inclusive=1))
            & hasKapasitasMesinCC.some(ConstrainedDatatype(int, min_inclusive=1, max_inclusive=200))
        )
        OP_Kendaraan_Bali_Over200cc.equivalent_to.append(
            WP_Wilayah_Bali & OrangPribadi & hasJumlahKendaraan.some(ConstrainedDatatype(int, min_inclusive=1))
            & hasKapasitasMesinCC.some(ConstrainedDatatype(int, min_exclusive=200))
        )

        # PPh Pasal 23 + Penalti Non-NPWP +100% (UU PPh Pasal 23)
        PenerimaPPh23_NonBank_JasaSewa.equivalent_to.append(
            WajibPajak & isPenerimaPenghasilanPPh23_JasaSewa.value(True) & isBankPenerimaPenghasilan.value(False)
        )
        PenerimaPPh23_NonBank_Modal.equivalent_to.append(
            WajibPajak & isPenerimaPenghasilanPPh23_Modal.value(True) & isBankPenerimaPenghasilan.value(False)
        )
        WP_PPh23_TanpaNPWP.equivalent_to.append(
            Or([PenerimaPPh23_NonBank_JasaSewa, PenerimaPPh23_NonBank_Modal]) & hasNPWP.value(False)
        )

        # PPh Final Pasal 4 ayat (2) (PP 34/2017, PP 131/2000, PP 51/2008 jo. PP 9/2022, PP 34/2016)
        WP_PenerimaSewaTanahBangunan.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(SewaTanahDanBangunan)
        )
        WP_Pengecualian_SewaPenginapan.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(SewaTanahDanBangunan) & isJasaAkomodasiPenginapan.value(True)
        )
        WP_PenerimaBungaDeposito.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(ObjekBungaDepositoTabunganUmum)
        )
        WP_PenerimaBungaDepositoDHE_USD.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(ObjekDepositoDHE_USD)
        )
        WP_Pengecualian_Deposito_Max7_5Jt.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(BungaDepositoDanTabungan)
            & hasPokokDepositoTabungan.some(ConstrainedDatatype(float, max_inclusive=7500000.0))
        )
        WP_Pengecualian_Deposito_DibawahPTKP.equivalent_to.append(
            OrangPribadi & memilikiPenghasilanFinal.some(BungaDepositoDanTabungan) & isPenghasilanDibawahPTKP.value(True)
        )
        WP_PenyediaJasaKonstruksi.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(JasaKonstruksi)
        )
        WP_JasaKonstruksi_Kecil_SBU.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(JasaKonstruksiPekerjaanKecilSBU)
        )
        WP_JasaKonstruksi_NonKecil_SBU.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(JasaKonstruksiPekerjaanNonKecilSBU)
        )
        WP_JasaKonstruksi_Terintegrasi_SBU.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(JasaKonstruksiTerintegrasiSBU)
        )
        WP_JasaKonstruksi_TanpaSBU.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(JasaKonstruksiPekerjaanTanpaSBU)
        )
        WP_JasaKonstruksi_Terintegrasi_TanpaSBU.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(JasaKonstruksiTerintegrasiTanpaSBU)
        )
        WP_JasaKonstruksi_Konsultansi_SBU.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(JasaKonstruksiKonsultansiSBU)
        )
        WP_JasaKonstruksi_Konsultansi_TanpaSBU.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(JasaKonstruksiKonsultansiTanpaSBU)
        )
        WP_PengalihanTanahBangunan.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(PengalihanHakAtasTanahBangunan)
        )
        WP_Pengalihan_Umum_2_5Pct.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(PengalihanTanahBangunanUmum)
        )
        WP_Pengalihan_RumahSederhana_1Pct.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(PengalihanRumahSederhanaDeveloper)
        )
        WP_Pengalihan_Pemerintah_0Pct.equivalent_to.append(
            WajibPajak & memilikiPenghasilanFinal.some(PengalihanKepadaPemerintahPenugasan)
        )
        WP_Pengecualian_Pengalihan_OP_Dibawah60Jt.equivalent_to.append(
            OrangPribadi
            & memilikiPenghasilanFinal.some(PengalihanHakAtasTanahBangunan)
            & isPenghasilanDibawahPTKP.value(True)
            & hasNilaiPengalihanTanahBangunan.some(ConstrainedDatatype(float, max_exclusive=60000000.0))
        )

    return w, onto


def _create_catalog_and_swrl(onto, rules_by_id: Dict[str, dict], mk_docs: Dict[str, dict], sema_docs: Dict[str, dict]) -> dict:
    """Isi katalog Tarif/Fasilitas/Kewajiban/Sanksi + tautan provenance + aturan SWRL."""
    rule_map: Dict[str, dict] = {}
    with onto:
        # 1. Buat individu PutusanMK & SEMA_TUN
        mk_inds = {}
        for mid, md in sorted(mk_docs.items()):
            ind = onto.PutusanMK(_safe_id(mid))
            ind.hasDocumentId = mid
            ind.hasJudul = str(md.get("nomor_perkara") or mid)
            ind.hasAmarKategori = str(md.get("amar_kategori") or "")
            ind.hasSourceQuote = str(md.get("amar_lengkap") or "")[:600]
            mk_inds[mid] = ind

        sema_inds = {}
        for sid, sd in sorted(sema_docs.items()):
            ind = onto.SEMA_TUN(_safe_id(sid))
            ind.hasDocumentId = sid
            ind.hasJudul = str(sd.get("judul_rumusan") or sid)[:220]
            ind.hasKaidahStatus = str(sd.get("status_kaidah") or "AKTIF")
            ind.hasSourceQuote = str(sd.get("teks") or "")[:600]
            sema_inds[sid] = ind

        reg_cache: Dict[str, Thing] = {}
        pasal_cache: Dict[str, Thing] = {}
        aturan_cache: Dict[str, Thing] = {}

        def ensure_reg(doc_id: str):
            if doc_id not in reg_cache:
                cls = getattr(onto, _doc_subclass_name(doc_id))
                r_ind = cls(_safe_id(f"Reg_{doc_id}"))
                r_ind.hasDocumentId = doc_id
                r_ind.label = [doc_id]
                reg_cache[doc_id] = r_ind
            return reg_cache[doc_id]

        def ensure_pasal(doc_id: str, loc: str):
            if loc not in pasal_cache:
                p_ind = onto.Pasal(_safe_id(f"Pasal_{loc}"))
                p_ind.hasSourceLocator = loc
                p_ind.bagianDariRegulasi.append(ensure_reg(doc_id))
                p_ind.label = [loc]
                pasal_cache[loc] = p_ind
            return pasal_cache[loc]

        def ensure_aturan(rule_id: str, fallback_doc: str, fallback_loc: str):
            if rule_id in aturan_cache:
                return aturan_cache[rule_id]
            r = rules_by_id.get(rule_id)
            doc_id = r["document_id"] if r else fallback_doc
            loc = r["source_locator"] if r else fallback_loc
            rtype = r.get("rule_type", "other") if r else "other"
            cls = getattr(onto, _rule_subclass_name(rtype))
            a_ind = cls(_safe_id(f"Aturan_{rule_id}"))
            a_ind.hasRuleId = rule_id
            a_ind.hasSourceLocator = loc
            a_ind.hasSourceQuote = (r.get("source_quote") or "")[:800] if r else ""
            a_ind.hasStatusValidasi = (r.get("validation_status") or "") if r else "CURATED"
            if r and r.get("human_notes"):
                a_ind.hasCatatanMKSEMA = str(r["human_notes"])[:500]
            a_ind.diaturDalam.append(ensure_reg(doc_id))
            a_ind.diaturDalamPasal.append(ensure_pasal(doc_id, loc))
            if r:
                for mid in r.get("mk_review_refs") or []:
                    if mid in mk_inds:
                        a_ind.terdampakPutusanMK.append(mk_inds[mid])
                for sid in r.get("sema_tun_refs") or []:
                    if sid in sema_inds:
                        a_ind.merujukSEMA.append(sema_inds[sid])
            aturan_cache[rule_id] = a_ind
            return a_ind

        # 2. Buat katalog konsep pajak & tautkan ke AturanHukum -> Pasal -> Regulasi
        for cat_cls_name, cat_id, lbl, pct, rid, fb_doc, fb_loc in CORE_RULE_SPECS:
            cat_cls = getattr(onto, cat_cls_name)
            c_ind = cat_cls(cat_id)
            c_ind.label = [lbl]
            if pct is not None and cat_cls_name in ("TarifPajak", "TarifProgresif", "TarifFinal"):
                c_ind.hasTarifPersen = float(pct)
            if cat_id == "Sanksi_Denda_KUP_SPT_OP_100Rb":
                c_ind.hasNominalSanksi = 100_000.0
            elif cat_id == "Sanksi_Denda_KUP_SPT_Badan_1Jt":
                c_ind.hasNominalSanksi = 1_000_000.0
            elif cat_id == "Sanksi_Denda_KUP_SPT_MasaPPN_500Rb":
                c_ind.hasNominalSanksi = 500_000.0
            a_ind = ensure_aturan(rid, fb_doc, fb_loc)
            c_ind.didasarkanPadaAturan.append(a_ind)
            if cat_id == "Fasilitas_Pengecualian_SpaKesehatanTradisional_MK" and "MK-2024-19-PUU-XXII" in mk_inds:
                a_ind.terdampakPutusanMK.append(mk_inds["MK-2024-19-PUU-XXII"])
            r_src = rules_by_id.get(rid, {})
            rule_map[cat_id] = {
                "catalog_class": cat_cls_name,
                "label": lbl,
                "rule_id": rid,
                "document_id": r_src.get("document_id", fb_doc),
                "source_locator": r_src.get("source_locator", fb_loc),
                "source_quote": r_src.get("source_quote", ""),
                "mk_review_refs": r_src.get("mk_review_refs", []),
                "sema_tun_refs": r_src.get("sema_tun_refs", []),
            }

        # 2b. Katalog Individu JenisPekerjaan (PMK-2023-168 Pasal 3 & PP-2022-55 Pasal 56(4))
        job_specs = [
            ("PekerjaanPegawaiTetap", "PegawaiTetap_Swasta", "Pegawai Tetap Swasta / BUMN"),
            ("PekerjaanPegawaiTetap", "PNS_TNI_Polri_Pejabat", "PNS / TNI / Polri / Pejabat Negara"),
            ("PekerjaanPegawaiTetap", "Pensiunan", "Pensiunan Penerima Uang Pensiun Berkala"),
            ("PekerjaanPegawaiTetap", "Dewan_Komisaris_Pengawas", "Anggota Dewan Komisaris / Dewan Pengawas"),
            ("PekerjaanPegawaiTetap", "Mantan_Pegawai", "Mantan Pegawai (Jasa Produksi / Tantiem / Bonus)"),
            ("PekerjaanPegawaiTidakTetap", "Pegawai_Tidak_Tetap_Harian", "Pegawai Tidak Tetap / Tenaga Kerja Lepas Harian"),
            ("PekerjaanPesertaKegiatan", "Peserta_Kegiatan_Lomba_Seminar_Magang", "Peserta Kegiatan (Lomba / Seminar / Kepanitiaan / Magang)"),
            ("PekerjaanBebas", "Dokter", "Tenaga Ahli - Dokter"),
            ("PekerjaanBebas", "Pengacara", "Tenaga Ahli - Pengacara / Advokat"),
            ("PekerjaanBebas", "Akuntan", "Tenaga Ahli - Akuntan"),
            ("PekerjaanBebas", "Arsitek", "Tenaga Ahli - Arsitek"),
            ("PekerjaanBebas", "Konsultan", "Tenaga Ahli - Konsultan"),
            ("PekerjaanBebas", "Notaris_PPAT", "Tenaga Ahli - Notaris / PPAT"),
            ("PekerjaanBebas", "Penilai_Aktuaris", "Tenaga Ahli - Penilai / Aktuaris"),
            ("PekerjaanBebas", "Influencer_KontenKreator", "Pembuat Konten Daring (Influencer / Selebgram / Blogger / Vlogger)"),
            ("PekerjaanBebas", "Seniman_Musisi_Aktor", "Pekerja Seni (Pemusik / Penyanyi / MC / Aktor / Pelukis / Sutradara)"),
            ("PekerjaanBebas", "Olahragawan", "Olahragawan"),
            ("PekerjaanBebas", "Pengajar_Pelatih_Pembicara", "Penasihat / Pengajar / Pelatih / Penceramah / Moderator"),
            ("PekerjaanBebas", "Penulis_Peneliti_Penerjemah", "Pengarang / Peneliti / Penerjemah"),
            ("PekerjaanBebas", "Agen_Iklan", "Agen Iklan"),
            ("PekerjaanBebas", "Pengelola_Proyek", "Pengawas atau Pengelola Proyek"),
            ("PekerjaanBebas", "Perantara_Broker", "Perantara / Pembawa Pesanan / Broker"),
            ("PekerjaanBebas", "Sales_Penjaja_Barang", "Petugas Penjaja Barang Dagangan"),
            ("PekerjaanBebas", "Agen_Asuransi", "Agen Asuransi"),
            ("PekerjaanBebas", "Distributor_MLM", "Distributor Pemasaran Berjenjang (MLM / Penjualan Langsung)"),
            ("UsahaDagangJasa", "Pedagang_ECommerce", "Pedagang Niaga Elektronik (E-Commerce / Marketplace)"),
            ("UsahaDagangJasa", "Pedagang_Ritel_Grosir", "Pedagang Eceran / Grosir / Toko"),
            ("UsahaDagangJasa", "Usaha_Kuliner_Warung", "Usaha Kuliner / Warung / Kafe"),
            ("UsahaDagangJasa", "Bengkel_Konveksi_Kerajinan", "Usaha Bengkel / Konveksi / Pengrajin"),
            ("UsahaDagangJasa", "Penyedia_Jasa_Umum", "Penyedia Jasa Umum Non-Pekerjaan Bebas"),
        ]
        for j_cls_name, j_id, j_lbl in job_specs:
            j_cls = getattr(onto, j_cls_name)
            j_ind = j_cls(j_id)
            j_ind.label = [j_lbl]

        # 2c. Katalog Individu ObjekPenghasilanFinal Pasal 4(2)
        final_obj_specs = [
            ("SewaTanahDanBangunan", "Jenis_SewaTanahBangunan", "Persewaan Tanah dan/atau Bangunan (PP 34/2017 - PPh Final 10%)"),
            ("ObjekBungaDepositoTabunganUmum", "Jenis_BungaDepositoTabungan", "Bunga Deposito, Tabungan & Diskonto SBI Umum (PP 131/2000 - PPh Final 20%)"),
            ("ObjekDepositoDHE_USD", "Jenis_DepositoDHE_USD", "Bunga Deposito Devisa Hasil Ekspor (DHE) USD (PP 131/2000 jo. PP 123/2015 - 0% s.d. 10%)"),
            ("JasaKonstruksiPekerjaanKecilSBU", "Jenis_JasaKonstruksi_Kecil_SBU", "Jasa Konstruksi - Pekerjaan Konstruksi Kualifikasi Kecil / SKK (PP 9/2022 - 1,75%)"),
            ("JasaKonstruksiPekerjaanNonKecilSBU", "Jenis_JasaKonstruksi_NonKecil_SBU", "Jasa Konstruksi - Pekerjaan Konstruksi Menengah/Besar Bersertifikat (PP 9/2022 - 2,65%)"),
            ("JasaKonstruksiTerintegrasiSBU", "Jenis_JasaKonstruksi_Terintegrasi_SBU", "Jasa Konstruksi - Pekerjaan Konstruksi Terintegrasi Bersertifikat SBU (PP 9/2022 - 2,65%)"),
            ("JasaKonstruksiPekerjaanTanpaSBU", "Jenis_JasaKonstruksi_TanpaSBU", "Jasa Konstruksi - Pekerjaan Konstruksi Tanpa Sertifikat SBU/SKK (PP 9/2022 - 4%)"),
            ("JasaKonstruksiTerintegrasiTanpaSBU", "Jenis_JasaKonstruksi_Terintegrasi_TanpaSBU", "Jasa Konstruksi - Pekerjaan Terintegrasi Tanpa SBU (PP 9/2022 - 4%)"),
            ("JasaKonstruksiKonsultansiSBU", "Jenis_JasaKonstruksi_Konsultansi_SBU", "Jasa Konstruksi - Jasa Konsultansi Bersertifikat SBU/SKK (PP 9/2022 - 3,5%)"),
            ("JasaKonstruksiKonsultansiTanpaSBU", "Jenis_JasaKonstruksi_Konsultansi_TanpaSBU", "Jasa Konstruksi - Jasa Konsultansi Tanpa Sertifikat SBU/SKK (PP 9/2022 - 6%)"),
            ("PengalihanTanahBangunanUmum", "Jenis_PengalihanTanahBangunan_Umum", "Pengalihan Hak atas Tanah dan/atau Bangunan Umum (PP 34/2016 - 2,5%)"),
            ("PengalihanRumahSederhanaDeveloper", "Jenis_PengalihanRumahSederhana", "Pengalihan Rumah Sederhana / Rusunami oleh Developer (PP 34/2016 - 1%)"),
            ("PengalihanKepadaPemerintahPenugasan", "Jenis_PengalihanKepadaPemerintah", "Pengalihan Tanah/Bangunan kepada Pemerintah/BUMN/BUMD Penugasan Khusus (PP 34/2016 - 0%)"),
        ]
        for f_cls_name, f_id, f_lbl in final_obj_specs:
            f_cls = getattr(onto, f_cls_name)
            f_ind = f_cls(f_id)
            f_ind.label = [f_lbl]

        # Tautkan contoh rantai rujukan regulasi (TransitiveProperty merujukDokumen -> S dalam SROIQ)
        r_pmk131 = ensure_reg("PMK-2024-131")
        r_pmk164 = ensure_reg("PMK-2023-164")
        r_pp55 = ensure_reg("PP-2022-55")
        r_uu_hpp = ensure_reg("UU-2021-7")
        r_uu_pph = ensure_reg("UU-1983-7")
        r_uu_ppn = ensure_reg("UU-1983-8")
        r_pmk131.merujukDokumen.append(r_uu_hpp)
        r_uu_hpp.merujukDokumen.append(r_uu_ppn)
        r_pmk164.merujukDokumen.append(r_pp55)
        r_pp55.merujukDokumen.append(r_uu_hpp)
        r_uu_hpp.merujukDokumen.append(r_uu_pph)

        # 3. Tambahkan pula ~50 individu AturanHukum inti terkurasi (P1-P6 HUMAN_FIXED / HUMAN_APPROVED)
        # agar ABox reasoning tetap kaya namun HermiT tetap responsif.
        curated_extras = [
            r for r in rules_by_id.values()
            if r.get("validation_status") in ("HUMAN_FIXED", "HUMAN_APPROVED")
            and r.get("rule_type") in ("rate", "sanction", "exception", "eligibility", "deadline", "right")
        ][:50]
        for r in curated_extras:
            ensure_aturan(r["rule_id"], r["document_id"], r["source_locator"])

        # 4. Aturan SWRL DL-safe (menautkan hasil klasifikasi SROIQ(D) -> katalog ber-provenance)
        swrl_defs = [
            ("SWRL_TK_A2_2_Badan_Tbk", "BadanTerbukaTbk(?wp) -> dikenaiTarif(?wp, Tarif_PPhBadan_Tbk_19Pct)"),
            ("SWRL_TK_A2_2_Badan_Umum", "BadanNonTbk(?wp), WajibPajakNonUMKM(?wp) -> dikenaiTarif(?wp, Tarif_PPhBadan_22Pct)"),
            ("SWRL_TK_A2_2_Pasal31E", "BadanLayakPasal31E(?wp) -> memilikiFasilitas(?wp, Fasilitas_Pasal31E_Diskon50Pct_11Pct)"),
            ("SWRL_TK_A2_1_TaxAllowance", "BadanLayakTaxAllowance(?wp) -> memilikiFasilitas(?wp, Fasilitas_TaxAllowance_PP78_30Pct)"),
            ("SWRL_TK_A2_1_PadatKarya", "BadanLayakPadatKarya(?wp) -> memilikiFasilitas(?wp, Fasilitas_PadatKarya_PMK81_60Pct)"),
            ("SWRL_TK_OP_NPPN_Gugur", "OP_NPPN_Gugur_TelatLapor(?wp) -> memilikiKewajiban(?wp, Kewajiban_Pembukuan_OP_NPPN_Terlambat)"),
            ("SWRL_TK_D2_Norma_Pemeriksaan", "WP_TidakSelenggarakanPembukuan(?wp) -> berisikoSanksi(?wp, Sanksi_NPPN_Norma_Pemeriksaan_Pasal14_5)"),
            ("SWRL_TK_HKPD_Opsen_NonDKI", "WP_Wilayah_NonDKI_Kendaraan(?wp) -> memilikiKewajiban(?wp, Kewajiban_Opsen_PKB_66Pct)"),
            ("SWRL_TK_A2_2_BUT_BranchProfit", "BadanUsahaTetap(?wp) -> dikenaiTarif(?wp, Tarif_PPh26_4_BUT_BranchProfit_20Pct)"),
            ("SWRL_TK_A2_2_UMKM_PP55", "WajibPajakUMKM(?wp) -> memilikiFasilitas(?wp, Fasilitas_PP55_Final_0_5Pct)"),
            ("SWRL_TK_A2_2_OP_UMKM_Bebas_500Jt", "OP_UMKM_Bebas_500Jt(?wp) -> memilikiFasilitas(?wp, Fasilitas_OP_UMKM_BebasPPh_500Jt)"),
            ("SWRL_TK_A2_2_OP_UMKM_Final_500JtPlus", "OP_UMKM_Final_PP55(?wp) -> memilikiFasilitas(?wp, Fasilitas_OP_UMKM_BebasPPh_500Jt)"),
            ("SWRL_TK_A2_2_UMKM_Lewat_4_8M", "PengusahaKenaPajak(?wp), isUMKM_PP55(?wp, true) -> memilikiKewajiban(?wp, Kewajiban_Peralihan_UMKM_Ke_KetentuanUmum)"),
            ("SWRL_TK_OP_TER_A", "OP_TER_Kategori_A(?wp) -> dikenaiTarif(?wp, Tarif_PPh21_TER_Bulanan_Kategori_A), memilikiFasilitas(?wp, Fasilitas_PTKP_Dasar_Keluarga), memilikiKewajiban(?wp, Kewajiban_LaporSPT_OP_LaporSeluruhPenghasilan)"),
            ("SWRL_TK_OP_TER_B", "OP_TER_Kategori_B(?wp) -> dikenaiTarif(?wp, Tarif_PPh21_TER_Bulanan_Kategori_B), memilikiFasilitas(?wp, Fasilitas_PTKP_Dasar_Keluarga), memilikiKewajiban(?wp, Kewajiban_LaporSPT_OP_LaporSeluruhPenghasilan)"),
            ("SWRL_TK_OP_TER_C", "OP_TER_Kategori_C(?wp) -> dikenaiTarif(?wp, Tarif_PPh21_TER_Bulanan_Kategori_C), memilikiFasilitas(?wp, Fasilitas_PTKP_Dasar_Keluarga), memilikiKewajiban(?wp, Kewajiban_LaporSPT_OP_LaporSeluruhPenghasilan)"),
            ("SWRL_TK_OP_TidakTetap", "OP_PenerimaPPh21_TidakTetap(?wp) -> dikenaiTarif(?wp, Tarif_PPh21_PegawaiTidakTetap_Harian), memilikiKewajiban(?wp, Kewajiban_LaporSPT_OP_LaporSeluruhPenghasilan)"),
            ("SWRL_TK_OP_SPLN_PPh26", "OP_SubjekLuarNegeri(?wp) -> dikenaiTarif(?wp, Tarif_PPh26_OP_LuarNegeri_20Pct)"),
            ("SWRL_TK_OP_PekerjaBebas", "OP_PekerjaBebas(?wp) -> dikenaiTarif(?wp, Tarif_PPh21_BukanPegawai_DPP50Pct), memilikiKewajiban(?wp, Kewajiban_PekerjaBebas_TarifUmum_NonPP55), memilikiKewajiban(?wp, Kewajiban_LaporSPT_OP_LaporSeluruhPenghasilan)"),
            ("SWRL_TK_OP_PekerjaBebas_NPPN", "OP_PekerjaBebas_LayakNPPN(?wp) -> memilikiFasilitas(?wp, Fasilitas_NPPN_OP_Dibawah_4_8M)"),
            ("SWRL_TK_OP_WajibPembukuan", "OP_WajibPembukuan(?wp) -> memilikiKewajiban(?wp, Kewajiban_Pembukuan_OP_4_8M_KeAtas)"),
            ("SWRL_TK_OP_MultiPemberiKerja", "OP_MultiPemberiKerja(?wp) -> memilikiKewajiban(?wp, Kewajiban_Rekonsiliasi_MultiPemberiKerja)"),
            ("SWRL_TK_OP_PPh17_L1", "OP_PPh17_Layer1_5Pct(?wp) -> dikenaiTarif(?wp, Tarif_PPhOP_Layer1_5Pct)"),
            ("SWRL_TK_OP_PPh17_L2", "OP_PPh17_Layer2_15Pct(?wp) -> dikenaiTarif(?wp, Tarif_PPhOP_Layer2_15Pct)"),
            ("SWRL_TK_OP_PPh17_L3", "OP_PPh17_Layer3_25Pct(?wp) -> dikenaiTarif(?wp, Tarif_PPhOP_Layer3_25Pct)"),
            ("SWRL_TK_OP_PPh17_L4", "OP_PPh17_Layer4_30Pct(?wp) -> dikenaiTarif(?wp, Tarif_PPhOP_Layer4_30Pct)"),
            ("SWRL_TK_OP_PPh17_L5", "OP_PPh17_Layer5_35Pct(?wp) -> dikenaiTarif(?wp, Tarif_PPhOP_Layer5_35Pct)"),
            ("SWRL_TK_A2_1_TH_50_5", "LayakTaxHoliday_50Pct_5Thn(?wp) -> memilikiFasilitas(?wp, Fasilitas_TaxHoliday_50Pct_5Thn), memilikiFasilitas(?wp, Fasilitas_TaxHoliday_Transisi_25Pct_2Thn)"),
            ("SWRL_TK_A2_1_TH_100_5", "LayakTaxHoliday_100Pct_5Thn(?wp) -> memilikiFasilitas(?wp, Fasilitas_TaxHoliday_100Pct_5Thn), memilikiFasilitas(?wp, Fasilitas_TaxHoliday_Transisi_50Pct_2Thn)"),
            ("SWRL_TK_A2_1_TH_100_7", "LayakTaxHoliday_100Pct_7Thn(?wp) -> memilikiFasilitas(?wp, Fasilitas_TaxHoliday_100Pct_7Thn), memilikiFasilitas(?wp, Fasilitas_TaxHoliday_Transisi_50Pct_2Thn)"),
            ("SWRL_TK_A2_1_TH_100_10", "LayakTaxHoliday_100Pct_10Thn(?wp) -> memilikiFasilitas(?wp, Fasilitas_TaxHoliday_100Pct_10Thn), memilikiFasilitas(?wp, Fasilitas_TaxHoliday_Transisi_50Pct_2Thn)"),
            ("SWRL_TK_A2_1_TH_100_15", "LayakTaxHoliday_100Pct_15Thn(?wp) -> memilikiFasilitas(?wp, Fasilitas_TaxHoliday_100Pct_15Thn), memilikiFasilitas(?wp, Fasilitas_TaxHoliday_Transisi_50Pct_2Thn)"),
            ("SWRL_TK_A2_1_TH_100_20", "LayakTaxHoliday_100Pct_20Thn(?wp) -> memilikiFasilitas(?wp, Fasilitas_TaxHoliday_100Pct_20Thn), memilikiFasilitas(?wp, Fasilitas_TaxHoliday_Transisi_50Pct_2Thn)"),
            ("SWRL_TK_B1_PKP_PPN", "PengusahaKenaPajak(?wp) -> memilikiKewajiban(?wp, Kewajiban_DaftarPKP_PungutPPN)"),
            ("SWRL_TK_B2_PPN_Mewah_12", "PengusahaKenaPajak(?wp), isPenyerahanBKP_Mewah(?wp, true) -> dikenaiTarif(?wp, Tarif_PPN_12Pct)"),
            ("SWRL_TK_B2_PPN_NonMewah_Efektif11", "PengusahaKenaPajak(?wp), isPenyerahanNonMewahPPN(?wp, true) -> dikenaiTarif(?wp, Tarif_PPN_Efektif_11Pct)"),
            ("SWRL_TK_B2_PPN_Strategis_Bebas", "PengusahaKenaPajak(?wp), isPenyerahanBKPStrategis(?wp, true) -> memilikiFasilitas(?wp, Fasilitas_PPN_Dibebaskan_Strategis)"),
            ("SWRL_TK_PPh23_JasaSewa", "PenerimaPPh23_NonBank_JasaSewa(?wp) -> dikenaiTarif(?wp, Tarif_PPh23_JasaSewa_2Pct)"),
            ("SWRL_TK_PPh23_Modal", "PenerimaPPh23_NonBank_Modal(?wp) -> dikenaiTarif(?wp, Tarif_PPh23_Modal_15Pct)"),
            ("SWRL_TK_PPh23_Bank", "WajibPajak(?wp), isBankPenerimaPenghasilan(?wp, true) -> memilikiFasilitas(?wp, Fasilitas_Pengecualian_PPh23_Bank)"),
            ("SWRL_TK_PPh23_NonNPWP", "WP_PPh23_TanpaNPWP(?wp) -> berisikoSanksi(?wp, Sanksi_PPh23_Kenaikan100Pct_NonNPWP)"),
            # PPh Final Pasal 4 ayat (2) (PP 34/2017, PP 131/2000, PP 51/2008 jo. PP 9/2022, PP 34/2016)
            ("SWRL_TK_PPh4_2_SewaTanahBangunan", "WP_PenerimaSewaTanahBangunan(?wp) -> dikenaiTarif(?wp, Tarif_PPhFinal_SewaTanahBangunan_10Pct), memilikiKewajiban(?wp, Kewajiban_PotongSetor_SewaTanahBangunan)"),
            ("SWRL_TK_PPh4_2_SewaPenginapan_Pengecualian", "WP_Pengecualian_SewaPenginapan(?wp) -> memilikiFasilitas(?wp, Fasilitas_Pengecualian_SewaPenginapan_PP34)"),
            ("SWRL_TK_PPh4_2_BungaDeposito_20", "WP_PenerimaBungaDeposito(?wp) -> dikenaiTarif(?wp, Tarif_PPhFinal_BungaDepositoTabungan_20Pct)"),
            ("SWRL_TK_PPh4_2_Deposito_DHE_USD", "WP_PenerimaBungaDepositoDHE_USD(?wp) -> dikenaiTarif(?wp, Tarif_PPhFinal_DepositoDHE_USD_Bertingkat)"),
            ("SWRL_TK_PPh4_2_Deposito_Max7_5Jt", "WP_Pengecualian_Deposito_Max7_5Jt(?wp) -> memilikiFasilitas(?wp, Fasilitas_Pengecualian_Deposito_Dibawah_7_5Jt)"),
            ("SWRL_TK_PPh4_2_Deposito_DibawahPTKP", "WP_Pengecualian_Deposito_DibawahPTKP(?wp) -> memilikiFasilitas(?wp, Fasilitas_Restitusi_BungaDeposito_DibawahPTKP)"),
            ("SWRL_TK_PPh4_2_Konstruksi_KecilSBU", "WP_JasaKonstruksi_Kecil_SBU(?wp) -> dikenaiTarif(?wp, Tarif_PPhFinal_Konstruksi_KecilSBU_1_75Pct)"),
            ("SWRL_TK_PPh4_2_Konstruksi_NonKecilSBU", "WP_JasaKonstruksi_NonKecil_SBU(?wp) -> dikenaiTarif(?wp, Tarif_PPhFinal_Konstruksi_NonKecilSBU_2_65Pct)"),
            ("SWRL_TK_PPh4_2_Konstruksi_TerintegrasiSBU", "WP_JasaKonstruksi_Terintegrasi_SBU(?wp) -> dikenaiTarif(?wp, Tarif_PPhFinal_Konstruksi_TerintegrasiSBU_2_65Pct)"),
            ("SWRL_TK_PPh4_2_Konstruksi_TanpaSBU", "WP_JasaKonstruksi_TanpaSBU(?wp) -> dikenaiTarif(?wp, Tarif_PPhFinal_Konstruksi_TanpaSBU_4Pct)"),
            ("SWRL_TK_PPh4_2_Konstruksi_TerintegrasiTanpaSBU", "WP_JasaKonstruksi_Terintegrasi_TanpaSBU(?wp) -> dikenaiTarif(?wp, Tarif_PPhFinal_Konstruksi_TerintegrasiTanpaSBU_4Pct)"),
            ("SWRL_TK_PPh4_2_Konstruksi_KonsultansiSBU", "WP_JasaKonstruksi_Konsultansi_SBU(?wp) -> dikenaiTarif(?wp, Tarif_PPhFinal_Konstruksi_KonsultansiSBU_3_5Pct)"),
            ("SWRL_TK_PPh4_2_Konstruksi_KonsultansiTanpaSBU", "WP_JasaKonstruksi_Konsultansi_TanpaSBU(?wp) -> dikenaiTarif(?wp, Tarif_PPhFinal_Konstruksi_KonsultansiTanpaSBU_6Pct)"),
            ("SWRL_TK_PPh4_2_Konstruksi_PencatatanTerpisah", "WP_PenyediaJasaKonstruksi(?wp) -> memilikiKewajiban(?wp, Kewajiban_PencatatanTerpisah_JasaKonstruksi)"),
            ("SWRL_TK_PPh4_2_Pengalihan_Umum", "WP_Pengalihan_Umum_2_5Pct(?wp) -> dikenaiTarif(?wp, Tarif_PPhFinal_PengalihanTanahBangunan_2_5Pct), memilikiKewajiban(?wp, Kewajiban_SetorSSP_ValidasiKPP_SebelumAkta)"),
            ("SWRL_TK_PPh4_2_Pengalihan_RumahSederhana", "WP_Pengalihan_RumahSederhana_1Pct(?wp) -> dikenaiTarif(?wp, Tarif_PPhFinal_PengalihanRumahSederhana_1Pct), memilikiKewajiban(?wp, Kewajiban_SetorSSP_ValidasiKPP_SebelumAkta)"),
            ("SWRL_TK_PPh4_2_Pengalihan_Pemerintah", "WP_Pengalihan_Pemerintah_0Pct(?wp) -> dikenaiTarif(?wp, Tarif_PPhFinal_PengalihanKepadaPemerintah_0Pct)"),
            ("SWRL_TK_PPh4_2_Pengalihan_OP_Dibawah60Jt", "WP_Pengecualian_Pengalihan_OP_Dibawah60Jt(?wp) -> memilikiFasilitas(?wp, Fasilitas_Pengecualian_Pengalihan_OP_Dibawah60Jt_PTKP)"),
            ("SWRL_TK_C1_PBB_DKI", "WP_Wilayah_DKI(?wp), isMemilikiObjekPBB(?wp, true) -> memilikiKewajiban(?wp, Kewajiban_LaporPBB), dikenaiTarif(?wp, Tarif_PBB_DKI_0_5Pct)"),
            ("SWRL_TK_C1_PBB_Semarang", "WP_Wilayah_Semarang(?wp), isMemilikiObjekPBB(?wp, true) -> memilikiKewajiban(?wp, Kewajiban_LaporPBB), dikenaiTarif(?wp, Tarif_PBB_Semarang_0_3Pct)"),
            ("SWRL_TK_C1_PBB_Nasional_NonDKI", "WP_Wilayah_Nasional_NonDKI(?wp), isMemilikiObjekPBB(?wp, true) -> memilikiKewajiban(?wp, Kewajiban_LaporPBB)"),
            ("SWRL_TK_C1_PBB_Surabaya_L1", "WP_PBB_Surabaya_L1(?wp) -> memilikiKewajiban(?wp, Kewajiban_LaporPBB), dikenaiTarif(?wp, Tarif_PBB_Surabaya_L1_0_05Pct)"),
            ("SWRL_TK_C1_PBB_Surabaya_L2", "WP_PBB_Surabaya_L2(?wp) -> memilikiKewajiban(?wp, Kewajiban_LaporPBB), dikenaiTarif(?wp, Tarif_PBB_Surabaya_L2_0_10Pct)"),
            ("SWRL_TK_C1_PBB_Surabaya_L3", "WP_PBB_Surabaya_L3(?wp) -> memilikiKewajiban(?wp, Kewajiban_LaporPBB), dikenaiTarif(?wp, Tarif_PBB_Surabaya_L3_0_15Pct)"),
            ("SWRL_TK_C1_PBB_Surabaya_L4", "WP_PBB_Surabaya_L4(?wp) -> memilikiKewajiban(?wp, Kewajiban_LaporPBB), dikenaiTarif(?wp, Tarif_PBB_Surabaya_L4_0_20Pct)"),
            ("SWRL_TK_C1_PBB_Surabaya_L5", "WP_PBB_Surabaya_L5(?wp) -> memilikiKewajiban(?wp, Kewajiban_LaporPBB), dikenaiTarif(?wp, Tarif_PBB_Surabaya_L5_0_25Pct)"),
            ("SWRL_TK_C1_PBB_Surabaya_L6", "WP_PBB_Surabaya_L6(?wp) -> memilikiKewajiban(?wp, Kewajiban_LaporPBB), dikenaiTarif(?wp, Tarif_PBB_Surabaya_L6_0_30Pct)"),
            ("SWRL_TK_C2_PKB_DKI_Badan", "Badan_PemilikKendaraanDKI(?wp) -> dikenaiTarif(?wp, Tarif_PKB_DKI_Badan_2Pct)"),
            ("SWRL_TK_C2_PKB_DKI_1", "OP_KendaraanKe1_DKI(?wp) -> dikenaiTarif(?wp, Tarif_PKB_DKI_Ke1_2Pct)"),
            ("SWRL_TK_C2_PKB_DKI_2", "OP_KendaraanKe2_DKI(?wp) -> dikenaiTarif(?wp, Tarif_PKB_DKI_Ke2_3Pct)"),
            ("SWRL_TK_C2_PKB_DKI_3", "OP_KendaraanKe3_DKI(?wp) -> dikenaiTarif(?wp, Tarif_PKB_DKI_Ke3_4Pct)"),
            ("SWRL_TK_C2_PKB_DKI_4", "OP_KendaraanKe4_DKI(?wp) -> dikenaiTarif(?wp, Tarif_PKB_DKI_Ke4_5Pct)"),
            ("SWRL_TK_C2_PKB_DKI_5Plus", "OP_KendaraanKe5Plus_DKI(?wp) -> dikenaiTarif(?wp, Tarif_PKB_DKI_Ke5Plus_6Pct)"),
            ("SWRL_TK_C2_PKB_Jabar_Badan", "Badan_PemilikKendaraanJabar(?wp) -> dikenaiTarif(?wp, Tarif_PKB_Jabar_Badan_NonProgresif), memilikiKewajiban(?wp, Kewajiban_Opsen_PKB_66Pct)"),
            ("SWRL_TK_C2_PKB_Jabar_1", "OP_KendaraanKe1_Jabar(?wp) -> dikenaiTarif(?wp, Tarif_PKB_Jabar_Ke1_1_12Pct), memilikiKewajiban(?wp, Kewajiban_Opsen_PKB_66Pct)"),
            ("SWRL_TK_C2_PKB_Jabar_2", "OP_KendaraanKe2_Jabar(?wp) -> dikenaiTarif(?wp, Tarif_PKB_Jabar_Ke2_1_62Pct), memilikiKewajiban(?wp, Kewajiban_Opsen_PKB_66Pct)"),
            ("SWRL_TK_C2_PKB_Jabar_3", "OP_KendaraanKe3_Jabar(?wp) -> dikenaiTarif(?wp, Tarif_PKB_Jabar_Ke3_2_12Pct), memilikiKewajiban(?wp, Kewajiban_Opsen_PKB_66Pct)"),
            ("SWRL_TK_C2_PKB_Jabar_4", "OP_KendaraanKe4_Jabar(?wp) -> dikenaiTarif(?wp, Tarif_PKB_Jabar_Ke4_2_62Pct), memilikiKewajiban(?wp, Kewajiban_Opsen_PKB_66Pct)"),
            ("SWRL_TK_C2_PKB_Jabar_5Plus", "OP_KendaraanKe5Plus_Jabar(?wp) -> dikenaiTarif(?wp, Tarif_PKB_Jabar_Ke5Plus_3_12Pct), memilikiKewajiban(?wp, Kewajiban_Opsen_PKB_66Pct)"),
            ("SWRL_TK_C2_PKB_Bali_Max200", "OP_Kendaraan_Bali_Max200cc(?wp) -> dikenaiTarif(?wp, Tarif_PKB_Bali_Max200cc_1_055Pct), memilikiKewajiban(?wp, Kewajiban_Opsen_PKB_66Pct)"),
            ("SWRL_TK_C2_PKB_Bali_Over200", "OP_Kendaraan_Bali_Over200cc(?wp) -> dikenaiTarif(?wp, Tarif_PKB_Bali_Over200cc_1_2Pct), memilikiKewajiban(?wp, Kewajiban_Opsen_PKB_66Pct)"),
            ("SWRL_TK_C2_Spa_Kesehatan_MK", "WajibPajak(?wp), isUsahaSpaKesehatanTradisional(?wp, true) -> memilikiFasilitas(?wp, Fasilitas_Pengecualian_SpaKesehatanTradisional_MK)"),
            ("SWRL_TK_C2_Spa_Hiburan_DKI", "WP_Wilayah_DKI(?wp), isUsahaHiburanSpaUmum(?wp, true) -> dikenaiTarif(?wp, Tarif_PBJT_Hiburan_DKI_40Pct)"),
            ("SWRL_TK_C2_Spa_Hiburan_Surabaya", "WP_Wilayah_Surabaya(?wp), isUsahaHiburanSpaUmum(?wp, true) -> dikenaiTarif(?wp, Tarif_PBJT_Hiburan_Surabaya_50Pct)"),
            ("SWRL_TK_D1_NIK_NPWP_OP", "OrangPribadi(?wp), isPendudukIndonesia(?wp, true) -> memilikiKewajiban(?wp, Kewajiban_NPWP_NIK_OP)"),
            ("SWRL_TK_D1_WajibSPT", "WajibPajak(?wp), hasNPWP(?wp, true) -> memilikiKewajiban(?wp, Kewajiban_LaporSPT)"),
            ("SWRL_TK_D1_TenggatSPT_OP", "OrangPribadi(?wp), hasNPWP(?wp, true) -> memilikiKewajiban(?wp, Kewajiban_Tenggat_SPT_Tahunan_OP_3Bln)"),
            ("SWRL_TK_D1_TenggatSPT_Badan", "Badan(?wp), hasNPWP(?wp, true) -> memilikiKewajiban(?wp, Kewajiban_Tenggat_SPT_Tahunan_Badan_4Bln)"),
            ("SWRL_TK_D2_Sanksi_SPT_OP", "OrangPribadi(?wp), isTerlambatLaporSPT(?wp, true) -> berisikoSanksi(?wp, Sanksi_Denda_KUP_SPT_OP_100Rb)"),
            ("SWRL_TK_D2_Sanksi_SPT_Badan", "Badan(?wp), isTerlambatLaporSPT(?wp, true) -> berisikoSanksi(?wp, Sanksi_Denda_KUP_SPT_Badan_1Jt)"),
            ("SWRL_TK_D2_Sanksi_SPT_PPN", "PengusahaKenaPajak(?wp), isTerlambatLaporSPTMasaPPN(?wp, true) -> berisikoSanksi(?wp, Sanksi_Denda_KUP_SPT_MasaPPN_500Rb)"),
            ("SWRL_TK_D2_Pengecualian_DendaSPT", "WajibPajak(?wp), isDikecualikanDendaSPT(?wp, true) -> memilikiFasilitas(?wp, Fasilitas_Pengecualian_DendaSPT_Pasal7_2)"),
            ("SWRL_TK_D2_Sanksi_SKPKB_Bunga", "WajibPajak(?wp), isKurangBayarSKPKB(?wp, true) -> berisikoSanksi(?wp, Sanksi_Bunga_SKPKB_Pasal13_2)"),
            ("SWRL_TK_D2_Sanksi_SKPKB_75", "WajibPajak(?wp), isTidakSetorPajakDipungut(?wp, true) -> berisikoSanksi(?wp, Sanksi_Kenaikan_75Pct_TidakSetor_Pasal13_3)"),
            ("SWRL_TK_D2_Sanksi_Keberatan", "WajibPajak(?wp), isKeberatanDitolak(?wp, true) -> berisikoSanksi(?wp, Sanksi_Keberatan_30Pct)"),
            ("SWRL_TK_D2_Sanksi_Banding", "WajibPajak(?wp), isBandingDitolak(?wp, true) -> berisikoSanksi(?wp, Sanksi_Banding_60Pct)"),
        ]
        for r_name, r_expr in swrl_defs:
            imp = Imp()
            imp.set_as_rule(r_expr)
            imp.label = [r_name]

    return rule_map


def _create_demo_scenarios(onto) -> None:
    """Tambahkan 8 individu skenario WajibPajak untuk demonstrasi & uji TK-A2-1..TK-E1."""
    with onto:
        # 1. Badan Umum non-Tbk omzet Rp60M (penyerahan non-mewah PPN) -> Tarif 22% + PKP + PPN 12% & Efektif 11% + Lapor SPT 4 bln
        s1 = onto.PT("PT_TechStartup_001")
        s1.hasOmzetTahunan = 60_000_000_000.0
        s1.isPerseroanTerbuka = False
        s1.isUMKM_PP55 = False
        s1.hasNPWP = True
        s1.isPenyerahanNonMewahPPN = True

        # 2. Badan Tbk saham publik 45%, >=300 pemegang saham, >=183 hari, penyerahan BKP Mewah -> Tarif 19% + PKP + PPN 12%
        s2 = onto.PT("PT_Terbuka_001")
        s2.hasOmzetTahunan = 200_000_000_000.0
        s2.isPerseroanTerbuka = True
        s2.hasPersentaseSahamPublik = 45.0
        s2.hasJumlahPemegangSahamPublik = 350
        s2.hasHariTerpenuhiTbk = 200
        s2.isPenyerahanBKP_Mewah = True
        s2.isUMKM_PP55 = False
        s2.hasNPWP = True

        # 3. Industri Pionir investasi baru Rp1,5T + SKF + belum pernah putus -> Tax Holiday 100% 7 thn + Transisi 50% 2 thn + Pasal 31E + PKP
        s3 = onto.PT("PT_Pionir_Investasi_1_5T")
        s3.hasOmzetTahunan = 50_000_000_000.0
        s3.isIndustriPionir = True
        s3.isPenanamanModalBaru = True
        s3.hasSuratKeteranganFiskal = True
        s3.isBelumPernahPutusTaxHoliday = True
        s3.hasNilaiInvestasi = 1_500_000_000_000.0
        s3.isPerseroanTerbuka = False
        s3.isUMKM_PP55 = False
        s3.isPenyerahanNonMewahPPN = True
        s3.hasNPWP = True

        # 4. UMKM PP 55 omzet Rp2,4M -> Fasilitas PP55 0,5%
        s4 = onto.CV("CV_UMKM_Aktif_001")
        s4.hasOmzetTahunan = 2_400_000_000.0
        s4.isUMKM_PP55 = True
        s4.isPerseroanTerbuka = False
        s4.hasNPWP = True

        # 5. UMKM PP 55 omzet lewat Rp4,8M (Rp5,5M) -> Wajib PKP + Transisi + Pasal 31E (omzet <= 50M) + PPN Efektif 11%
        s5 = onto.CV("CV_UMKM_Lewat_4_8M")
        s5.hasOmzetTahunan = 5_500_000_000.0
        s5.isUMKM_PP55 = True
        s5.isPerseroanTerbuka = False
        s5.isPenyerahanNonMewahPPN = True
        s5.hasNPWP = True

        # 6. Usaha Spa Kesehatan Tradisional di DKI -> Pengecualian PBJT Hiburan 40% (MK-2024-19-PUU-XXII)
        s6 = onto.PT("PT_Spa_Kesehatan_DKI")
        s6.hasOmzetTahunan = 3_000_000_000.0
        s6.isUsahaSpaKesehatanTradisional = True
        s6.isPerseroanTerbuka = False
        s6.isUMKM_PP55 = False
        s6.isDomisiliDKI = True
        s6.isMemilikiObjekPBB = True
        s6.hasNPWP = True

        # 7. Orang Pribadi penduduk Indonesia pemilik kendaraan ke-2 di DKI Jakarta -> PKB Progresif 3% + NIK-NPWP + SPT 3 bln
        s7 = onto.OrangPribadi("OP_KendaraanKedua_DKI")
        s7.isDomisiliDKI = True
        s7.isMilikPribadi = True
        s7.hasJumlahKendaraan = 2
        s7.isPendudukIndonesia = True
        s7.hasNPWP = True

        # 8. Wajib Pajak telat lapor SPT & banding ditolak -> Risiko Sanksi KUP Rp1jt Badan + Banding 60% + SEMA-2024-2-TUN-4 + Pasal 31E + PPN 11%
        s8 = onto.PT("PT_Risiko_Sanksi_001")
        s8.hasOmzetTahunan = 10_000_000_000.0
        s8.isPerseroanTerbuka = False
        s8.isUMKM_PP55 = False
        s8.isPenyerahanNonMewahPPN = True
        s8.hasNPWP = True
        s8.isTerlambatLaporSPT = True
        s8.isBandingDitolak = True

        # 9. OP Pegawai Tetap K/2 (2 pemberi kerja) -> TER Kategori B + PTKP + Pasal 17 L1-L2 + Rekonsiliasi Multi Pemberi Kerja
        s9 = onto.OrangPribadi("OP_Pegawai_K2_001")
        s9.memilikiPekerjaan = [onto.PegawaiTetap_Swasta]
        s9.isSubjekLuarNegeri = False
        s9.isPendudukIndonesia = True
        s9.isKawin = True
        s9.hasJumlahTanggungan = 2
        s9.hasJumlahPemberiKerja = 2
        s9.hasPenghasilanKenaPajakTahunan = 120_000_000.0
        s9.hasNPWP = True

        # 10. OP Multi-Peran: Dokter (PekerjaanBebas) + Karyawan + Toko Online Rp300jt -> Larangan PP55 Dokter + NPPN + Bebas 500jt Toko + TER A
        s10 = onto.OrangPribadi("OP_Dokter_MultiPeran_001")
        s10.memilikiPekerjaan = [onto.Dokter, onto.PegawaiTetap_Swasta, onto.Pedagang_ECommerce]
        s10.isSubjekLuarNegeri = False
        s10.isPendudukIndonesia = True
        s10.isKawin = False
        s10.hasJumlahTanggungan = 0
        s10.isUMKM_PP55 = True
        s10.hasOmzetTahunan = 300_000_000.0
        s10.hasPenghasilanKenaPajakTahunan = 300_000_000.0
        s10.hasNPWP = True

        # 11. OP Influencer Pekerjaan Bebas omzet Rp1,2M -> Dilarang PP 55, layak NPPN, DPP 50% Bukan Pegawai, Pasal 17 L1-L3
        s11 = onto.OrangPribadi("OP_Influencer_NPPN_001")
        s11.memilikiPekerjaan = [onto.Influencer_KontenKreator]
        s11.isSubjekLuarNegeri = False
        s11.isPendudukIndonesia = True
        s11.isUMKM_PP55 = True  # meskipun dicentang, tidak boleh PP 55 karena PekerjaanBebas
        s11.hasOmzetTahunan = 1_200_000_000.0
        s11.hasPenghasilanKenaPajakTahunan = 400_000_000.0
        s11.hasNPWP = True

        # 12. OP Pedagang Kuliner UMKM omzet Rp1,2M -> Bebas Rp500jt pertama + PP 55 0,5% atas selisih > Rp500jt
        s12 = onto.OrangPribadi("OP_UMKM_Kuliner_1_2M")
        s12.memilikiPekerjaan = [onto.Usaha_Kuliner_Warung]
        s12.isSubjekLuarNegeri = False
        s12.isPendudukIndonesia = True
        s12.isUMKM_PP55 = True
        s12.hasOmzetTahunan = 1_200_000_000.0
        s12.hasNPWP = True

        # 13. Bentuk Usaha Tetap (BUT) -> PPh Badan 22% + Branch Profit Tax 20%, tanpa PP55 & tanpa Pasal 31E
        s13 = onto.BUT("BUT_TechGlobal_001")
        s13.hasOmzetTahunan = 3_000_000_000.0
        s13.isUMKM_PP55 = True
        s13.hasNPWP = True

        # 14. WP Surabaya pemilik objek PBB NJOP Rp1,5M + Spa Hiburan Umum -> PBB 0,15% + PBJT 50% + PPh 22% + Pasal 31E
        s14 = onto.PT("PT_Surabaya_Properti_001")
        s14.berdomisiliDi = [onto.Wilayah_Kota_Surabaya]
        s14.isMemilikiObjekPBB = True
        s14.hasNilaiNJOP = 1_500_000_000.0
        s14.isUsahaHiburanSpaUmum = True
        s14.isPerseroanTerbuka = False
        s14.isUMKM_PP55 = False
        s14.hasOmzetTahunan = 4_000_000_000.0
        s14.hasNPWP = True

        # 15. OP Jawa Barat pemilik kendaraan ke-2 -> PKB 1,62% + Opsen PKB 66%
        s15 = onto.OrangPribadi("OP_Jabar_PKB2_001")
        s15.berdomisiliDi = [onto.Wilayah_Jawa_Barat]
        s15.isMilikPribadi = True
        s15.hasJumlahKendaraan = 2
        s15.isPendudukIndonesia = True
        s15.hasNPWP = True


def export_full_rules_ttl(rules_list: List[dict], out_ttl: Path) -> int:
    """Ekspor seluruh 12.907 aturan legal_rules.jsonl ke Turtle RDF untuk rdflib/SPARQL."""
    g = Graph()
    KBR = Namespace(BASE_IRI)
    g.bind("kbr", KBR)
    g.bind("rdfs", RDFS)
    g.bind("xsd", XSD)

    seen_regs, seen_pasals = set(), set()
    for r in rules_list:
        did = r["document_id"]
        loc = r["source_locator"]
        rid = r["rule_id"]

        reg_uri = KBR[_safe_id(f"Reg_{did}")]
        if did not in seen_regs:
            seen_regs.add(did)
            g.add((reg_uri, RDF.type, KBR[_doc_subclass_name(did)]))
            g.add((reg_uri, KBR.hasDocumentId, Literal(did, datatype=XSD.string)))

        pasal_uri = KBR[_safe_id(f"Pasal_{loc}")]
        if loc not in seen_pasals:
            seen_pasals.add(loc)
            g.add((pasal_uri, RDF.type, KBR.Pasal))
            g.add((pasal_uri, KBR.hasSourceLocator, Literal(loc, datatype=XSD.string)))
            g.add((pasal_uri, KBR.bagianDariRegulasi, reg_uri))

        a_uri = KBR[_safe_id(f"Aturan_{rid}")]
        g.add((a_uri, RDF.type, KBR[_rule_subclass_name(r.get("rule_type", "other"))]))
        g.add((a_uri, KBR.hasRuleId, Literal(rid, datatype=XSD.string)))
        g.add((a_uri, KBR.hasSourceLocator, Literal(loc, datatype=XSD.string)))
        if r.get("source_quote"):
            g.add((a_uri, KBR.hasSourceQuote, Literal(r["source_quote"], datatype=XSD.string)))
        if r.get("validation_status"):
            g.add((a_uri, KBR.hasStatusValidasi, Literal(r["validation_status"], datatype=XSD.string)))
        if r.get("domain"):
            g.add((a_uri, KBR.termasukDomain, KBR[_safe_id(f"Domain_{r['domain']}")]))
        g.add((a_uri, KBR.diaturDalam, reg_uri))
        g.add((a_uri, KBR.diaturDalamPasal, pasal_uri))
        for mid in r.get("mk_review_refs") or []:
            g.add((a_uri, KBR.terdampakPutusanMK, KBR[_safe_id(mid)]))
        for sid in r.get("sema_tun_refs") or []:
            g.add((a_uri, KBR.merujukSEMA, KBR[_safe_id(sid)]))

    out_ttl.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(out_ttl), format="turtle")
    return len(rules_list)


def build_all_ontologies(
    *,
    rules_jsonl: Path,
    mk_dir: Path,
    sema_dir: Path,
    out_dir: Path,
    full_ttl_path: Path,
) -> dict:
    """Bangun TBox, Reasoning OWL (clean), Rule Map, dan ekspor RDF penuh, lalu uji HermiT."""
    rules_list = [json.loads(l) for l in rules_jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
    rules_by_id = {r["rule_id"]: r for r in rules_list}

    mk_docs = {}
    if mk_dir.exists():
        for p in sorted(mk_dir.glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            mk_docs[d.get("case_id") or p.stem] = d

    sema_docs = {}
    if sema_dir.exists():
        for p in sorted(sema_dir.glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("is_pajak_terkait"):
                sema_docs[d.get("sema_id") or p.stem] = d

    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Simpan TBox murni (RDF/XML + Turtle + kbr-core.ttl sesuai plan §9)
    w_tbox, onto_tbox = build_tbox()
    tbox_owl = out_dir / "kbr_pajak_tbox.owl"
    tbox_ttl = out_dir / "kbr_pajak_tbox.ttl"
    core_ttl = out_dir / "kbr-core.ttl"
    onto_tbox.save(file=str(tbox_owl), format="rdfxml")
    g_tbox = Graph()
    g_tbox.parse(str(tbox_owl), format="xml")
    g_tbox.serialize(destination=str(tbox_ttl), format="turtle")
    g_tbox.serialize(destination=str(core_ttl), format="turtle")

    # 2. Bangun Reasoning OWL (TBox + SWRL + ABox inti + 8 skenario uji)
    w_res, onto_res = build_tbox()
    rule_map = _create_catalog_and_swrl(onto_res, rules_by_id, mk_docs, sema_docs)
    _create_demo_scenarios(onto_res)

    reasoning_owl = out_dir / "kbr_pajak_reasoning.owl"
    onto_res.save(file=str(reasoning_owl), format="rdfxml")
    (out_dir / "rule_map.json").write_text(json.dumps(rule_map, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3. Uji konsistensi & inferensi dengan HermiT pada World terisolasi
    w_test = World()
    o_test = w_test.get_ontology(str(reasoning_owl)).load()
    with o_test:
        sync_reasoner_hermit(w_test, infer_property_values=True, debug=0)

    # Kumpulkan hasil inferensi skenario demonstrasi
    inferred_summary = {}
    for s_name in (
        "PT_TechStartup_001", "PT_Terbuka_001", "PT_Pionir_Investasi_1_5T",
        "CV_UMKM_Aktif_001", "CV_UMKM_Lewat_4_8M", "PT_Spa_Kesehatan_DKI",
        "OP_KendaraanKedua_DKI", "PT_Risiko_Sanksi_001",
        "OP_Pegawai_K2_001", "OP_Dokter_MultiPeran_001",
        "OP_Influencer_NPPN_001", "OP_UMKM_Kuliner_1_2M",
        "BUT_TechGlobal_001", "PT_Surabaya_Properti_001", "OP_Jabar_PKB2_001",
    ):
        ind = getattr(o_test, s_name)
        inferred_summary[s_name] = {
            "classes": sorted(
                c.name for c in ind.INDIRECT_is_a
                if isinstance(c, ThingClass) and c.name != "Thing"
            ),
            "tarif": sorted(t.name for t in ind.dikenaiTarif),
            "fasilitas": sorted(f.name for f in ind.memilikiFasilitas),
            "kewajiban": sorted(k.name for k in ind.memilikiKewajiban),
            "sanksi": sorted(s.name for s in ind.berisikoSanksi),
        }

    # 4. Ekspor penuh seluruh 12.907 aturan ke Turtle untuk rdflib/SPARQL
    full_count = export_full_rules_ttl(rules_list, full_ttl_path)

    return {
        "tbox_owl": str(tbox_owl),
        "tbox_ttl": str(tbox_ttl),
        "core_ttl": str(core_ttl),
        "reasoning_owl": str(reasoning_owl),
        "reasoning_individuals": len(list(onto_res.individuals())),
        "reasoning_classes": len(list(onto_res.classes())),
        "swrl_rules": len(list(onto_res.rules())),
        "full_ttl": str(full_ttl_path),
        "full_rules_exported": full_count,
        "inferred_scenarios": inferred_summary,
    }


def reason_wajib_pajak(reasoning_owl: Path, wp_id: str, wp_kind: str, props: dict) -> dict:
    """Evaluasi 1 skenario WajibPajak secara terisolasi (per-request World()) + justifikasi pasal."""
    w = World()
    onto = w.get_ontology(str(reasoning_owl)).load()
    with onto:
        # Bersihkan individu skenario demo & aturan tambahan yang tidak tertaut ke katalog agar inferensi tunggal cepat & steril
        for ind in list(onto.WajibPajak.instances()):
            destroy_entity(ind)
        linked_aturan = set()
        for cat_cls in (onto.TarifPajak, onto.FasilitasPerpajakan, onto.KewajibanPajak, onto.SanksiAdministratif):
            for it in cat_cls.instances():
                for at in getattr(it, "didasarkanPadaAturan", []):
                    linked_aturan.add(at.name)
        for ind in list(onto.AturanHukum.instances()):
            if ind.name not in linked_aturan:
                destroy_entity(ind)

        cls = getattr(onto, wp_kind, None)
        if cls is None:
            cls = onto.Badan if wp_kind == "Badan" else onto.OrangPribadi
        wp = cls(wp_id)
        for k, v in props.items():
            if k in ("memilikiPekerjaan", "berdomisiliDi", "memilikiPenghasilanFinal"):
                vals = v if isinstance(v, (list, tuple)) else [v]
                objs = [getattr(onto, str(item), None) for item in vals]
                setattr(wp, k, [o for o in objs if o is not None])
            elif hasattr(wp, k):
                setattr(wp, k, v)
        sync_reasoner_hermit(w, infer_property_values=True, debug=0)

    def _explain(items) -> List[dict]:
        out = []
        for it in items:
            just = []
            for at in getattr(it, "didasarkanPadaAturan", []):
                just.append({
                    "rule_id": getattr(at, "hasRuleId", None),
                    "source_locator": getattr(at, "hasSourceLocator", None),
                    "source_quote": getattr(at, "hasSourceQuote", None),
                    "regulasi": [r.hasDocumentId for r in getattr(at, "diaturDalam", [])],
                    "mk_refs": [m.hasDocumentId for m in getattr(at, "terdampakPutusanMK", [])],
                    "sema_refs": [s.hasDocumentId for s in getattr(at, "merujukSEMA", [])],
                })
            out.append({
                "id": it.name,
                "label": it.label[0] if it.label else it.name,
                "tarif_persen": getattr(it, "hasTarifPersen", None),
                "justifikasi": just,
            })
        return out

    return {
        "wp_id": wp_id,
        "inferred_classes": sorted(
            c.name for c in wp.INDIRECT_is_a
            if isinstance(c, ThingClass) and c.name != "Thing"
        ),
        "tarif": _explain(wp.dikenaiTarif),
        "fasilitas": _explain(wp.memilikiFasilitas),
        "kewajiban": _explain(wp.memilikiKewajiban),
        "sanksi": _explain(wp.berisikoSanksi),
    }


def query_rule_provenance_sparql(
    rdf_path: Path,
    *,
    rule_id: Optional[str] = None,
    document_id: Optional[str] = None,
    limit: int = 20,
    graph: Optional[Graph] = None,
) -> List[dict]:
    """Jalankan query SPARQL lokal via rdflib untuk melacak provenance rule_id -> Pasal -> Regulasi -> MK/SEMA."""
    if graph is None:
        g = Graph()
        fmt = "turtle" if rdf_path.suffix == ".ttl" else "xml"
        g.parse(str(rdf_path), format=fmt)
    else:
        g = graph

    filters = []
    if rule_id:
        safe_rid = rule_id.replace('"', '\\"')
        filters.append(f'FILTER(STR(?ruleId) = "{safe_rid}")')
    if document_id:
        safe_did = document_id.replace('"', '\\"')
        filters.append(f'FILTER(STR(?docId) = "{safe_did}")')
    filter_clause = "\n        ".join(filters)

    q = f"""
    PREFIX kbr: <{BASE_IRI}>
    SELECT ?aturan ?ruleId ?docId ?locator ?quote ?status ?mk ?sema
    WHERE {{
        ?aturan kbr:hasRuleId ?ruleId ;
                kbr:hasSourceLocator ?locator ;
                kbr:diaturDalam ?reg .
        ?reg kbr:hasDocumentId ?docId .
        OPTIONAL {{ ?aturan kbr:hasSourceQuote ?quote . }}
        OPTIONAL {{ ?aturan kbr:hasStatusValidasi ?status . }}
        OPTIONAL {{ ?aturan kbr:terdampakPutusanMK ?mk . }}
        OPTIONAL {{ ?aturan kbr:merujukSEMA ?sema . }}
        {filter_clause}
    }}
    ORDER BY ?docId ?locator ?ruleId
    LIMIT {int(limit)}
    """
    rows = []
    for r in g.query(q):
        rows.append({
            "aturan_uri": str(r.aturan),
            "rule_id": str(r.ruleId),
            "document_id": str(r.docId),
            "source_locator": str(r.locator),
            "source_quote": str(r.quote) if r.quote is not None else "",
            "validation_status": str(r.status) if r.status is not None else "",
            "mk_ref": str(r.mk).split("#")[-1] if r.mk is not None else None,
            "sema_ref": str(r.sema).split("#")[-1] if r.sema is not None else None,
        })
    return rows
