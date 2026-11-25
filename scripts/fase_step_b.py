# -*- coding: utf-8 -*-
"""CLI Step B — Bangun graf RDF TER PPh 21 (PP 58/2023) & SKOS KBLI (PER-17/PJ/2015 + PP 78/2019)."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ter_kbli import (
    export_kbli_skos_ttl,
    export_ter_ttl,
    parse_per17_lampiran,
    parse_perbkpm_industri_pionir,
    parse_pmk16_padat_karya,
    parse_pp58_ter,
    parse_pp78_tax_allowance,
)


def _pick(*rels: str) -> Path:
    for r in rels:
        p = ROOT / r
        if p.exists():
            return p
    return ROOT / rels[0]


def main() -> int:
    # 1. TER PPh 21 (PP 58/2023)
    brackets = parse_pp58_ter(_pick("data/text/PP-2023-58.txt", "knowledge_json/text_lampiran/PP-2023-58.txt"))
    ter_out = ROOT / "ontology" / "kbr_ter_pph21.ttl"
    ter_count = export_ter_ttl(brackets, ter_out)
    ter_counts = dict(Counter(b.kategori for b in brackets))

    # 2. KBLI SKOS (PER-17/PJ/2015 Lampiran 1-3 + PP 78/2019 + PerBKPM 7/2020 + PMK 16/2020)
    per17_local = ROOT / "knowledge_json" / "text_lampiran"
    per17_dir = per17_local if (per17_local / "Lampiran 1_PER - 17.PJ_.2015.txt").exists() else (ROOT.parent / "forNow" / "knowledge_txt" / "4_PER_DGTRegulations")
    lamp1 = parse_per17_lampiran(per17_dir / "Lampiran 1_PER - 17.PJ_.2015.txt")
    lamp2 = parse_per17_lampiran(per17_dir / "Lampiran 2_PER - 17.PJ_.2015.txt")
    lamp3 = parse_per17_lampiran(per17_dir / "Lampiran 3_PER - 17.PJ_.2015.txt")
    pp78 = parse_pp78_tax_allowance(_pick("data/text/PP-2019-78.txt", "knowledge_json/text_lampiran/PP-2019-78.txt"), lamp1)
    perbkpm7 = parse_perbkpm_industri_pionir(_pick("data/text/PERBKPM-2020-7-LAMP.txt", "knowledge_json/text_lampiran/PERBKPM-2020-7-LAMP.txt"))
    pmk16 = parse_pmk16_padat_karya(_pick("data/text/PMK-2020-16-LAMP-OCR.txt", "knowledge_json/text_lampiran/PMK-2020-16-LAMP-OCR.txt"))

    kbli_out = ROOT / "ontology" / "kbr_kbli.ttl"
    kbli_summary = export_kbli_skos_ttl(
        lamp1=lamp1,
        lamp2=lamp2,
        lamp3=lamp3,
        pp78=pp78,
        perbkpm7=perbkpm7,
        pmk16=pmk16,
        out_ttl=kbli_out,
    )

    summary = {
        "ter_ttl": str(ter_out),
        "ter_total_brackets": ter_count,
        "ter_by_category": ter_counts,
        "kbli": kbli_summary,
    }
    (ROOT / "ontology" / "step_b_build_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
