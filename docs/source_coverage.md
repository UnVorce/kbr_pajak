# Source Coverage & Quality (dihasilkan report.py)

*Target metrik: spec Bagian 9.1 (M1–M8) dan invarian 6.4 (I1–I3).*

## M1 — Antrean kunjungan tersisa (target: kosong)
- total: **18** — per domain: {'DOMAIN_A': 6, 'UNASSIGNED': 12}

## M2 — Kutipan belum terselesaikan (target: tidak ada UNRESOLVED)
- tidak ada baris

## M3 — Selisih daftar dokumen antar-sumber (target: setiap selisih dijelaskan)
- BPK_minus_KEMENKEU: 20 dokumen — PERPU-2020-1, PERPU-2022-2, UU-1970-12, UU-1983-6, UU-1983-7, UU-1983-8, UU-1991-7, UU-1994-10, UU-1994-9, UU-1995-11…
- KEMENKEU_minus_BPK: 0 dokumen (kosong)
- BPK_minus_DJP: 20 dokumen — PERPU-2020-1, PERPU-2022-2, UU-1970-12, UU-1983-6, UU-1983-7, UU-1983-8, UU-1991-7, UU-1994-10, UU-1994-9, UU-1995-11…
- DJP_minus_BPK: 0 dokumen (kosong)
- KEMENKEU_minus_DJP: 0 dokumen (kosong)
- DJP_minus_KEMENKEU: 0 dokumen (kosong)

## M4 — Rantai versi pasal lengkap (dilaporkan persentasenya)
- total pasal: 0, punya versi: 0, tumpang tindih interval: 0, lengkap: 0 (N/A%)

## M5 — Kecocokan naskah konsolidasi (Fase 7)
- status: N/A — Dihitung Fase 7 setelah verifikasi naskah konsolidasi

## M6 — Pelanggaran invarian (target: 0)
- I1_in_scope_without_owner: **0** ✅
- I2_claimed_by_mismatch_owner: **0** ✅
- I3_boundary_without_origin: **0** ✅

## M7 — Dokumen FAILED / NEEDS_REVIEW per tahap
- discovery_status: tidak ada
- ingestion_status: tidak ada
- extraction_status: tidak ada
- validation_status: tidak ada

## M8 — BOUNDARY/UNDECIDED belum ditinjau
- BOUNDARY: 9, UNDECIDED: 109, belum ditinjau: **118**

## Status terpakai (review disiplin enumerasi 5.10)
- scope_status: BOUNDARY=9, IN_SCOPE=11, UNDECIDED=109
- discovery_status: DISCOVERED=109, METADATA_FETCHED=20
- ingestion_status: PENDING=129
- extraction_status: PENDING=129
- validation_status: PENDING=129
- legal_status: NEEDS_VERIFICATION=129
- review_queue.status: tidak ada baris
