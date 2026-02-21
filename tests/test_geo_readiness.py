"""Tests for _analyze_geo_readiness in web_tools.py.

Tests the 4-category GEO scoring algorithm (100 points max):
  - AI Crawler Access (25p)
  - Content Structure (25p)
  - Citation & Data Density (25p)
  - AI Discovery (25p)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bs4 import BeautifulSoup
from src.tools.web_tools import _analyze_geo_readiness


def _soup(html: str) -> BeautifulSoup:
    """Helper to create BeautifulSoup from HTML string."""
    return BeautifulSoup(html, "html.parser")


def _base_args(**overrides):
    """Create base arguments for _analyze_geo_readiness with defaults."""
    defaults = {
        "soup": _soup("<html><body><p>Hello</p></body></html>"),
        "main_text": "Hello world",
        "robots_result": {"has_robots_txt": False},
        "llms_result": {"has_llms_txt": False},
        "schema_data": {"schema_types": [], "schema_data": []},
        "content_quality": {"word_count": 500},
        "links": {"external_links": 0},
        "response_headers": {},
    }
    defaults.update(overrides)
    return defaults


# ============================================================================
# Category 1: AI Crawler Access (25 max)
# ============================================================================

class TestAICrawlerAccess:
    """Tests for robots.txt AI bot access scoring."""

    def test_no_robots_txt_full_score(self):
        """No robots.txt = all bots allowed = 25 points."""
        args = _base_args(robots_result={"has_robots_txt": False})
        result = _analyze_geo_readiness(**args)
        assert result["ai_crawler_access"]["score"] == 25

    def test_all_bots_allowed(self):
        """All 9 bots explicitly allowed = 25 points."""
        all_bots = [
            "GPTBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot",
            "PerplexityBot", "Perplexity-User", "Google-Extended",
            "Applebot-Extended", "YouBot",
        ]
        args = _base_args(robots_result={
            "has_robots_txt": True,
            "ai_bots_access": {
                "bots_allowed": all_bots,
                "bots_blocked": [],
                "bots_not_mentioned": [],
            },
        })
        result = _analyze_geo_readiness(**args)
        assert result["ai_crawler_access"]["score"] == 25

    def test_all_bots_blocked(self):
        """All 9 bots blocked = 0 points."""
        all_bots = [
            "GPTBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot",
            "PerplexityBot", "Perplexity-User", "Google-Extended",
            "Applebot-Extended", "YouBot",
        ]
        args = _base_args(robots_result={
            "has_robots_txt": True,
            "ai_bots_access": {
                "bots_allowed": [],
                "bots_blocked": all_bots,
                "bots_not_mentioned": [],
            },
        })
        result = _analyze_geo_readiness(**args)
        assert result["ai_crawler_access"]["score"] == 0

    def test_partial_bot_access(self):
        """Some bots allowed, some not mentioned = proportional score."""
        args = _base_args(robots_result={
            "has_robots_txt": True,
            "ai_bots_access": {
                "bots_allowed": ["GPTBot", "ClaudeBot"],
                "bots_blocked": ["PerplexityBot"],
                "bots_not_mentioned": ["ChatGPT-User", "Claude-SearchBot",
                                        "Perplexity-User", "Google-Extended",
                                        "Applebot-Extended", "YouBot"],
            },
        })
        result = _analyze_geo_readiness(**args)
        # 2 allowed + 6 not_mentioned = 8 accessible out of 9
        expected = round(25 * 8 / 9)
        assert result["ai_crawler_access"]["score"] == expected


# ============================================================================
# Category 2: Content Structure (25 max)
# ============================================================================

class TestContentStructure:
    """Tests for FAQ sections, tables, lists, question headings."""

    def test_faq_schema_detected(self):
        """FAQPage schema = 5 points."""
        args = _base_args(
            schema_data={"schema_types": ["FAQPage"], "schema_data": []},
        )
        result = _analyze_geo_readiness(**args)
        cs = result["content_structure"]
        assert cs["faq_schema"] is True
        assert cs["score"] >= 5

    def test_details_summary_element(self):
        """<details> element present = 3 points."""
        html = "<html><body><details><summary>FAQ</summary><p>Answer</p></details></body></html>"
        args = _base_args(soup=_soup(html))
        result = _analyze_geo_readiness(**args)
        cs = result["content_structure"]
        assert cs["has_faq_section"] is True
        assert cs["score"] >= 3

    def test_question_headings_scored(self):
        """H2/H3 headings with question marks earn points."""
        html = """
        <html><body>
            <h2>What is SEO?</h2>
            <h2>How does it work?</h2>
            <h3>Why choose us?</h3>
        </body></html>
        """
        args = _base_args(soup=_soup(html))
        result = _analyze_geo_readiness(**args)
        cs = result["content_structure"]
        assert cs["question_headings_count"] == 3
        # 3 questions * 2 points each = 6 points (capped at 7)
        assert cs["score"] >= 6

    def test_question_headings_capped_at_7(self):
        """Question heading points capped at 7."""
        html = "<html><body>"
        for i in range(10):
            html += f"<h2>Question {i}?</h2>"
        html += "</body></html>"
        args = _base_args(soup=_soup(html))
        result = _analyze_geo_readiness(**args)
        # 10 * 2 = 20, but capped at 7
        # Total should reflect the cap
        cs = result["content_structure"]
        assert cs["question_headings_count"] == 10

    def test_tables_and_lists(self):
        """Tables and multiple lists earn points."""
        html = """
        <html><body>
            <table><tr><td>Data</td></tr></table>
            <ul><li>A</li></ul>
            <ul><li>B</li></ul>
            <ol><li>1</li></ol>
        </body></html>
        """
        args = _base_args(soup=_soup(html))
        result = _analyze_geo_readiness(**args)
        cs = result["content_structure"]
        assert cs["tables_count"] == 1
        assert cs["lists_count"] == 3  # 2 ul + 1 ol
        # table=3, ul>=2=2, ol>0=3 = 8 points
        assert cs["score"] >= 8

    def test_empty_html_zero_structure(self):
        """Minimal HTML = 0 content structure score."""
        args = _base_args()
        result = _analyze_geo_readiness(**args)
        assert result["content_structure"]["score"] == 0

    def test_content_structure_capped_at_25(self, geo_perfect_html, make_soup):
        """Content structure score cannot exceed 25."""
        args = _base_args(
            soup=make_soup(geo_perfect_html),
            schema_data={"schema_types": ["FAQPage"], "schema_data": []},
        )
        result = _analyze_geo_readiness(**args)
        assert result["content_structure"]["score"] <= 25


# ============================================================================
# Category 3: Citation & Data Density (25 max)
# ============================================================================

class TestCitationDensity:
    """Tests for external citation and statistics density."""

    def test_high_citation_density(self):
        """3+ external links per 1k words = 13 points."""
        args = _base_args(
            content_quality={"word_count": 1000},
            links={"external_links": 4},
        )
        result = _analyze_geo_readiness(**args)
        cd = result["citation_data"]
        assert cd["citation_density_per_1k"] == 4.0
        assert cd["score"] >= 13

    def test_low_citation_density(self):
        """0.5-1 external links per 1k words = 4 points."""
        args = _base_args(
            content_quality={"word_count": 2000},
            links={"external_links": 1},
        )
        result = _analyze_geo_readiness(**args)
        cd = result["citation_data"]
        assert cd["citation_density_per_1k"] == 0.5
        assert cd["score"] >= 4

    def test_zero_citations(self):
        """No external links = 0 citation points."""
        args = _base_args(
            content_quality={"word_count": 1000},
            links={"external_links": 0},
        )
        result = _analyze_geo_readiness(**args)
        assert result["citation_data"]["external_citations"] == 0

    def test_statistics_detection(self):
        """Text with percentages, years, currency detected."""
        text = "In 2025, 68% of users prefer mobile. Revenue reached ₺5000 per month. The area is 100 m² with 2,500 visitors."
        args = _base_args(
            main_text=text,
            content_quality={"word_count": 500},
        )
        result = _analyze_geo_readiness(**args)
        cd = result["citation_data"]
        # Should detect: 2025, 68%, ₺5000, 100 m², 2,500
        assert cd["statistics_count"] >= 4

    def test_citation_capped_at_25(self):
        """Citation score cannot exceed 25."""
        text = "Stats: 50% growth, 75% retention, $100, €200, ₺300, 2024, 2025, 2026, " * 20
        args = _base_args(
            main_text=text,
            content_quality={"word_count": 200},
            links={"external_links": 20},
        )
        result = _analyze_geo_readiness(**args)
        assert result["citation_data"]["score"] <= 25


# ============================================================================
# Category 4: AI Discovery (25 max)
# ============================================================================

class TestAIDiscovery:
    """Tests for llms.txt, schema types, freshness signals."""

    def test_llms_txt_present(self):
        """llms.txt exists = 6 points."""
        args = _base_args(
            llms_result={"has_llms_txt": True, "has_llms_full": False},
        )
        result = _analyze_geo_readiness(**args)
        assert result["ai_discovery"]["has_llms_txt"] is True
        assert result["ai_discovery"]["score"] >= 6

    def test_llms_txt_with_full(self):
        """llms.txt + llms-full.txt = 8 points."""
        args = _base_args(
            llms_result={"has_llms_txt": True, "has_llms_full": True},
        )
        result = _analyze_geo_readiness(**args)
        assert result["ai_discovery"]["score"] >= 8

    def test_geo_schema_types(self):
        """Each GEO-critical schema type = 2 points (max 10)."""
        args = _base_args(
            schema_data={
                "schema_types": ["FAQPage", "HowTo", "Organization", "Article", "Product"],
                "schema_data": [],
            },
        )
        result = _analyze_geo_readiness(**args)
        ad = result["ai_discovery"]
        assert len(ad["geo_schema_types_present"]) == 5
        assert ad["score"] >= 10  # 5 types * 2 = 10

    def test_missing_schema_types_reported(self):
        """Missing GEO schema types are listed."""
        args = _base_args(
            schema_data={"schema_types": ["Organization"], "schema_data": []},
        )
        result = _analyze_geo_readiness(**args)
        ad = result["ai_discovery"]
        assert "Organization" in ad["geo_schema_types_present"]
        assert "FAQPage" in ad["geo_schema_types_missing"]
        assert "HowTo" in ad["geo_schema_types_missing"]

    def test_freshness_time_element(self):
        """<time> element detected as freshness signal."""
        html = '<html><body><time datetime="2026-01-01">Jan 2026</time></body></html>'
        args = _base_args(soup=_soup(html))
        result = _analyze_geo_readiness(**args)
        assert "time_element" in result["ai_discovery"]["freshness_signals"]

    def test_freshness_schema_date(self):
        """Schema datePublished detected as freshness signal."""
        args = _base_args(
            schema_data={
                "schema_types": [],
                "schema_data": [{"@type": "Article", "datePublished": "2026-01-15"}],
            },
        )
        result = _analyze_geo_readiness(**args)
        assert "schema_date" in result["ai_discovery"]["freshness_signals"]

    def test_freshness_last_modified_header(self):
        """Last-Modified header detected as freshness signal."""
        args = _base_args(
            response_headers={"last-modified": "Sat, 01 Feb 2026 10:00:00 GMT"},
        )
        result = _analyze_geo_readiness(**args)
        assert "last_modified_header" in result["ai_discovery"]["freshness_signals"]

    def test_no_discovery_signals(self):
        """No llms.txt, no schema, no freshness = 0 points."""
        args = _base_args()
        result = _analyze_geo_readiness(**args)
        assert result["ai_discovery"]["score"] == 0


# ============================================================================
# Full GEO Score Tests
# ============================================================================

class TestFullGEOScore:
    """End-to-end GEO readiness score tests."""

    def test_result_structure(self):
        """Result contains all 4 categories with score and max."""
        args = _base_args()
        result = _analyze_geo_readiness(**args)

        assert "geo_readiness_score" in result
        for category in ["ai_crawler_access", "content_structure",
                         "citation_data", "ai_discovery"]:
            assert category in result, f"Missing category: {category}"
            assert "score" in result[category]
            assert "max" in result[category]
            assert result[category]["max"] == 25

    def test_total_equals_sum_of_categories(self):
        """Total GEO score = sum of all 4 category scores."""
        args = _base_args()
        result = _analyze_geo_readiness(**args)
        category_sum = sum(
            result[cat]["score"]
            for cat in ["ai_crawler_access", "content_structure",
                        "citation_data", "ai_discovery"]
        )
        assert result["geo_readiness_score"] == category_sum

    def test_well_optimized_page(self, geo_perfect_html, make_soup):
        """A GEO-optimized page should score reasonably high."""
        args = _base_args(
            soup=make_soup(geo_perfect_html),
            main_text="In 2025, 68% of online experiences begin with a search engine. "
                      "Revenue reached ₺5000 per month. The area is 100 m² with 2,500 visitors.",
            robots_result={"has_robots_txt": False},
            llms_result={"has_llms_txt": True, "has_llms_full": True},
            schema_data={
                "schema_types": ["FAQPage", "Organization", "Article"],
                "schema_data": [{"@type": "Article", "datePublished": "2026-01-15"}],
            },
            content_quality={"word_count": 1000},
            links={"external_links": 5},
            response_headers={"last-modified": "Sat, 01 Feb 2026 10:00:00 GMT"},
        )
        result = _analyze_geo_readiness(**args)
        assert result["geo_readiness_score"] >= 60

    def test_empty_page_scores_low(self):
        """An unoptimized page should score low (except AI crawler if no robots.txt)."""
        args = _base_args()
        result = _analyze_geo_readiness(**args)
        # No robots.txt gives 25 points for AI crawler access
        # Everything else should be 0 or near 0
        non_crawler_score = (
            result["content_structure"]["score"]
            + result["citation_data"]["score"]
            + result["ai_discovery"]["score"]
        )
        assert non_crawler_score == 0
