"""Shared test fixtures for agents-sdk tests."""

import pytest
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# SEO Score v2 Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def perfect_seo_analysis():
    """A site that scores maximum on every SEO category."""
    return {
        "meta_tags": {
            "title": "Best Digital Agency Istanbul",
            "title_length": 35,
            "description": "We are the leading digital agency in Istanbul providing web design, SEO, and marketing services for businesses of all sizes.",
            "description_length": 135,
            "canonical": "https://example.com/",
            "og_title": "Best Digital Agency Istanbul",
            "og_description": "Leading digital agency in Istanbul",
        },
        "headings": {
            "h1": ["Best Digital Agency"],
            "h1_count": 1,
            "h2": ["Services", "About Us", "Contact"],
            "h3": ["Web Design", "SEO", "Marketing"],
        },
        "images": {
            "total_images": 10,
            "images_with_alt": 10,
            "images_without_alt": 0,
        },
        "links": {
            "external_links": 5,
            "internal_links": 15,
            "external_link_domains": ["instagram.com", "twitter.com", "reference.com"],
        },
        "schema_markup": {
            "has_schema": True,
            "schema_types": ["Organization", "LocalBusiness", "FAQPage"],
        },
        "url_analysis": {
            "is_https": True,
            "is_seo_friendly": True,
            "has_keywords": True,
        },
        "robots_txt": {
            "has_robots_txt": True,
            "allows_crawling": True,
        },
        "sitemap": {
            "has_sitemap": True,
            "url_count": 50,
            "has_lastmod": True,
        },
        "ssl_security": {
            "ssl_valid": True,
            "cert_expiry_days": 300,
        },
        "mobile_analysis": {
            "has_viewport": True,
            "has_responsive_meta": True,
            "has_media_queries": True,
            "touch_icon": True,
        },
        "content_quality": {
            "word_count": 1200,
            "readability_score": 8.5,
            "keyword_in_title": True,
            "keyword_in_h1": True,
            "keyword_in_first_paragraph": True,
            "keyword_stuffing": False,
        },
        "response_headers": {
            "strict-transport-security": "max-age=31536000",
            "x-frame-options": "DENY",
            "content-security-policy": "default-src 'self'",
            "x-content-type-options": "nosniff",
        },
        "ttfb_ms": 200,
        "mobile_ttfb_ms": 300,
        "redirect_count": 0,
    }


@pytest.fixture
def empty_seo_analysis():
    """A minimal/empty site that scores poorly on everything."""
    return {
        "meta_tags": {},
        "headings": {},
        "images": {"total_images": 0},
        "links": {"external_links": 0, "internal_links": 0, "external_link_domains": []},
        "schema_markup": {"has_schema": False, "schema_types": []},
        "url_analysis": {"is_https": False},
        "robots_txt": {"has_robots_txt": False},
        "sitemap": {"has_sitemap": False},
        "ssl_security": {},
        "mobile_analysis": {},
        "content_quality": {"word_count": 0},
        "response_headers": {},
        "ttfb_ms": 0,
        "redirect_count": 0,
    }


# ---------------------------------------------------------------------------
# GEO Readiness Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def make_soup():
    """Factory fixture: pass HTML string, get BeautifulSoup object."""
    def _make(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")
    return _make


@pytest.fixture
def geo_perfect_html():
    """HTML optimized for GEO readiness."""
    return """
    <html>
    <head><title>Test</title></head>
    <body>
        <h1>Digital Agency Services</h1>
        <h2>What is SEO?</h2>
        <p>SEO is search engine optimization. In 2025, 68% of online experiences begin with a search engine.</p>
        <h2>How does SEO work?</h2>
        <p>According to recent studies, websites with proper SEO see a $3,500 increase in monthly revenue.</p>
        <h3>Why choose us?</h3>
        <table><tr><td>Service</td><td>Price</td></tr><tr><td>SEO</td><td>₺5000</td></tr></table>
        <ul><li>Web Design</li><li>SEO</li></ul>
        <ul><li>Marketing</li><li>Analytics</li></ul>
        <ol><li>Step 1</li><li>Step 2</li></ol>
        <details><summary>FAQ</summary><p>Answer here</p></details>
        <time datetime="2026-01-15">January 15, 2026</time>
    </body>
    </html>
    """


@pytest.fixture
def geo_empty_html():
    """Minimal HTML with no GEO optimization."""
    return "<html><body><p>Hello world</p></body></html>"
