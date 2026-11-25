# -*- coding: utf-8 -*-
"""CLI Step C — Bangun graf RDF tarif 524 Perda (390 Pemda) `ontology/kbr-perda-rates.ttl`."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.perda_rates import build_perda_rates_ttl


def main() -> int:
    perda_dir = ROOT / "data" / "perda"
    if not perda_dir.exists():
        perda_dir = ROOT / "knowledge_json" / "perda"
    summary = build_perda_rates_ttl(
        perda_dir=perda_dir,
        out_ttl=ROOT / "ontology" / "kbr-perda-rates.ttl",
    )
    (ROOT / "ontology" / "step_c_build_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
