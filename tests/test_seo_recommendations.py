"""Tests for _generate_seo_recommendations in web_tools.py.

Tests that SEO score breakdowns produce user-friendly Turkish recommendations.
Each recommendation has: category, priority (high/medium/low), action, reason.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tools.web_tools import _generate_seo_recommendations


# ============================================================================
# Helpers
# ============================================================================

def _make_breakdown(**overrides):
    """Build a full breakdown dict with defaults (all scores = max)."""
    base = {
        "technical_seo": {
            "score": 25, "max": 25,
            "details": {
                "robots_txt": 5, "sitemap": 5, "ssl_security": 5,
                "redirects": 3, "ttfb": 4, "canonical": 3,
            },
        },
        "on_page_seo": {
            "score": 25, "max": 25,
            "details": {
                "title": 5, "meta_description": 5, "h1": 5,
                "heading_hierarchy": 3, "image_alt": 4, "url_structure": 3,
            },
        },
        "content_quality": {
            "score": 20, "max": 20,
            "details": {
                "word_count": 5, "readability": 3, "keyword_in_title": 3,
                "keyword_in_h1": 3, "keyword_in_first_para": 2, "no_stuffing": 4,
            },
        },
        "mobile_performance": {
            "score": 15, "max": 15,
            "details": {
                "viewport": 5, "responsive": 3, "touch_icon": 3, "mobile_ttfb": 4,
            },
        },
        "schema_structured_data": {
            "score": 10, "max": 10,
            "details": {"json_ld": 5, "schema_types": 3, "og_tags": 2},
        },
        "authority_signals": {
            "score": 5, "max": 5,
            "details": {"external_links": 2, "internal_links": 2, "social_links": 1},
        },
    }
    # Apply overrides: e.g. technical_seo={"details": {"robots_txt": 0}}
    for key, val in overrides.items():
        if key in base and isinstance(val, dict):
            if "details" in val:
                base[key]["details"].update(val["details"])
            if "score" in val:
                base[key]["score"] = val["score"]
        else:
            base[key] = val
    return base


# ============================================================================
# Recommendation Format Tests
# ============================================================================

class TestRecommendationFormat:
    """Verify that each recommendation has the required fields."""

    def test_recommendation_is_list(self):
        """Return value should be a list."""
        breakdown = _make_breakdown(
            technical_seo={"score": 0, "details": {"robots_txt": 0, "sitemap": 0,
                           "ssl_security": 0, "redirects": 0, "ttfb": 0, "canonical": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        assert isinstance(result, list)

    def test_each_recommendation_has_required_keys(self):
        """Each item must have category, priority, action, reason."""
        breakdown = _make_breakdown(
            technical_seo={"score": 0, "details": {"robots_txt": 0, "sitemap": 0,
                           "ssl_security": 0, "redirects": 0, "ttfb": 0, "canonical": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        assert len(result) > 0, "Should produce at least one recommendation"
        for rec in result:
            assert "category" in rec, f"Missing 'category' in {rec}"
            assert "priority" in rec, f"Missing 'priority' in {rec}"
            assert "action" in rec, f"Missing 'action' in {rec}"
            assert "reason" in rec, f"Missing 'reason' in {rec}"

    def test_priority_values_are_valid(self):
        """Priority must be one of: high, medium, low."""
        breakdown = _make_breakdown(
            technical_seo={"score": 0, "details": {"robots_txt": 0, "sitemap": 0,
                           "ssl_security": 0, "redirects": 0, "ttfb": 0, "canonical": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        valid_priorities = {"high", "medium", "low"}
        for rec in result:
            assert rec["priority"] in valid_priorities, \
                f"Invalid priority '{rec['priority']}' in {rec}"

    def test_no_recommendations_for_perfect_scores(self):
        """A perfect breakdown should produce no recommendations."""
        breakdown = _make_breakdown()  # all max scores
        result = _generate_seo_recommendations(breakdown, [])
        assert result == [], f"Expected empty list for perfect scores, got {len(result)} recs"


# ============================================================================
# Technical SEO Recommendations
# ============================================================================

class TestTechnicalSEORecommendations:
    """Tests for Technical SEO category recommendations."""

    def test_missing_robots_txt(self):
        """robots_txt == 0 should produce a recommendation."""
        breakdown = _make_breakdown(
            technical_seo={"details": {"robots_txt": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        robots_recs = [r for r in result if "robots" in r["action"].lower()]
        assert len(robots_recs) >= 1, "Should recommend adding robots.txt"

    def test_missing_sitemap(self):
        """sitemap == 0 should produce a recommendation."""
        breakdown = _make_breakdown(
            technical_seo={"details": {"sitemap": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        sitemap_recs = [r for r in result if "site harita" in r["action"].lower()
                        or "sitemap" in r["action"].lower()]
        assert len(sitemap_recs) >= 1, "Should recommend creating a sitemap"

    def test_low_ssl(self):
        """Low ssl_security should produce HTTPS recommendation."""
        breakdown = _make_breakdown(
            technical_seo={"details": {"ssl_security": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        ssl_recs = [r for r in result if "https" in r["action"].lower()
                    or "ssl" in r["action"].lower()
                    or "güvenli" in r["action"].lower()]
        assert len(ssl_recs) >= 1, "Should recommend HTTPS/SSL"

    def test_slow_ttfb(self):
        """Low TTFB score should recommend speed improvement."""
        breakdown = _make_breakdown(
            technical_seo={"details": {"ttfb": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        speed_recs = [r for r in result if "hız" in r["action"].lower()
                      or "yavaş" in r["reason"].lower()
                      or "açılış" in r["action"].lower()]
        assert len(speed_recs) >= 1, "Should recommend improving site speed"

    def test_missing_canonical(self):
        """canonical == 0 should produce a recommendation."""
        breakdown = _make_breakdown(
            technical_seo={"details": {"canonical": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        canonical_recs = [r for r in result if "adres" in r["action"].lower()
                          or "canonical" in r["action"].lower()
                          or "orijinal" in r["action"].lower()]
        assert len(canonical_recs) >= 1, "Should recommend canonical tags"

    def test_good_technical_no_recs(self):
        """High technical scores should not produce technical recommendations."""
        breakdown = _make_breakdown()  # all max
        result = _generate_seo_recommendations(breakdown, [])
        tech_recs = [r for r in result if r["category"] == "Teknik Altyapı"]
        assert len(tech_recs) == 0, "Perfect technical scores should produce no recs"


# ============================================================================
# On-Page SEO Recommendations
# ============================================================================

class TestOnPageSEORecommendations:
    """Tests for On-Page SEO category recommendations."""

    def test_missing_title(self):
        """title == 0 should recommend writing a title."""
        breakdown = _make_breakdown(
            on_page_seo={"details": {"title": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        title_recs = [r for r in result if "başlığ" in r["action"].lower()
                      or "başlık" in r["action"].lower()
                      or "title" in r["action"].lower()]
        assert len(title_recs) >= 1, "Should recommend writing a page title"

    def test_missing_meta_description(self):
        """meta_description == 0 should recommend writing a description."""
        breakdown = _make_breakdown(
            on_page_seo={"details": {"meta_description": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        desc_recs = [r for r in result if "açıklama" in r["action"].lower()
                     or "description" in r["action"].lower()]
        assert len(desc_recs) >= 1, "Should recommend writing a meta description"

    def test_missing_h1(self):
        """h1 == 0 should recommend adding an H1."""
        breakdown = _make_breakdown(
            on_page_seo={"details": {"h1": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        h1_recs = [r for r in result if "başlık" in r["action"].lower()
                   or "h1" in r["action"].lower()]
        assert len(h1_recs) >= 1, "Should recommend adding an H1 heading"

    def test_low_image_alt(self):
        """image_alt <= 1 should recommend adding alt text."""
        breakdown = _make_breakdown(
            on_page_seo={"details": {"image_alt": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        img_recs = [r for r in result if "resim" in r["action"].lower()
                    or "görsel" in r["action"].lower()
                    or "alt" in r["action"].lower()]
        assert len(img_recs) >= 1, "Should recommend adding image alt texts"


# ============================================================================
# Content Quality Recommendations
# ============================================================================

class TestContentQualityRecommendations:
    """Tests for Content Quality category recommendations."""

    def test_low_word_count(self):
        """word_count <= 1 should recommend more content."""
        breakdown = _make_breakdown(
            content_quality={"details": {"word_count": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        wc_recs = [r for r in result if "içerik" in r["action"].lower()
                   or "kelime" in r["action"].lower()
                   or "yazı" in r["action"].lower()]
        assert len(wc_recs) >= 1, "Should recommend adding more content"

    def test_keyword_stuffing(self):
        """no_stuffing == 0 means keyword stuffing detected."""
        breakdown = _make_breakdown(
            content_quality={"details": {"no_stuffing": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        stuff_recs = [r for r in result if "anahtar kelime" in r["action"].lower()
                      or "tekrar" in r["action"].lower()
                      or "doğal" in r["action"].lower()]
        assert len(stuff_recs) >= 1, "Should warn about keyword stuffing"


# ============================================================================
# Mobile & Performance Recommendations
# ============================================================================

class TestMobileRecommendations:
    """Tests for Mobile & Performance category recommendations."""

    def test_missing_viewport(self):
        """viewport == 0 should recommend mobile optimization."""
        breakdown = _make_breakdown(
            mobile_performance={"details": {"viewport": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        mobile_recs = [r for r in result if "mobil" in r["action"].lower()
                       or "telefon" in r["action"].lower()]
        assert len(mobile_recs) >= 1, "Should recommend mobile optimization"

    def test_missing_touch_icon(self):
        """touch_icon == 0 should recommend adding an icon."""
        breakdown = _make_breakdown(
            mobile_performance={"details": {"touch_icon": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        icon_recs = [r for r in result if "ikon" in r["action"].lower()
                     or "icon" in r["action"].lower()]
        assert len(icon_recs) >= 1, "Should recommend adding a touch icon"


# ============================================================================
# Schema & Structured Data Recommendations
# ============================================================================

class TestSchemaRecommendations:
    """Tests for Schema & Structured Data category recommendations."""

    def test_missing_json_ld(self):
        """json_ld == 0 should recommend structured data."""
        breakdown = _make_breakdown(
            schema_structured_data={"details": {"json_ld": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        schema_recs = [r for r in result if "işletme" in r["action"].lower()
                       or "google" in r["action"].lower()
                       or "bilgi" in r["action"].lower()
                       or "tanıt" in r["action"].lower()]
        assert len(schema_recs) >= 1, "Should recommend adding structured data"

    def test_missing_og_tags(self):
        """og_tags == 0 should recommend social sharing tags."""
        breakdown = _make_breakdown(
            schema_structured_data={"details": {"og_tags": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        og_recs = [r for r in result if "sosyal" in r["action"].lower()
                   or "paylaşım" in r["action"].lower()
                   or "önizleme" in r["action"].lower()]
        assert len(og_recs) >= 1, "Should recommend adding OG tags"


# ============================================================================
# Authority Signals Recommendations
# ============================================================================

class TestAuthorityRecommendations:
    """Tests for Authority Signals category recommendations."""

    def test_no_external_links(self):
        """external_links == 0 should recommend linking out."""
        breakdown = _make_breakdown(
            authority_signals={"details": {"external_links": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        ext_recs = [r for r in result if "kaynak" in r["action"].lower()
                    or "link" in r["action"].lower()
                    or "referans" in r["action"].lower()]
        assert len(ext_recs) >= 1, "Should recommend adding external links"

    def test_no_internal_links(self):
        """internal_links == 0 should recommend internal linking."""
        breakdown = _make_breakdown(
            authority_signals={"details": {"internal_links": 0}},
        )
        result = _generate_seo_recommendations(breakdown, [])
        int_recs = [r for r in result if "bağlantı" in r["action"].lower()
                    or "link" in r["action"].lower()
                    or "sayfalar" in r["action"].lower()]
        assert len(int_recs) >= 1, "Should recommend internal linking"


# ============================================================================
# Penalty Recommendations
# ============================================================================

class TestPenaltyRecommendations:
    """Tests that penalties produce recommendations."""

    def test_missing_title_penalty(self):
        """Missing title penalty should produce a high-priority recommendation."""
        penalties = [{"reason": "Missing title tag", "points": -15}]
        breakdown = _make_breakdown()
        result = _generate_seo_recommendations(breakdown, penalties)
        penalty_recs = [r for r in result if r["priority"] == "high"]
        assert len(penalty_recs) >= 1, "Missing title penalty should create high-priority rec"

    def test_no_https_penalty(self):
        """Not using HTTPS penalty should produce a recommendation."""
        penalties = [{"reason": "Not using HTTPS", "points": -10}]
        breakdown = _make_breakdown()
        result = _generate_seo_recommendations(breakdown, penalties)
        assert len(result) >= 1, "HTTPS penalty should create a recommendation"

    def test_multiple_h1_penalty(self):
        """Multiple H1 tags penalty should produce a recommendation."""
        penalties = [{"reason": "Multiple H1 tags", "points": -5}]
        breakdown = _make_breakdown()
        result = _generate_seo_recommendations(breakdown, penalties)
        h1_recs = [r for r in result if "başlık" in r["action"].lower()
                   or "h1" in r["action"].lower()]
        assert len(h1_recs) >= 1, "Multiple H1 penalty should create a rec"

    def test_keyword_stuffing_penalty(self):
        """Keyword stuffing penalty should produce a high-priority rec."""
        penalties = [{"reason": "Keyword stuffing detected", "points": -5}]
        breakdown = _make_breakdown()
        result = _generate_seo_recommendations(breakdown, penalties)
        assert len(result) >= 1, "Keyword stuffing penalty should create a rec"

    def test_no_sitemap_penalty(self):
        """No sitemap penalty should produce a recommendation."""
        penalties = [{"reason": "No sitemap.xml found", "points": -3}]
        breakdown = _make_breakdown()
        result = _generate_seo_recommendations(breakdown, penalties)
        assert len(result) >= 1, "No sitemap penalty should create a rec"


# ============================================================================
# Integrated / Realistic Scenario Tests
# ============================================================================

class TestRealisticScenarios:
    """Test with realistic score combinations."""

    def test_typical_small_business_site(self):
        """A typical small business site (score ~50-65) should get 5-15 recs."""
        breakdown = _make_breakdown(
            technical_seo={"score": 10, "details": {
                "robots_txt": 0, "sitemap": 0, "ssl_security": 3,
                "redirects": 3, "ttfb": 2, "canonical": 0,
            }},
            on_page_seo={"score": 12, "details": {
                "title": 2, "meta_description": 0, "h1": 5,
                "heading_hierarchy": 2, "image_alt": 1, "url_structure": 2,
            }},
            content_quality={"score": 8, "details": {
                "word_count": 1, "readability": 0, "keyword_in_title": 3,
                "keyword_in_h1": 0, "keyword_in_first_para": 0, "no_stuffing": 4,
            }},
            mobile_performance={"score": 5, "details": {
                "viewport": 5, "responsive": 0, "touch_icon": 0, "mobile_ttfb": 0,
            }},
            schema_structured_data={"score": 0, "details": {
                "json_ld": 0, "schema_types": 0, "og_tags": 0,
            }},
            authority_signals={"score": 1, "details": {
                "external_links": 1, "internal_links": 0, "social_links": 0,
            }},
        )
        penalties = [
            {"reason": "No sitemap.xml found", "points": -3},
        ]
        result = _generate_seo_recommendations(breakdown, penalties)
        assert 5 <= len(result) <= 20, \
            f"Typical small business should get 5-20 recs, got {len(result)}"

        # Should have at least some high priority items
        high_priority = [r for r in result if r["priority"] == "high"]
        assert len(high_priority) >= 1, "Should have at least 1 high priority rec"

    def test_well_optimized_site_few_recs(self):
        """A well-optimized site should have very few or no recommendations."""
        breakdown = _make_breakdown(
            technical_seo={"score": 23, "details": {
                "robots_txt": 5, "sitemap": 5, "ssl_security": 4,
                "redirects": 3, "ttfb": 3, "canonical": 3,
            }},
            on_page_seo={"score": 23, "details": {
                "title": 5, "meta_description": 5, "h1": 5,
                "heading_hierarchy": 3, "image_alt": 3, "url_structure": 2,
            }},
            content_quality={"score": 18, "details": {
                "word_count": 5, "readability": 3, "keyword_in_title": 3,
                "keyword_in_h1": 3, "keyword_in_first_para": 2, "no_stuffing": 4,
            }},
            mobile_performance={"score": 14, "details": {
                "viewport": 5, "responsive": 3, "touch_icon": 3, "mobile_ttfb": 3,
            }},
            schema_structured_data={"score": 9, "details": {
                "json_ld": 5, "schema_types": 2, "og_tags": 2,
            }},
            authority_signals={"score": 5, "details": {
                "external_links": 2, "internal_links": 2, "social_links": 1,
            }},
        )
        result = _generate_seo_recommendations(breakdown, [])
        assert len(result) <= 3, \
            f"Well-optimized site should have <=3 recs, got {len(result)}"
