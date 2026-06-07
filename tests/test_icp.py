"""Faz 5 — ICP fit saf fonksiyonu testleri.

score_icp_fit() LLM'siz, deterministik çekirdek mantık: lead'in sektör + konum
(+ sinyaller) ICP'ye ne kadar uyuyor. Qualifier Agent bunu referans alır ama
nihai qualified kararını LLM verir.
"""
from __future__ import annotations

from src.tools.sales.icp import (
    TARGET_KONUMLAR,
    TARGET_SEKTORLER,
    score_icp_fit,
)


class TestSectorFit:
    def test_target_sector_scores_high(self):
        r = score_icp_fit(sektor="Otelcilik", konum="Bodrum")
        assert r["fit"] is True
        assert r["fit_score"] >= 60
        assert any("sektör" in reason.lower() for reason in r["reasons"])

    def test_each_target_sector_recognized(self):
        for sektor in TARGET_SEKTORLER:
            r = score_icp_fit(sektor=sektor, konum="Bodrum")
            assert r["fit_score"] >= 60, sektor

    def test_non_target_sector_lower(self):
        target = score_icp_fit(sektor="Otelcilik", konum="Bodrum")["fit_score"]
        other = score_icp_fit(sektor="Kurumsal-Kamu", konum="Bodrum")["fit_score"]
        assert other < target

    def test_unknown_sector_no_sector_points(self):
        r = score_icp_fit(sektor="Uzay Madenciligi", konum="Bodrum")
        # konum puanı var ama sektör puanı yok → fit eşiğinin altında
        assert r["fit"] is False


class TestLocationFit:
    def test_target_location_scores(self):
        for konum in TARGET_KONUMLAR:
            r = score_icp_fit(sektor="Otelcilik", konum=konum)
            assert any("konum" in reason.lower() for reason in r["reasons"]), konum

    def test_location_substring_match(self):
        # serbest metin konum içinde hedef şehir geçmesi yeterli
        r = score_icp_fit(sektor="Otelcilik", konum="Muğla / Bodrum merkez")
        assert r["fit"] is True

    def test_non_target_location_lower(self):
        target = score_icp_fit(sektor="Otelcilik", konum="Bodrum")["fit_score"]
        other = score_icp_fit(sektor="Otelcilik", konum="Ankara")["fit_score"]
        assert other < target


class TestEdgeCases:
    def test_missing_fields_no_crash(self):
        r = score_icp_fit(sektor=None, konum=None)
        assert r["fit"] is False
        assert r["fit_score"] == 0
        assert isinstance(r["reasons"], list)

    def test_score_capped_at_100(self):
        r = score_icp_fit(
            sektor="Otelcilik", konum="Bodrum", lead_skoru=100
        )
        assert r["fit_score"] <= 100

    def test_case_insensitive(self):
        lower = score_icp_fit(sektor="otelcilik", konum="bodrum")
        upper = score_icp_fit(sektor="OTELCILIK", konum="BODRUM")
        assert lower["fit_score"] == upper["fit_score"]
        assert lower["fit"] is True
