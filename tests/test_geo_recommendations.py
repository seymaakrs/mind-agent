"""Tests for _generate_geo_recommendations in web_tools.py.

Tests that GEO readiness results produce user-friendly Turkish recommendations.
Each recommendation has: category, priority (high/medium/low), action, reason.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tools.web_tools import _generate_geo_recommendations


# ============================================================================
# Helpers
# ============================================================================

def _make_geo_result(**overrides):
    """Build a full GEO result dict with defaults (all scores = max)."""
    base = {
        "geo_readiness_score": 100,
        "ai_crawler_access": {
            "score": 25, "max": 25,
            "bots_allowed": ["GPTBot", "ClaudeBot", "PerplexityBot"],
            "bots_blocked": [],
            "bots_not_mentioned": [],
        },
        "content_structure": {
            "score": 25, "max": 25,
            "has_faq_section": True,
            "faq_schema": True,
            "tables_count": 2,
            "lists_count": 4,
            "question_headings_count": 3,
        },
        "citation_data": {
            "score": 25, "max": 25,
            "external_citations": 8,
            "citation_density_per_1k": 4.0,
            "statistics_count": 10,
            "statistics_density_per_1k": 5.0,
        },
        "ai_discovery": {
            "score": 25, "max": 25,
            "has_llms_txt": True,
            "geo_schema_types_present": ["FAQPage", "Organization", "Article"],
            "geo_schema_types_missing": [],
            "freshness_signals": ["time_element", "schema_date", "last_modified_header"],
        },
    }
    for key, val in overrides.items():
        if key in base and isinstance(val, dict):
            base[key].update(val)
        else:
            base[key] = val
    return base


# ============================================================================
# Recommendation Format Tests
# ============================================================================

class TestGEORecommendationFormat:
    """Verify that each recommendation has the required fields."""

    def test_recommendation_is_list(self):
        """Return value should be a list."""
        geo = _make_geo_result(
            ai_crawler_access={"score": 0, "bots_blocked": ["GPTBot", "ClaudeBot"]},
        )
        result = _generate_geo_recommendations(geo)
        assert isinstance(result, list)

    def test_each_recommendation_has_required_keys(self):
        """Each item must have category, priority, action, reason."""
        geo = _make_geo_result(
            ai_crawler_access={"score": 0, "bots_blocked": ["GPTBot"]},
        )
        result = _generate_geo_recommendations(geo)
        assert len(result) > 0, "Should produce at least one recommendation"
        for rec in result:
            assert "category" in rec, f"Missing 'category' in {rec}"
            assert "priority" in rec, f"Missing 'priority' in {rec}"
            assert "action" in rec, f"Missing 'action' in {rec}"
            assert "reason" in rec, f"Missing 'reason' in {rec}"

    def test_priority_values_are_valid(self):
        """Priority must be one of: high, medium, low."""
        geo = _make_geo_result(
            content_structure={"score": 0, "has_faq_section": False, "tables_count": 0,
                               "lists_count": 0, "question_headings_count": 0},
        )
        result = _generate_geo_recommendations(geo)
        valid_priorities = {"high", "medium", "low"}
        for rec in result:
            assert rec["priority"] in valid_priorities, \
                f"Invalid priority '{rec['priority']}' in {rec}"

    def test_no_recommendations_for_perfect_scores(self):
        """A perfect GEO result should produce no recommendations."""
        geo = _make_geo_result()  # all max scores
        result = _generate_geo_recommendations(geo)
        assert result == [], f"Expected empty list for perfect GEO, got {len(result)} recs"


# ============================================================================
# AI Crawler Access Recommendations
# ============================================================================

class TestAICrawlerRecommendations:
    """Tests for AI Crawler Access category recommendations."""

    def test_bots_blocked(self):
        """Blocked bots should produce a high-priority recommendation."""
        geo = _make_geo_result(
            ai_crawler_access={
                "score": 5, "bots_blocked": ["GPTBot", "ClaudeBot", "PerplexityBot"],
                "bots_allowed": [], "bots_not_mentioned": [],
            },
        )
        result = _generate_geo_recommendations(geo)
        crawler_recs = [r for r in result if "yapay zeka" in r["action"].lower()
                        or "ai" in r["action"].lower()
                        or "bot" in r["action"].lower()
                        or "erişim" in r["action"].lower()]
        assert len(crawler_recs) >= 1, "Blocked bots should produce a rec"
        # Should be high priority
        high = [r for r in crawler_recs if r["priority"] == "high"]
        assert len(high) >= 1, "Blocked AI bots should be high priority"

    def test_all_bots_allowed_no_rec(self):
        """All bots allowed should produce no crawler rec."""
        geo = _make_geo_result()  # perfect
        result = _generate_geo_recommendations(geo)
        crawler_recs = [r for r in result if r["category"] == "AI Erişimi"]
        assert len(crawler_recs) == 0, "All bots allowed should produce no rec"


# ============================================================================
# Content Structure Recommendations
# ============================================================================

class TestContentStructureRecommendations:
    """Tests for Content Structure category recommendations."""

    def test_no_faq_section(self):
        """Missing FAQ should recommend adding one."""
        geo = _make_geo_result(
            content_structure={
                "score": 5, "has_faq_section": False, "faq_schema": False,
                "tables_count": 1, "lists_count": 2, "question_headings_count": 0,
            },
        )
        result = _generate_geo_recommendations(geo)
        faq_recs = [r for r in result if "sss" in r["action"].lower()
                    or "soru" in r["action"].lower()
                    or "faq" in r["action"].lower()]
        assert len(faq_recs) >= 1, "Missing FAQ should produce a rec"

    def test_no_tables_or_lists(self):
        """No tables/lists should recommend adding structured content."""
        geo = _make_geo_result(
            content_structure={
                "score": 3, "has_faq_section": False, "faq_schema": False,
                "tables_count": 0, "lists_count": 0, "question_headings_count": 0,
            },
        )
        result = _generate_geo_recommendations(geo)
        struct_recs = [r for r in result if "liste" in r["action"].lower()
                       or "tablo" in r["action"].lower()]
        assert len(struct_recs) >= 1, "No tables/lists should produce a rec"

    def test_no_question_headings(self):
        """No question headings should recommend adding some."""
        geo = _make_geo_result(
            content_structure={
                "score": 10, "has_faq_section": True, "faq_schema": True,
                "tables_count": 2, "lists_count": 3, "question_headings_count": 0,
            },
        )
        result = _generate_geo_recommendations(geo)
        q_recs = [r for r in result if "soru" in r["action"].lower()
                  or "başlık" in r["action"].lower()]
        assert len(q_recs) >= 1, "No question headings should produce a rec"


# ============================================================================
# Citation & Data Density Recommendations
# ============================================================================

class TestCitationRecommendations:
    """Tests for Citation & Data Density category recommendations."""

    def test_low_citation_density(self):
        """Low citations should recommend adding references."""
        geo = _make_geo_result(
            citation_data={
                "score": 3, "external_citations": 0,
                "citation_density_per_1k": 0,
                "statistics_count": 0, "statistics_density_per_1k": 0,
            },
        )
        result = _generate_geo_recommendations(geo)
        cite_recs = [r for r in result if "kaynak" in r["action"].lower()
                     or "link" in r["action"].lower()
                     or "referans" in r["action"].lower()]
        assert len(cite_recs) >= 1, "Low citations should produce a rec"

    def test_low_statistics(self):
        """Low statistics should recommend adding data."""
        geo = _make_geo_result(
            citation_data={
                "score": 10, "external_citations": 5,
                "citation_density_per_1k": 3.0,
                "statistics_count": 0, "statistics_density_per_1k": 0,
            },
        )
        result = _generate_geo_recommendations(geo)
        stat_recs = [r for r in result if "istatistik" in r["action"].lower()
                     or "veri" in r["action"].lower()
                     or "rakam" in r["action"].lower()]
        assert len(stat_recs) >= 1, "Low statistics should produce a rec"


# ============================================================================
# AI Discovery Recommendations
# ============================================================================

class TestAIDiscoveryRecommendations:
    """Tests for AI Discovery category recommendations."""

    def test_missing_llms_txt(self):
        """Missing llms.txt should recommend adding it."""
        geo = _make_geo_result(
            ai_discovery={
                "score": 5, "has_llms_txt": False,
                "geo_schema_types_present": [],
                "geo_schema_types_missing": ["FAQPage", "Organization"],
                "freshness_signals": [],
            },
        )
        result = _generate_geo_recommendations(geo)
        llms_recs = [r for r in result if "llms.txt" in r["action"].lower()
                     or "llms" in r["action"].lower()]
        assert len(llms_recs) >= 1, "Missing llms.txt should produce a rec"

    def test_missing_schema_types(self):
        """Missing GEO schema types should recommend adding them."""
        geo = _make_geo_result(
            ai_discovery={
                "score": 8, "has_llms_txt": True,
                "geo_schema_types_present": [],
                "geo_schema_types_missing": ["FAQPage", "Organization", "LocalBusiness"],
                "freshness_signals": ["time_element"],
            },
        )
        result = _generate_geo_recommendations(geo)
        schema_recs = [r for r in result if "yapılandırılmış" in r["action"].lower()
                       or "bilgi" in r["action"].lower()
                       or "schema" in r["action"].lower()
                       or "işletme" in r["action"].lower()]
        assert len(schema_recs) >= 1, "Missing schema types should produce a rec"

    def test_no_freshness_signals(self):
        """No freshness signals should recommend adding dates."""
        geo = _make_geo_result(
            ai_discovery={
                "score": 10, "has_llms_txt": True,
                "geo_schema_types_present": ["Organization"],
                "geo_schema_types_missing": [],
                "freshness_signals": [],
            },
        )
        result = _generate_geo_recommendations(geo)
        date_recs = [r for r in result if "tarih" in r["action"].lower()
                     or "güncel" in r["action"].lower()
                     or "tarih" in r["reason"].lower()]
        assert len(date_recs) >= 1, "No freshness signals should produce a rec"


# ============================================================================
# Integrated / Realistic Scenario Tests
# ============================================================================

class TestGEORealisticScenarios:
    """Test with realistic GEO score combinations."""

    def test_typical_low_geo_site(self):
        """A typical site with no GEO optimization should get many recs."""
        geo = _make_geo_result(
            geo_readiness_score=20,
            ai_crawler_access={
                "score": 25, "bots_allowed": [],
                "bots_blocked": [], "bots_not_mentioned": ["GPTBot"],
            },
            content_structure={
                "score": 0, "has_faq_section": False, "faq_schema": False,
                "tables_count": 0, "lists_count": 0, "question_headings_count": 0,
            },
            citation_data={
                "score": 0, "external_citations": 0,
                "citation_density_per_1k": 0,
                "statistics_count": 0, "statistics_density_per_1k": 0,
            },
            ai_discovery={
                "score": 0, "has_llms_txt": False,
                "geo_schema_types_present": [],
                "geo_schema_types_missing": ["FAQPage", "Organization"],
                "freshness_signals": [],
            },
        )
        result = _generate_geo_recommendations(geo)
        assert len(result) >= 3, \
            f"Unoptimized site should get >=3 GEO recs, got {len(result)}"

    def test_well_optimized_geo_few_recs(self):
        """A well-optimized GEO site should have very few recs."""
        geo = _make_geo_result()  # perfect scores
        result = _generate_geo_recommendations(geo)
        assert len(result) <= 2, \
            f"Well-optimized GEO should have <=2 recs, got {len(result)}"

    def test_recommendations_in_turkish(self):
        """All recommendations should be in Turkish (no English-only text)."""
        geo = _make_geo_result(
            content_structure={
                "score": 0, "has_faq_section": False, "faq_schema": False,
                "tables_count": 0, "lists_count": 0, "question_headings_count": 0,
            },
            citation_data={
                "score": 0, "external_citations": 0,
                "citation_density_per_1k": 0,
                "statistics_count": 0, "statistics_density_per_1k": 0,
            },
        )
        result = _generate_geo_recommendations(geo)
        # Turkish indicators: ı, ş, ç, ğ, ü, ö, İ
        turkish_chars = set("ışçğüöİŞÇĞÜÖ")
        for rec in result:
            combined = rec["action"] + rec["reason"]
            has_turkish = any(c in combined for c in turkish_chars)
            assert has_turkish, \
                f"Recommendation should contain Turkish chars: {rec['action']}"
