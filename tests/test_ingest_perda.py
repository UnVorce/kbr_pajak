# -*- coding: utf-8 -*-
"""Tes pembuat ID Perda daerah (scripts/ingest_perda.py)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.ingest_perda import make_perda_id  # noqa: E402


def test_make_perda_id_unique_by_region():
    used: set[str] = set()
    id1 = make_perda_id("perda-prov-dki-jakarta-no-1-tahun-2024", 2024, "279709", used)
    id2 = make_perda_id("perda-kota-bandung-no-1-tahun-2024", 2024, "999999", used)
    id3 = make_perda_id("perda-prov-dki-jakarta-no-1-tahun-2024", 2024, "888888", used)
    assert id1 == "PERDA-PROV-DKI-JAKARTA-2024-1"
    assert id2 == "PERDA-KOTA-BANDUNG-2024-1"
    assert id3 == "PERDA-PROV-DKI-JAKARTA-2024-1-BPK888888"
