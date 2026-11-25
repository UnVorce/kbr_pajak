# -*- coding: utf-8 -*-
"""Tes parser katalog Perda BPK (scripts/download_perda_pdf.py)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.download_perda_pdf import CARD_LINK_RE, LAST_PAGE_RE  # noqa: E402


def test_parse_perda_card_and_last_page():
    sample = """
    <div class="col-lg-8 fw-semibold fs-5">
      <a class="text-gray-600 text-decoration-none" href="/Details/279709/perda-prov-dki-jakarta-no-1-tahun-2024">
        Peraturan Daerah (PERDA) Provinsi DKI Jakarta Nomor 1 Tahun 2024
      </a>
    </div>
    <a class="text-danger" href="/Details/999/perda-lama">Perda Lama</a>
    <a class="page-link" href="/Search?tema=48&amp;jenis=19&amp;tahun=2024&amp;p=26">Last</a>
    """
    cards = CARD_LINK_RE.findall(sample)
    assert len(cards) == 1
    assert cards[0][1] == "279709"
    assert cards[0][2] == "perda-prov-dki-jakarta-no-1-tahun-2024"
    lm = LAST_PAGE_RE.search(sample)
    assert lm and lm.group(1) == "26"
