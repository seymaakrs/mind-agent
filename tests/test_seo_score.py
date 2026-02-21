"""Tests for _calculate_seo_score_v2 in web_tools.py.

Tests the 6-category SEO scoring algorithm (100 points max):
  - Technical SEO (25p)
  - On-Page SEO (25p)
  - Content Quality (20p)
  - Mobile & Performance (15p)
  - Schema & Structured Data (10p)
  - Authority Signals (5p)
  + Penalties (negative points)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tools.web_tools import _calculate_seo_score_v2


# ============================================================================
# Category 1: Technical SEO (25 max)
# ============================================================================

class TestTechnicalSEO:
    """Tests for robots.txt, sitemap, SSL, redirects, TTFB, canonical."""

    def test_robots_txt_present_and_allows_crawling(self):
        """robots.txt exists + allows crawling = 5 points."""
        analysis = {
            "meta_tags": {}, "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
            "robots_txt": {"has_robots_txt": True, "allows_crawling": True},
        }
        result = _calculate_seo_score_v2(analysis)
        tech = result["breakdown"]["technical_seo"]
        assert tech["details"]["robots_txt"] == 5

    def test_robots_txt_present_but_blocks_crawling(self):
        """robots.txt exists but blocks = only 3 points."""
        analysis = {
            "meta_tags": {}, "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
            "robots_txt": {"has_robots_txt": True, "allows_crawling": False},
        }
        result = _calculate_seo_score_v2(analysis)
        tech = result["breakdown"]["technical_seo"]
        assert tech["details"]["robots_txt"] == 3

    def test_no_robots_txt(self):
        """No robots.txt = 0 points."""
        analysis = {
            "meta_tags": {}, "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
            "robots_txt": {"has_robots_txt": False},
        }
        result = _calculate_seo_score_v2(analysis)
        tech = result["breakdown"]["technical_seo"]
        assert tech["details"]["robots_txt"] == 0

    def test_sitemap_full_score(self):
        """Sitemap with URLs and lastmod = 5 points."""
        analysis = {
            "meta_tags": {}, "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
            "sitemap": {"has_sitemap": True, "url_count": 50, "has_lastmod": True},
        }
        result = _calculate_seo_score_v2(analysis)
        tech = result["breakdown"]["technical_seo"]
        assert tech["details"]["sitemap"] == 5

    def test_ttfb_fast(self):
        """TTFB < 500ms = 4 points."""
        analysis = {
            "meta_tags": {}, "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "redirect_count": 0,
            "ttfb_ms": 200,
        }
        result = _calculate_seo_score_v2(analysis)
        assert result["breakdown"]["technical_seo"]["details"]["ttfb"] == 4

    def test_ttfb_slow(self):
        """TTFB >= 3000ms = 0 points."""
        analysis = {
            "meta_tags": {}, "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "redirect_count": 0,
            "ttfb_ms": 5000,
        }
        result = _calculate_seo_score_v2(analysis)
        assert result["breakdown"]["technical_seo"]["details"]["ttfb"] == 0

    def test_ttfb_boundary_500(self):
        """TTFB = 500ms (exactly) should score 3, not 4."""
        analysis = {
            "meta_tags": {}, "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "redirect_count": 0,
            "ttfb_ms": 500,
        }
        result = _calculate_seo_score_v2(analysis)
        assert result["breakdown"]["technical_seo"]["details"]["ttfb"] == 3

    def test_redirect_chain_scores(self):
        """0 redirects=3, 1=2, 2=1, 3+=0."""
        base = {
            "meta_tags": {}, "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0,
        }
        for count, expected in [(0, 3), (1, 2), (2, 1), (3, 0), (5, 0)]:
            data = {**base, "redirect_count": count}
            result = _calculate_seo_score_v2(data)
            actual = result["breakdown"]["technical_seo"]["details"]["redirects"]
            assert actual == expected, f"redirect_count={count}: expected {expected}, got {actual}"

    def test_technical_seo_capped_at_25(self, perfect_seo_analysis):
        """Technical SEO score cannot exceed 25."""
        result = _calculate_seo_score_v2(perfect_seo_analysis)
        assert result["breakdown"]["technical_seo"]["score"] <= 25


# ============================================================================
# Category 2: On-Page SEO (25 max)
# ============================================================================

class TestOnPageSEO:
    """Tests for title, meta description, H1, headings, images, URL."""

    def test_title_optimal_length(self):
        """Title 30-60 chars = 5 points."""
        analysis = {
            "meta_tags": {"title": "Best Agency", "title_length": 35},
            "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
        }
        result = _calculate_seo_score_v2(analysis)
        assert result["breakdown"]["on_page_seo"]["details"]["title"] == 5

    def test_title_too_short(self):
        """Title exists but < 30 chars = 2 points."""
        analysis = {
            "meta_tags": {"title": "Hi", "title_length": 2},
            "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
        }
        result = _calculate_seo_score_v2(analysis)
        assert result["breakdown"]["on_page_seo"]["details"]["title"] == 2

    def test_single_h1_full_score(self):
        """Exactly 1 H1 = 5 points."""
        analysis = {
            "meta_tags": {}, "headings": {"h1_count": 1},
            "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
        }
        result = _calculate_seo_score_v2(analysis)
        assert result["breakdown"]["on_page_seo"]["details"]["h1"] == 5

    def test_multiple_h1_reduced(self):
        """Multiple H1s = only 2 points."""
        analysis = {
            "meta_tags": {}, "headings": {"h1_count": 3},
            "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
        }
        result = _calculate_seo_score_v2(analysis)
        assert result["breakdown"]["on_page_seo"]["details"]["h1"] == 2

    def test_image_alt_ratio(self):
        """Half images with alt = 2 points (round(0.5 * 4))."""
        analysis = {
            "meta_tags": {}, "headings": {},
            "images": {"total_images": 10, "images_with_alt": 5, "images_without_alt": 5},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
        }
        result = _calculate_seo_score_v2(analysis)
        assert result["breakdown"]["on_page_seo"]["details"]["image_alt"] == 2

    def test_no_images_neutral_score(self):
        """No images = neutral 2 points (not penalized)."""
        analysis = {
            "meta_tags": {}, "headings": {},
            "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
        }
        result = _calculate_seo_score_v2(analysis)
        assert result["breakdown"]["on_page_seo"]["details"]["image_alt"] == 2


# ============================================================================
# Category 3: Content Quality (20 max)
# ============================================================================

class TestContentQuality:
    """Tests for word count, readability, keywords, stuffing."""

    def test_high_word_count(self):
        """1000+ words = 5 points."""
        analysis = {
            "meta_tags": {}, "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
            "content_quality": {"word_count": 1500, "readability_score": 0},
        }
        result = _calculate_seo_score_v2(analysis)
        assert result["breakdown"]["content_quality"]["details"]["word_count"] == 5

    def test_low_word_count(self):
        """< 100 words = 0 points."""
        analysis = {
            "meta_tags": {}, "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
            "content_quality": {"word_count": 50, "readability_score": 0},
        }
        result = _calculate_seo_score_v2(analysis)
        assert result["breakdown"]["content_quality"]["details"]["word_count"] == 0

    def test_readability_good_range(self):
        """Readability 5-12 = 3 points (ideal range)."""
        analysis = {
            "meta_tags": {}, "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
            "content_quality": {"word_count": 0, "readability_score": 8.5},
        }
        result = _calculate_seo_score_v2(analysis)
        assert result["breakdown"]["content_quality"]["details"]["readability"] == 3

    def test_keyword_stuffing_penalty(self):
        """Keyword stuffing = 0 points for no_stuffing field."""
        analysis = {
            "meta_tags": {}, "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
            "content_quality": {"word_count": 0, "readability_score": 0, "keyword_stuffing": True},
        }
        result = _calculate_seo_score_v2(analysis)
        assert result["breakdown"]["content_quality"]["details"]["no_stuffing"] == 0

    def test_no_stuffing_rewarded(self):
        """No keyword stuffing = 4 points."""
        analysis = {
            "meta_tags": {}, "headings": {}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {}, "robots_txt": {}, "sitemap": {}, "ssl_security": {},
            "mobile_analysis": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
            "content_quality": {"word_count": 0, "readability_score": 0, "keyword_stuffing": False},
        }
        result = _calculate_seo_score_v2(analysis)
        assert result["breakdown"]["content_quality"]["details"]["no_stuffing"] == 4


# ============================================================================
# Penalties
# ============================================================================

class TestPenalties:
    """Tests for penalty deductions."""

    def test_missing_title_penalty(self):
        """Missing title = -15 penalty."""
        analysis = {
            "meta_tags": {},  # no title
            "headings": {"h1_count": 1}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {"is_https": True}, "robots_txt": {},
            "sitemap": {"has_sitemap": True}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
        }
        result = _calculate_seo_score_v2(analysis)
        penalty_reasons = [p["reason"] for p in result["penalties"]]
        assert "Missing title tag" in penalty_reasons

    def test_missing_h1_penalty(self):
        """Missing H1 = -10 penalty."""
        analysis = {
            "meta_tags": {"title": "Test"},
            "headings": {"h1_count": 0}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {"is_https": True}, "robots_txt": {},
            "sitemap": {"has_sitemap": True}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
        }
        result = _calculate_seo_score_v2(analysis)
        penalty_reasons = [p["reason"] for p in result["penalties"]]
        assert "Missing H1 heading" in penalty_reasons

    def test_no_https_penalty(self):
        """Not HTTPS = -10 penalty."""
        analysis = {
            "meta_tags": {"title": "Test"},
            "headings": {"h1_count": 1}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {"is_https": False}, "robots_txt": {},
            "sitemap": {"has_sitemap": True}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
        }
        result = _calculate_seo_score_v2(analysis)
        penalty_reasons = [p["reason"] for p in result["penalties"]]
        assert "Not using HTTPS" in penalty_reasons

    def test_multiple_h1_penalty(self):
        """Multiple H1 tags = -5 penalty."""
        analysis = {
            "meta_tags": {"title": "Test"},
            "headings": {"h1_count": 3}, "images": {"total_images": 0},
            "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
            "schema_markup": {"has_schema": False, "schema_types": []},
            "url_analysis": {"is_https": True}, "robots_txt": {},
            "sitemap": {"has_sitemap": True}, "ssl_security": {},
            "mobile_analysis": {}, "content_quality": {}, "response_headers": {},
            "ttfb_ms": 0, "redirect_count": 0,
        }
        result = _calculate_seo_score_v2(analysis)
        penalty_reasons = [p["reason"] for p in result["penalties"]]
        assert "Multiple H1 tags" in penalty_reasons

    def test_score_never_negative(self, empty_seo_analysis):
        """Even with all penalties, score should not go below 0."""
        result = _calculate_seo_score_v2(empty_seo_analysis)
        assert result["total_score"] >= 0

    def test_score_never_above_100(self, perfect_seo_analysis):
        """Even with all bonuses, score should not exceed 100."""
        result = _calculate_seo_score_v2(perfect_seo_analysis)
        assert result["total_score"] <= 100


# ============================================================================
# Integration / Full Score Tests
# ============================================================================

class TestFullScore:
    """End-to-end tests for complete scoring scenarios."""

    def test_perfect_site_scores_high(self, perfect_seo_analysis):
        """A well-optimized site should score 85+."""
        result = _calculate_seo_score_v2(perfect_seo_analysis)
        assert result["total_score"] >= 85
        assert result["penalty_total"] == 0
        assert len(result["penalties"]) == 0

    def test_empty_site_scores_low(self, empty_seo_analysis):
        """An empty/minimal site should score very low."""
        result = _calculate_seo_score_v2(empty_seo_analysis)
        assert result["total_score"] < 20

    def test_result_structure(self, perfect_seo_analysis):
        """Result should contain all expected keys."""
        result = _calculate_seo_score_v2(perfect_seo_analysis)
        assert "total_score" in result
        assert "raw_score" in result
        assert "penalty_total" in result
        assert "breakdown" in result
        assert "penalties" in result

        expected_categories = [
            "technical_seo", "on_page_seo", "content_quality",
            "mobile_performance", "schema_structured_data", "authority_signals",
        ]
        for cat in expected_categories:
            assert cat in result["breakdown"], f"Missing category: {cat}"
            assert "score" in result["breakdown"][cat]
            assert "max" in result["breakdown"][cat]

    def test_category_max_values(self, perfect_seo_analysis):
        """Each category max should match the defined limits."""
        result = _calculate_seo_score_v2(perfect_seo_analysis)
        b = result["breakdown"]
        assert b["technical_seo"]["max"] == 25
        assert b["on_page_seo"]["max"] == 25
        assert b["content_quality"]["max"] == 20
        assert b["mobile_performance"]["max"] == 15
        assert b["schema_structured_data"]["max"] == 10
        assert b["authority_signals"]["max"] == 5

    def test_raw_score_equals_sum_of_categories(self, perfect_seo_analysis):
        """raw_score should equal sum of all category scores."""
        result = _calculate_seo_score_v2(perfect_seo_analysis)
        b = result["breakdown"]
        category_sum = sum(b[cat]["score"] for cat in b)
        assert result["raw_score"] == category_sum

    def test_total_score_equals_raw_plus_penalties(self, perfect_seo_analysis):
        """total_score = max(0, min(100, raw_score + penalty_total))."""
        result = _calculate_seo_score_v2(perfect_seo_analysis)
        expected = max(0, min(100, result["raw_score"] + result["penalty_total"]))
        assert result["total_score"] == expected

    def test_typical_small_business_site(self):
        """A real-world small business site should score 50-65.

        Scenario: Istanbul'da bir kafe. Title var ama uzun, tek H1,
        birkaç görsel (bazıları alt text'siz), robots.txt yok, sitemap yok,
        SSL geçerli, TTFB ortalama, schema sadece Organization, viewport var
        ama touch icon yok.
        """
        analysis = {
            "meta_tags": {
                "title": "Cafe Moda Istanbul - En iyi kahve deneyimi icin bizi ziyaret edin, taze kavurma kahveler",
                "title_length": 82,  # too long (ideal: 30-60)
                "description": "Istanbul Kadikoy'de ozel kahve deneyimi",
                "description_length": 42,  # too short (ideal: 120-160)
                "canonical": None,
                "og_title": "Cafe Moda Istanbul",
                "og_description": None,
            },
            "headings": {
                "h1": ["Cafe Moda"],
                "h1_count": 1,
                "h2": ["Menumuz", "Hakkimizda"],
                "h3": None,
            },
            "images": {
                "total_images": 8,
                "images_with_alt": 3,
                "images_without_alt": 5,
            },
            "links": {
                "external_links": 1,
                "internal_links": 5,
                "external_link_domains": ["instagram.com"],
            },
            "schema_markup": {
                "has_schema": True,
                "schema_types": ["Organization"],
            },
            "url_analysis": {
                "is_https": True,
                "is_seo_friendly": True,
                "has_keywords": False,
            },
            "robots_txt": {"has_robots_txt": False},
            "sitemap": {"has_sitemap": False},
            "ssl_security": {"ssl_valid": True, "cert_expiry_days": 200},
            "mobile_analysis": {
                "has_viewport": True,
                "has_responsive_meta": True,
                "has_media_queries": False,
                "touch_icon": False,
            },
            "content_quality": {
                "word_count": 450,
                "readability_score": 7.0,
                "keyword_in_title": True,
                "keyword_in_h1": False,
                "keyword_in_first_paragraph": False,
                "keyword_stuffing": False,
            },
            "response_headers": {},
            "ttfb_ms": 950,
            "mobile_ttfb_ms": 1400,
            "redirect_count": 1,
        }
        result = _calculate_seo_score_v2(analysis)
        assert 45 <= result["total_score"] <= 65, (
            f"Typical small business site scored {result['total_score']}, "
            f"expected 45-65"
        )
