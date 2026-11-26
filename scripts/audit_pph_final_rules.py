# -*- coding: utf-8 -*-
"""Part 1 — Audit & Normalisasi Aturan PPh Final Pasal 4(2) (PP 34/2017, PP 131/2000, PP 51/2008 jo. PP 9/2022, PP 34/2016).

Memverifikasi 21 aturan berstatus REVIEW_REQUIRED pada 4 regulasi PPh Final Pasal 4(2)
terhadap teks chunk sumber, memperbaiki artefak OCR pada rate_or_value / source_quote / condition,
dan mempromosikan status validasinya menjadi HUMAN_FIXED atau HUMAN_APPROVED tanpa mengubah
jumlah total aturan (12.921) di data/legal_rules.jsonl.

Contoh:
    python3 scripts/audit_pph_final_rules.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET_DOCS = ("PP-2017-34", "PP-2000-131", "PP-2008-51", "PP-2016-34")

# Keputusan audit per rule_id (hanya untuk 21 aturan REVIEW_REQUIRED pada 4 regulasi di atas)
AUDIT_DECISIONS: Dict[str, dict] = {
    # --- PP-2017-34 (Sewa Tanah dan/atau Bangunan) ---
    "R-PP-2017-34-a11ca8c4a6": {
        "decision": "HUMAN_FIXED",
        "notes": "Tarif PPh Final 10% sewa tanah/bangunan (PP 34/2017 Pasal 4(1)) benar; perbaiki typo OCR '10olo' pada rate_or_value[0].value menjadi numerik 10.0 sambil mempertahankan raw & source_quote persis teks sumber.",
        "fixes": {
            "rate_or_value": [{"value": 10.0, "unit": "%", "raw": "10olo (sepuluh persen)"}],
        },
    },
    "R-PP-2017-34-86e520fb7b": {
        "decision": "HUMAN_APPROVED",
        "notes": "Pengecualian jasa pelayanan penginapan beserta akomodasinya (PP 34/2017 Pasal 2(3)) terverifikasi persis terhadap chunk sumber.",
    },
    "R-PP-2017-34-fac78fb711": {
        "decision": "HUMAN_APPROVED",
        "notes": "Definisi jumlah bruto nilai persewaan termasuk biaya perawatan/keamanan/layanan/fasilitas (PP 34/2017 Pasal 4(2)) terverifikasi persis terhadap chunk sumber.",
    },
    # --- PP-2000-131 jo. PP-2015-123 (Bunga Deposito, Tabungan, Diskonto SBI) ---
    "R-PP-2000-131-fc05ed2fb9": {
        "decision": "HUMAN_APPROVED",
        "notes": "Tarif PPh Final 20% atas bunga tabungan, diskonto SBI, dan deposito umum selain DHE (PP 131/2000 jo. PP 123/2015 Pasal 2 huruf c) terverifikasi persis.",
    },
    "R-PP-2000-131-c9221e0b78": {
        "decision": "HUMAN_APPROVED",
        "notes": "Tarif PPh Final bertingkat deposito DHE USD 10%/7,5%/2,5%/0% (PP 131/2000 jo. PP 123/2015 Pasal 2 huruf a) terverifikasi persis.",
    },
    "R-PP-2000-131-d7e7a5e6ac": {
        "decision": "HUMAN_APPROVED",
        "notes": "Pengecualian pemotongan bagi OP SPDN dengan total penghasilan tahunan tidak melebihi PTKP (PP 131/2000 Pasal 1(3)) terverifikasi persis.",
    },
    # --- PP-2008-51 jo. PP-2022-9 (Jasa Konstruksi) ---
    "R-PP-2008-51-bd43270f8a": {
        "decision": "HUMAN_FIXED",
        "notes": "Tarif PPh Final 1,75% pekerjaan konstruksi SBU kecil/SKK (PP 51/2008 jo. PP 9/2022 Pasal 3(1)a); normalkan string '1,75' menjadi numerik 1.75.",
        "fixes": {
            "rate_or_value": [{"value": 1.75, "unit": "%", "raw": "l,75oh (satu koma tujuh puluh lima persen)"}],
        },
    },
    "R-PP-2008-51-fc527468d8": {
        "decision": "HUMAN_FIXED",
        "notes": "Tarif PPh Final 4% pekerjaan konstruksi tanpa SBU/SKK (PP 51/2008 jo. PP 9/2022 Pasal 3(1)b); normalkan string '4' menjadi numerik 4.0.",
        "fixes": {
            "rate_or_value": [{"value": 4.0, "unit": "%", "raw": "4% (empat persen)"}],
        },
    },
    "R-PP-2008-51-77cd2d02ee": {
        "decision": "HUMAN_FIXED",
        "notes": "Tarif PPh Final 2,65% pekerjaan konstruksi menengah/besar bersertifikat (PP 51/2008 jo. PP 9/2022 Pasal 3(1)c); normalkan string '2,65' menjadi numerik 2.65.",
        "fixes": {
            "rate_or_value": [{"value": 2.65, "unit": "%", "raw": "2,650/o (dua koma enam puluh lima persen)"}],
        },
    },
    "R-PP-2008-51-59116f2a02": {
        "decision": "HUMAN_FIXED",
        "notes": "Tarif PPh Final 2,65% pekerjaan konstruksi terintegrasi bersertifikat (PP 51/2008 jo. PP 9/2022 Pasal 3(1)d); normalkan string '2,65' menjadi numerik 2.65.",
        "fixes": {
            "rate_or_value": [{"value": 2.65, "unit": "%", "raw": "2,650/o (dua koma enam puluh lima persen)"}],
        },
    },
    "R-PP-2008-51-fe99b15648": {
        "decision": "HUMAN_FIXED",
        "notes": "Tarif PPh Final 4% pekerjaan konstruksi terintegrasi tanpa SBU (PP 51/2008 jo. PP 9/2022 Pasal 3(1)e); normalkan string '4' menjadi numerik 4.0.",
        "fixes": {
            "rate_or_value": [{"value": 4.0, "unit": "%", "raw": "4% (empat persen)"}],
        },
    },
    "R-PP-2008-51-ee380105e4": {
        "decision": "HUMAN_FIXED",
        "notes": "Tarif PPh Final 3,5% jasa konsultansi konstruksi bersertifikat (PP 51/2008 jo. PP 9/2022 Pasal 3(1)f); normalkan string '3,5' menjadi numerik 3.5.",
        "fixes": {
            "rate_or_value": [{"value": 3.5, "unit": "%", "raw": "3,5% (tiga koma lima persen)"}],
        },
    },
    "R-PP-2008-51-631d959451": {
        "decision": "HUMAN_FIXED",
        "notes": "Tarif PPh Final 6% jasa konsultansi konstruksi tanpa SBU/SKK (PP 51/2008 jo. PP 9/2022 Pasal 3(1)g); normalkan string '6' menjadi numerik 6.0.",
        "fixes": {
            "rate_or_value": [{"value": 6.0, "unit": "%", "raw": "60/o (enam persen)"}],
        },
    },
    "R-PP-2008-51-93814c2b7a": {
        "decision": "HUMAN_APPROVED",
        "notes": "Aturan piutang tak tertagih atas nilai kontrak jasa konstruksi tidak dibayar sepenuhnya (PP 51/2008 Pasal 6(2)) terverifikasi persis.",
    },
    "R-PP-2008-51-2e03aa08cc": {
        "decision": "HUMAN_APPROVED",
        "notes": "Ketentuan peralihan BAST sampai dengan 31 Desember 2008 (PP 51/2008 Pasal 10A huruf a) terverifikasi persis.",
    },
    # --- PP-2016-34 (Pengalihan Hak atas Tanah dan/atau Bangunan) ---
    "R-PP-2016-34-7c066787f5": {
        "decision": "HUMAN_FIXED",
        "notes": "Tarif PPh Final 2,5% pengalihan hak atas tanah/bangunan umum (PP 34/2016 Pasal 2(1)a) benar; normalkan value string '2,5%' menjadi numerik 2.5.",
        "fixes": {
            "rate_or_value": [{"value": 2.5, "unit": "%", "raw": "2,5% (dua koma lima persen)"}],
        },
    },
    "R-PP-2016-34-9fdb5292bd": {
        "decision": "HUMAN_FIXED",
        "notes": "Tarif PPh Final 1% pengalihan Rumah Sederhana/Rusunami oleh developer (PP 34/2016 Pasal 2(1)b) benar; normalkan value string '1%' menjadi numerik 1.0.",
        "fixes": {
            "rate_or_value": [{"value": 1.0, "unit": "%", "raw": "1% (satu persen)"}],
        },
    },
    "R-PP-2016-34-2c3484ea65": {
        "decision": "HUMAN_FIXED",
        "notes": "Tarif PPh Final 0% pengalihan kepada pemerintah/BUMN/BUMD penugasan khusus (PP 34/2016 Pasal 2(1)c) benar; normalkan value string '0%' menjadi numerik 0.0.",
        "fixes": {
            "rate_or_value": [{"value": 0.0, "unit": "%", "raw": "O% (nol persen)"}],
        },
    },
    "R-PP-2016-34-f8880289de": {
        "decision": "HUMAN_APPROVED",
        "notes": "Tarif PPh Final 2,5% ayat (2) PP 34/2016 sudah numerik (2.5) dan terverifikasi persis terhadap chunk sumber.",
    },
    "R-PP-2016-34-9b3e8ded61": {
        "decision": "HUMAN_APPROVED",
        "notes": "Tarif PPh Final 2,5% PPJB ayat (3) huruf a PP 34/2016 sudah numerik (2.5) dan terverifikasi persis terhadap chunk sumber.",
    },
    "R-PP-2016-34-f7d3df5af9": {
        "decision": "HUMAN_APPROVED",
        "notes": "Kewajiban bendahara pemerintah menyetor PPh pengalihan hak sebelum pembayaran (PP 34/2016 Pasal 4(2)) terverifikasi persis.",
    },
    "R-PP-2016-34-7a730deeca": {
        "decision": "HUMAN_APPROVED",
        "notes": "Kewajiban bendahara pemerintah melaporkan pengalihan hak ke DJP (PP 34/2016 Pasal 4(3)) terverifikasi persis.",
    },
    "R-PP-2016-34-9bbd83e4c2": {
        "decision": "HUMAN_FIXED",
        "notes": "Pengecualian OP di bawah PTKP dengan nilai bruto pengalihan < Rp60jt (PP 34/2016 Pasal 6 huruf a) benar; perbaiki typo 'pemunya' -> 'mempunyai' pada condition[0].raw sesuai teks chunk.",
        "fixes": {
            "condition": [
                {
                    "attribute": "penghasilan",
                    "operator": "<",
                    "value": "Penghasilan Tidak Kena Pajak",
                    "raw": "mempunyai penghasilan di bawah Penghasilan Tidak Kena Pajak",
                },
                {
                    "attribute": "jumlah bruto pengalihan",
                    "operator": "<",
                    "value": "Rp60.000.000,00",
                    "raw": "jumlah bruto pengalihannya kurang dari Rp60.000.000,00",
                },
                {
                    "attribute": "jumlah bruto pengalihan",
                    "operator": "!=",
                    "value": "jumlah yang dipecah-pecah",
                    "raw": "bukan merupakan jumlah yang dipecah-pecah",
                },
            ],
        },
    },
    "R-PP-2016-34-87d35ef74f": {
        "decision": "HUMAN_FIXED",
        "notes": "Pengecualian hibah badan keagamaan/pendidikan/sosial/UMK (PP 34/2016 Pasal 6 huruf d) benar; perbaiki source_quote & condition agar persis substring teks chunk ('pihak- pihak').",
        "fixes": {
            "source_quote": (
                "d. badan yang melakukan pengalihan harta berupa tanah dan/ atau bangunan dengan cara hibah kepada "
                "badan keagamaan, badan pendidikan, badan sosial termasuk yayasan, koperasi atau orang pribadi yang "
                "menjalankan usaha mikro dan kecil, yang ketentuannya diatur lebih lanjut dengan Peraturan Menteri "
                "Keuangan, sepanjang hibah tersebut tidak ada hubungan dengan usaha, pekerjaan, kepemilikan, atau "
                "penguasaan antara pihak- pihak yang bersangkutan;"
            ),
            "condition": [
                {
                    "attribute": "penerima hibah",
                    "operator": "in",
                    "value": "badan keagamaan, badan pendidikan, badan sosial termasuk yayasan, koperasi atau orang pribadi yang menjalankan usaha mikro dan kecil",
                    "raw": "badan keagamaan, badan pendidikan, badan sosial termasuk yayasan, koperasi atau orang pribadi yang menjalankan usaha mikro dan kecil",
                },
                {
                    "attribute": "hibah",
                    "operator": "!=",
                    "value": "hubungan dengan usaha, pekerjaan, kepemilikan, atau penguasaan antara pihak- pihak yang bersangkutan",
                    "raw": "sepanjang hibah tersebut tidak ada hubungan dengan usaha, pekerjaan, kepemilikan, atau penguasaan antara pihak- pihak yang bersangkutan",
                },
            ],
        },
    },
    "R-PP-2016-34-8d02c0f189": {
        "decision": "HUMAN_APPROVED",
        "notes": "Pengecualian pengalihan oleh bukan subjek pajak (PP 34/2016 Pasal 6) terverifikasi persis terhadap chunk sumber.",
    },
    "R-PP-2016-34-a5cc82241a": {
        "decision": "HUMAN_APPROVED",
        "notes": "Kewajiban verifikasi SSP oleh Kementerian ATR/BPN sebelum menerbitkan SK hak atas tanah (PP 34/2016 Pasal 7) terverifikasi persis.",
    },
    "R-PP-2016-34-01ce0e8e89": {
        "decision": "HUMAN_APPROVED",
        "notes": "Sanksi pejabat pembuat akta/risalah lelang yang melanggar Pasal 3(5)-(6) (PP 34/2016 Pasal 8) terverifikasi persis.",
    },
    "R-PP-2016-34-9a6c7a7ba1": {
        "decision": "HUMAN_APPROVED",
        "notes": "Sanksi pihak penjual PPJB yang melanggar Pasal 5(2)-(3) (PP 34/2016 Pasal 8) terverifikasi persis.",
    },
}


def run_audit(
    rules_path: Path = ROOT / "data" / "legal_rules.jsonl",
    chunks_path: Path = ROOT / "data" / "chunks" / "pending" / "all_t2_chunks.jsonl",
    log_path: Path = ROOT / "data" / "review" / "pph_final_audit_log.jsonl",
    report_path: Path = ROOT / "data" / "review" / "pph_final_audit_report.json",
) -> dict:
    rules: List[dict] = [json.loads(l) for l in rules_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    chunks: Dict[str, dict] = {}
    if chunks_path.exists():
        for l in chunks_path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                c = json.loads(l)
                chunks[c["chunk_id"]] = c

    audit_entries = []
    decision_counts: Counter = Counter()
    by_doc_status: Dict[str, Counter] = {d: Counter() for d in TARGET_DOCS}
    now_iso = datetime.now(timezone.utc).isoformat()

    for r in rules:
        rid = r["rule_id"]
        doc_id = r["document_id"]
        if rid in AUDIT_DECISIONS:
            spec = AUDIT_DECISIONS[rid]
            prev_status = r.get("validation_status")
            for k, v in (spec.get("fixes") or {}).items():
                r[k] = v
            r["validation_status"] = spec["decision"]
            r["human_notes"] = spec["notes"]
            decision_counts[spec["decision"]] += 1
            audit_entries.append(
                {
                    "audited_at": now_iso,
                    "rule_id": rid,
                    "document_id": doc_id,
                    "source_locator": r.get("source_locator"),
                    "previous_status": prev_status,
                    "human_decision": spec["decision"],
                    "human_notes": spec["notes"],
                    "fixes": spec.get("fixes") or {},
                }
            )

        if doc_id in TARGET_DOCS:
            by_doc_status[doc_id][r["validation_status"]] += 1
            if chunks:
                ctext = (chunks.get(r.get("chunk_id")) or {}).get("text", "")
                sq = r.get("source_quote") or ""
                if sq not in ctext:
                    raise AssertionError(
                        f"P4 violation: source_quote {rid} ({doc_id}) bukan substring persis dari chunk {r.get('chunk_id')}"
                    )
            if r["rule_type"] == "rate":
                for item in r.get("rate_or_value") or []:
                    if not isinstance(item.get("value"), (int, float)):
                        raise AssertionError(
                            f"Rate value belum numerik pada {rid}: {item!r}"
                        )

    # Tulis kembali legal_rules.jsonl (jumlah & urutan persis 12.921)
    with rules_path.open("w", encoding="utf-8") as f:
        for r in rules:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        for e in audit_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    report = {
        "total_rules": len(rules),
        "audited_count": len(audit_entries),
        "decision_counts": dict(sorted(decision_counts.items())),
        "by_document_status": {d: dict(sorted(c.items())) for d, c in by_doc_status.items()},
        "quote_verbatim_verified": bool(chunks),
        "numeric_rate_verified": True,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    rep = run_audit()
    print(json.dumps(rep, ensure_ascii=False, indent=2))
