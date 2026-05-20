"""Outreach lead skorlama — outreach motorunu akilli sec."""
from __future__ import annotations

from unittest.mock import MagicMock

from src.agents.outreach.targeting import (
    _CANDIDATE_POOL_SIZE,
    pick_next_target,
    score_lead,
)


class TestScoreLead:
    def test_empty_lead_zero(self):
        assert score_lead({}) == 0

    def test_full_signals_max(self):
        lead = {
            "sirket_adi": "Bodrum Otel",
            "ad_soyad": "Ahmet Y.",
            "telefon": "+905551112233",
            "il": "Muğla",
        }
        # 3 + 2 + 2 + 1
        assert score_lead(lead) == 8

    def test_only_company_name(self):
        assert score_lead({"sirket_adi": "Otel X"}) == 3

    def test_tr_phone_bonus(self):
        assert score_lead({"telefon": "+905551112233"}) == 2
        assert score_lead({"telefon": "905551112233"}) == 2
        assert score_lead({"telefon": "+15551112233"}) == 0

    def test_target_region_match(self):
        assert score_lead({"il": "Antalya"}) == 2
        assert score_lead({"il": "İzmir"}) == 2
        assert score_lead({"il": "Ankara"}) == 0

    def test_sehir_fallback(self):
        assert score_lead({"sehir": "Muğla"}) == 2

    def test_ad_soyad_only(self):
        assert score_lead({"ad_soyad": "Ahmet"}) == 1


class TestPickNextTargetScoring:
    def test_fetches_candidate_pool_oldest_first(self):
        client = MagicMock()
        client.list_records.return_value = {"list": []}
        pick_next_target(client, "leads_tbl", "outreach_agent_v1")
        kwargs = client.list_records.call_args.kwargs
        assert kwargs["limit"] == _CANDIDATE_POOL_SIZE
        assert kwargs["sort"] == "CreatedAt"

    def test_picks_highest_score_not_oldest(self):
        client = MagicMock()
        client.list_records.return_value = {
            "list": [
                # Eski ama bos lead (score 0)
                {"Id": 1, "telefon": "+15551112233"},
                # Yeni ama Bodrum oteli (score 8) — KAZANIR
                {
                    "Id": 2,
                    "sirket_adi": "Bodrum Otel",
                    "ad_soyad": "Ahmet",
                    "telefon": "+905551112233",
                    "il": "Muğla",
                },
                # Orta — sirket adi var (score 3)
                {"Id": 3, "sirket_adi": "Otel C"},
            ]
        }
        target = pick_next_target(client, "leads_tbl", "outreach_agent_v1")
        assert target["Id"] == 2

    def test_tie_breaker_oldest_wins(self):
        # Esit skor -> NocoDB siralamasi FIFO; ilk siradaki kazanir
        client = MagicMock()
        client.list_records.return_value = {
            "list": [
                {"Id": 1, "sirket_adi": "Otel A"},  # score 3
                {"Id": 2, "sirket_adi": "Otel B"},  # score 3
            ]
        }
        target = pick_next_target(client, "leads_tbl", "outreach_agent_v1")
        assert target["Id"] == 1

    def test_empty_pool_returns_none(self):
        client = MagicMock()
        client.list_records.return_value = {"list": []}
        assert pick_next_target(client, "leads_tbl", "outreach_agent_v1") is None

    def test_custom_pool_size(self):
        client = MagicMock()
        client.list_records.return_value = {"list": []}
        pick_next_target(
            client, "leads_tbl", "outreach_agent_v1", candidate_pool=5
        )
        assert client.list_records.call_args.kwargs["limit"] == 5
