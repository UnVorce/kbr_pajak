# -*- coding: utf-8 -*-
"""Tahap 4A — Merge korpus pph_op/, konsolidasi UU 6/2023 (Cipta Kerja) & PMK-2024-118,
re-parse sub-pasal consolidated/*.json, dan bangun data/scope_manifest.jsonl.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.fase1_korpus import canon_doc  # noqa: E402
from src.consolidate import consolidate  # noqa: E402
from src.gaps import extract_citations  # noqa: E402
from src.parse_structure import parse_document, parse_pasals_to_subprovisions  # noqa: E402
from src.textutil import cut_penjelasan, split_pasal  # noqa: E402

DOCS = ROOT / "data" / "documents"
TEXT = ROOT / "data" / "text"
CONS = ROOT / "data" / "consolidated"
PERDA = ROOT / "data" / "perda"
PPH_OP_FULL = ROOT.parent / "kbr_pajak" / "knowledge_json" / "pph_op" / "full"
CONFIG = ROOT / "config" / "consolidation.yaml"
SCOPE_OUT = ROOT / "data" / "scope_manifest.jsonl"

PILOT_PERDAS = [
    "PERDA-PROV-DKI-JAKARTA-2024-1",
    "PERDA-PROV-JAWA-BARAT-2023-9",
    "PERDA-KOTA-SEMARANG-2023-10",
    "PERDA-KOTA-SURABAYA-2023-7",
    "PERDA-PROV-BALI-2024-1",
]

NOISE_IDS = {
    "PP-2018-40", "PMK-2018-109", "PMK-2018-151",
    "PMK-2019-56", "PMK-2019-121", "PMK-2024-127",
    "UU-2011-12", "PMK-2020-96", "UU-2009-16", "PP-2021-9",
}

DOMAIN_RULES = [
    ({"UU-1983-7", "PP-2022-55", "PP-2010-94", "PP-2019-78", "PMK-2020-130",
      "PMK-2019-128", "PMK-2024-79", "PMK-2023-172", "PMK-2023-72",
      "PMK-2015-169", "PMK-2009-105", "PMK-2010-2", "PMK-2019-35",
      "PMK-2024-136", "PMK-2025-114", "PMK-2023-66", "PP-2000-20"}, "A2_PPH_BADAN"),
    ({"UU-1983-8", "PP-2022-44", "PP-2022-49", "PMK-2024-81", "PMK-2025-11",
      "PMK-2024-131", "PMK-2010-68", "PMK-2023-41", "PMK-2023-48",
      "PMK-2022-71", "PP-2019-73", "PP-2020-61", "PMK-2021-96", "PMK-2024-8"}, "B_PPN"),
    ({"UU-1985-12", "PMK-2019-186", "PMK-2023-142", "UU-2022-1",
      "PP-2023-35", "PMK-2023-143"}, "C_PBB_HKPD"),
    ({"UU-1983-6", "PP-2022-50", "PERPRES-2018-40", "PER-DJP-2025-11",
      "PER-DJP-2025-7", "PMK-2022-112", "PMK-2024-118", "PMK-2026-28",
      "PMK-2023-61", "PMK-2023-80", "PMK-2025-15", "PMK-2025-111",
      "UU-1997-19", "UU-2002-14", "PMK-2014-111", "PERPU-2017-1",
      "UU-2020-10", "PP-2022-3", "PMK-2024-78", "PER-DJP-2026-11"}, "D_ADMIN_SANKSI"),
    ({"PMK-2016-101", "PMK-2023-164", "PMK-2023-168", "PMK-2025-105",
      "PMK-2026-6", "PER-DJP-2015-17", "PP-2023-58", "PP-2009-68",
      "PMK-2010-16", "PMK-2015-141", "PMK-2025-37", "PMK-2025-112",
      "PMK-2018-192", "PMK-2022-69", "PMK-2025-50"}, "PPH_OP_POTPUT"),
    ({"PP-2008-51", "PP-2021-91", "PP-2009-15", "PP-1994-41", "PP-2000-132",
      "PP-2000-131", "PMK-2018-212", "PP-2024-22", "PP-2016-34",
      "PP-2017-34", "PMK-2019-92", "PMK-2015-90"}, "PPH_FINAL_SEKTOR"),
    ({"PP-2021-40", "PMK-2020-237", "PP-2021-41", "PP-2010-79",
      "PP-2017-53", "PP-2021-93", "PP-2022-15", "UU-2021-7"}, "FASILITAS_SEKTOR"),
    ({"UU-1995-10", "UU-1995-11", "PP-2008-28", "PP-2009-32", "PMK-2023-96"}, "KEPABEANAN_CUKAI"),
]


MK_MANIFEST = ROOT / "data" / "mk_manifest.json"
SEMA_MANIFEST = ROOT / "data" / "sema_tun_manifest.json"
SEMA_DIR = ROOT / "data" / "sema_tun"


def _extract_pasal_nums(items: list[str]) -> set[str]:
    nums = set()
    for s in items or []:
        m = re.search(r"(?i)Pasal\s+(\d+[A-Z]?)", s)
        if m:
            nums.add(m.group(1).upper())
    return nums


def _build_review_ref_maps() -> tuple[dict[tuple[str, str], list[str]], dict[tuple[str, str], list[str]]]:
    """Petakan (document_id, pasal_nomor) -> daftar case_id MK / sema_id Kamar TUN."""
    mk_map: dict[tuple[str, str], list[str]] = {}
    if MK_MANIFEST.exists():
        mk_man = json.loads(MK_MANIFEST.read_text(encoding="utf-8"))
        for c in mk_man.get("cases", []):
            cid = c["case_id"]
            pnums = _extract_pasal_nums(c.get("pasal_diuji") or [])
            if not pnums:
                continue  # amar tanpa pasal spesifik: cukup tercatat di manifest, tanpa tautan pasal
            for did in c.get("impacted_corpus_docs") or c.get("uu_diuji") or []:
                for pno in pnums:
                    mk_map.setdefault((did, pno), []).append(cid)

    sema_map: dict[tuple[str, str], list[str]] = {}
    if SEMA_MANIFEST.exists():
        sm = json.loads(SEMA_MANIFEST.read_text(encoding="utf-8"))
        for it in sm.get("items", []):
            if not it.get("is_pajak_terkait"):
                continue
            sid = it["sema_id"]
            pfile = SEMA_DIR / f"{sid}.json"
            teks = json.loads(pfile.read_text(encoding="utf-8")).get("teks", "") if pfile.exists() else ""
            if not teks:
                continue
            # Hanya tautkan "Pasal N" bila peraturan yang dirujuk muncul dekat penyebutannya,
            # supaya nomor pasal dari PP/PMK lain tidak salah ditempel ke UU pajak.
            for m in re.finditer(r"(?i)\bPasal\s+(\d+[A-Z]?)\b", teks):
                pno = m.group(1).upper()
                snippet = teks[max(0, m.start() - 120): m.start() + 280]
                cits = extract_citations({
                    "document_id": sid, "jenis": "SEMA", "judul": it.get("judul_rumusan") or "",
                    "preamble": "",
                    "provisions": [{"level": "PASAL", "nomor": "1", "text": snippet}],
                    "penjelasan": "",
                })
                for c in cits:
                    did = c["resolved_document_id"]
                    if did.startswith("MK-") or did == sid:
                        continue
                    sema_map.setdefault((did, pno), []).append(sid)
    return mk_map, sema_map


def domain_for(doc_id: str) -> str:
    if doc_id.startswith("PERDA-"):
        return "PERDA_PDRD"
    for ids, dom in DOMAIN_RULES:
        if doc_id in ids:
            return dom
    return "LAINNYA"


def _norm_pph_id(fn: str, d: dict) -> str | None:
    did = d.get("document_id")
    if did:
        parts = did.split("_")
        if len(parts) == 3:
            j = "PER-DJP" if parts[0] == "PER" else parts[0]
            no = int(parts[1]) if parts[1].isdigit() else parts[1]
            return f"{j}-{parts[2]}-{no}"
    m = re.match(r"^(UU|PP|PMK|PER|PERPRES|PERPU)_(\d+)_(?:PMK\.\d+_|PJ_)?(\d{4})_", fn)
    if m:
        j = "PER-DJP" if m.group(1) == "PER" else m.group(1)
        return f"{j}-{m.group(3)}-{int(m.group(2))}"
    return None


def _collect_lampiran(nodes: list) -> list[dict]:
    out = []
    for n in nodes or []:
        if n.get("jenis_elemen") in ("LAMPIRAN", "BAGIAN_LAMPIRAN"):
            out.append({
                "jenis_elemen": n.get("jenis_elemen"),
                "judul": n.get("judul"),
                "teks": n.get("teks"),
                "halaman_sumber": n.get("halaman_sumber"),
            })
        out.extend(_collect_lampiran(n.get("children") or []))
    return out


def merge_pph_op() -> list[str]:
    existing = {p.stem for p in DOCS.glob("*.json")}
    added = []
    if not PPH_OP_FULL.exists():
        print("[WARN] pph_op/full tidak ditemukan")
        return added
    for f in sorted(PPH_OP_FULL.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        cid = _norm_pph_id(f.name, d)
        if not cid or cid in existing or cid == "UU-2011-12":
            continue
        raw_pages = d.get("raw_pages") or []
        text = "\n\n".join(p.get("content") or p.get("text") or "" for p in raw_pages)
        if not text.strip():
            continue
        TEXT.joinpath(f"{cid}.txt").write_text(text, encoding="utf-8")

        batang, _ = cut_penjelasan(text)
        _, arts, _ = split_pasal(batang)
        parsed = parse_document(cid, text)

        judul = (d.get("nama_dokumen")
                 or (d.get("metadata") or {}).get("document_name")
                 or f.stem.replace("_", " "))
        jenis = cid.split("-")[0] if not cid.startswith("PER-DJP") else "PER-DJP"
        tahun = int(cid.split("-")[-2])
        status_sumber = "Tidak Berlaku" if cid == "PP-1994-42" else "Berlaku"

        extra = {
            "status_sumber": status_sumber,
            "structure": parsed["structure"],
            "preamble": parsed["preamble"],
            "source_urls": [{"source": "pph_op_corpus", "file": f.name}],
        }
        lamp = _collect_lampiran(d.get("isi_dokumen") or [])
        if lamp:
            extra["lampiran"] = lamp

        rec = canon_doc(
            cid, jenis, tahun, judul, arts,
            {"origin": "merged_pph_op", "file": f.name, "pages": len(raw_pages)},
            extra=extra,
        )
        rec["penjelasan"] = parsed["penjelasan"]
        rec["penjelasan_articles"] = parsed["penjelasan_articles"]
        rec["provisions"] = parsed["provisions"]
        rec["structure"] = parsed["structure"]
        rec["quality"]["ocr_suspect"] = False
        rec["quality"]["zero_pasal"] = (len(parsed["provisions"]) == 0 and len(arts) == 0)
        DOCS.joinpath(f"{cid}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        existing.add(cid)
        added.append(cid)
        n_pas = sum(1 for p in parsed["provisions"] if p["level"] == "PASAL")
        print(f"  [MERGE pph_op] {cid:15} {parsed['structure']:14} pasal={n_pas:3} pages={len(raw_pages):3}")
    return added


def run_consolidations() -> dict[str, dict]:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    CONS.mkdir(parents=True, exist_ok=True)
    out = {}
    for target, chain in cfg.get("chains", {}).items():
        if (DOCS / f"{target}.json").exists():
            res = consolidate(target, chain or [], DOCS, CONS, TEXT)
        elif (PERDA / f"{target}.json").exists():
            res = consolidate(target, chain or [], PERDA, CONS, ROOT / "data" / "perda_ocr_text")
        else:
            print(f"  [SKIP CONS] {target}: tidak ditemukan")
            continue
        sub = parse_pasals_to_subprovisions(target, res["provisions"])
        res["sub_provisions"] = sub
        (CONS / f"{target}.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        out[target] = res
        print(f"  [CONS] {target:28} applied={res['applied_count']:3} "
              f"unparsed={res['unparsed_count']:2} pasals={len(res['provisions']):3} sub={len(sub):4}")
    return out


_CUT_TAIL_RE = re.compile(
    r"(?im)^\s*(?:Agar\s+setiap\s+orang\s+mengetahuinya\b|"
    r"Ditetapkan\s+di\s+[A-Z]|"
    r"LAMPIRAN\s+(?:[IVXLC]+\b|HURUF\b|PERATURAN\b|KEPUTUSAN\b))"
)


def _trim_tail(text: str) -> str:
    m = _CUT_TAIL_RE.search(text or "", 20) if len(text or "") > 20 else None
    return text[:m.start()].strip() if m else (text or "").strip()


def classify_pasal_role(nomor: str, text: str, base_role: str | None) -> str:
    trimmed = _trim_tail(text)
    low = trimmed.lower()
    if base_role in ("AMENDING_INSTRUCTION", "EFFECTIVITY"):
        return "AMENDMENT_INSTR"
    if re.match(r"(?i)^\s*Beberapa ketentuan dalam\b", trimmed):
        return "AMENDMENT_INSTR"
    if (nomor == "1" and "yang dimaksud" in low) or base_role == "DEFINITION":
        return "DEFINITION"
    if "dicabut dan dinyatakan tidak berlaku" in low and len(low) < 25000:
        # catatan: pasal panjang berisi substansi + pencabutan tetap boleh di-chunk jika bukan murni penutup;
        # tandai CLOSING bila diawali 'Pada saat ... mulai berlaku'
        if re.match(r"(?i)\s*pada saat\b", low):
            return "CLOSING"
    if re.search(r"(?i)\bmulai berlaku\s+(?:pada\s+tanggal|sejak|setelah)\b", low) and len(low) < 1200:
        return "CLOSING"
    if re.search(r"(?i)^pada saat .*? mulai berlaku", low) and "masih tetap berlaku" in low and len(low) < 1500:
        return "TRANSITIONAL"
    return "SUBSTANTIVE"


def build_scope_manifest() -> None:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    chained_amenders = set()
    for ch in cfg.get("chains", {}).values():
        chained_amenders.update(ch or [])
    chained_amenders.discard("UU-2023-6")  # UU 6/2023 konsolidasinya sudah diterapkan; tetap skip ekstraksi ulang

    cons_ids = {p.stem for p in CONS.glob("*.json")}
    candidates: list[tuple[Path, str]] = []
    for p in sorted(DOCS.glob("*.json")):
        candidates.append((p, "national"))
    for pid in PILOT_PERDAS:
        pp = PERDA / f"{pid}.json"
        if pp.exists():
            candidates.append((pp, "pilot_perda"))

    mk_map, sema_map = _build_review_ref_maps()
    rows = []
    dom_counts: Counter = Counter()
    role_counts: Counter = Counter()

    for p, pool in candidates:
        d = json.loads(p.read_text(encoding="utf-8"))
        did = d["document_id"]
        if d.get("jenis") in ("MANUAL", "LAMPIRAN") or did in NOISE_IDS:
            continue
        if d.get("status_sumber") == "Tidak Berlaku":
            continue
        if did in chained_amenders and (
            d.get("structure") == "AMENDING_ROMAN"
            or re.search(r"(?i)perubahan\s+.*atas\s+", d.get("judul") or "")
        ):
            continue
        if did == "UU-2023-6":
            continue  # perubahan pajak CK sudah dikonsolidasikan ke KUP/PPh/PPN

        dom = domain_for(did)
        use_cons = did in cons_ids
        if use_cons:
            c = json.loads((CONS / f"{did}.json").read_text(encoding="utf-8"))
            pasals = [sp for sp in c.get("sub_provisions", []) if sp["level"] == "PASAL"]
            src_kind = "consolidated"
        else:
            pasals = [pr for pr in d.get("provisions", []) if pr["level"] == "PASAL"]
            if not pasals and d.get("articles"):
                pasals = [{"nomor": str(a.get("nomor", "")), "text": a.get("text", ""),
                           "locator": a.get("locator", f"{did}#BT/{a.get('nomor','')}"),
                           "role": a.get("role")} for a in d["articles"]]
            src_kind = "document"

        for pr in pasals:
            pno = str(pr.get("nomor", ""))
            # Di UU-2021-7 (HPP), Pasal 2/3/4/14 sudah dikonsolidasi ke KUP/PPh/PPN/Cukai;
            # hanya simpan Pasal 1 (asas) & Pasal 13 (Pajak Karbon) dll.
            if did == "UU-2021-7" and pno in ("2", "3", "4", "14"):
                role = "AMENDMENT_INSTR"
            else:
                role = classify_pasal_role(pno, pr.get("text") or "", pr.get("role"))
            extract_t2 = role in ("SUBSTANTIVE", "DEFINITION")
            pno_key = pno.upper()
            mk_refs = list(dict.fromkeys(mk_map.get((did, pno_key), [])))
            if did.startswith("PERDA-") and re.search(r"(?i)\bmandi\s+uap\b|\bspa\b", pr.get("text") or ""):
                if "MK-2024-19-PUU-XXII" not in mk_refs:
                    mk_refs.append("MK-2024-19-PUU-XXII")
            sema_refs = list(dict.fromkeys(sema_map.get((did, pno_key), [])))
            row_rec = {
                "document_id": did,
                "pool": pool,
                "domain": dom,
                "source_kind": src_kind,
                "locator": pr.get("locator") or f"{did}#BT/{pr.get('nomor','')}",
                "pasal_nomor": str(pr.get("nomor", "")),
                "role": role,
                "extract_t2": extract_t2,
                "text_len": len(pr.get("text") or ""),
            }
            if mk_refs:
                row_rec["mk_review_refs"] = mk_refs
            if sema_refs:
                row_rec["sema_tun_refs"] = sema_refs
            rows.append(row_rec)
            dom_counts[dom] += 1
            role_counts[role] += 1

    with SCOPE_OUT.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    t2_rows = [r for r in rows if r["extract_t2"]]
    print(f"\n[SCOPE] total pasal={len(rows)} | extract_t2={len(t2_rows)}")
    print("  by_domain:", dict(sorted(dom_counts.items())))
    print("  by_role  :", dict(sorted(role_counts.items())))


def main() -> int:
    print("== 1. Merge dokumen unik dari pph_op/full ==")
    added = merge_pph_op()
    print(f"  ditambahkan: {len(added)} dokumen")

    print("\n== 2. Konsolidasi ulang (termasuk CK + PMK-2024-118 + Perda Semarang) & re-parse sub_provisions ==")
    run_consolidations()

    print("\n== 3. Bangun scope_manifest.jsonl ==")
    build_scope_manifest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
