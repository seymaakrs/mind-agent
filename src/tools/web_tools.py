"""
Web tools for web search and website scraping.

Tools:
- web_search: Search the web using Google (via Serper.dev API)
- scrape_website: Scrape a website for business analysis
- scrape_for_seo: Detailed SEO analysis of a single website
- scrape_competitors: Batch scraping of multiple competitor websites
- check_serp_position: Check real Google search visibility for keywords
"""
from __future__ import annotations

import asyncio
import json
import re
import ssl
import socket
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from agents import function_tool

from src.app.config import get_settings


# ---------------------------------------------------------------------------
# Phase 1: Enhanced page fetcher + Flesch-Kincaid readability
# ---------------------------------------------------------------------------

_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

# AI search engine bots to check in robots.txt for GEO analysis
_AI_BOTS = [
    "GPTBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot",
    "PerplexityBot", "Perplexity-User", "Google-Extended",
    "Applebot-Extended", "YouBot",
]


async def _fetch_page_enhanced(url: str, *, mobile: bool = False) -> dict[str, Any]:
    """Fetch a page capturing TTFB, redirect chain, and response headers.

    Returns a dict with:
      html, final_url, status_code, ttfb_ms, redirect_chain,
      redirect_count, response_headers, success, error
    """
    ua = _MOBILE_UA if mobile else _DESKTOP_UA
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            t0 = time.monotonic()
            response = await client.get(
                url,
                follow_redirects=True,
                headers={
                    "User-Agent": ua,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                },
            )
            ttfb_ms = round((time.monotonic() - t0) * 1000)

            redirect_chain = [str(r.url) for r in response.history]

            # Grab a few useful headers
            headers_of_interest = {}
            for h in (
                "server", "x-powered-by", "content-encoding",
                "cache-control", "strict-transport-security",
                "x-frame-options", "x-content-type-options",
                "content-security-policy", "referrer-policy",
                "permissions-policy",
            ):
                val = response.headers.get(h)
                if val:
                    headers_of_interest[h] = val

            return {
                "html": response.text if response.status_code == 200 else None,
                "final_url": str(response.url),
                "status_code": response.status_code,
                "ttfb_ms": ttfb_ms,
                "redirect_chain": redirect_chain,
                "redirect_count": len(redirect_chain),
                "response_headers": headers_of_interest,
                "success": response.status_code == 200,
                "error": None if response.status_code == 200 else f"HTTP {response.status_code}",
            }
    except httpx.TimeoutException:
        return {
            "html": None, "final_url": url, "status_code": 0,
            "ttfb_ms": 0, "redirect_chain": [], "redirect_count": 0,
            "response_headers": {}, "success": False,
            "error": "Request timeout",
        }
    except Exception as exc:
        return {
            "html": None, "final_url": url, "status_code": 0,
            "ttfb_ms": 0, "redirect_chain": [], "redirect_count": 0,
            "response_headers": {}, "success": False,
            "error": str(exc),
        }


def _count_syllables(word: str) -> int:
    """Approximate syllable count for English/Turkish text (heuristic)."""
    word = word.lower().strip()
    if not word:
        return 0
    vowels = set("aeıioöuüâîûAEIOU")
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    return max(count, 1)


def _flesch_kincaid_score(text: str) -> float:
    """Calculate Flesch-Kincaid readability grade level (pure Python).

    Lower = easier to read.  Typical web content: 7-10.
    """
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return 0.0

    words = re.findall(r'\b\w+\b', text)
    if not words:
        return 0.0

    total_syllables = sum(_count_syllables(w) for w in words)
    num_words = len(words)
    num_sentences = len(sentences)

    # Flesch-Kincaid Grade Level formula
    grade = 0.39 * (num_words / num_sentences) + 11.8 * (total_syllables / num_words) - 15.59
    return round(max(0, grade), 1)


# ---------------------------------------------------------------------------
# Phase 2: New SEO check functions
# ---------------------------------------------------------------------------

async def _check_robots_txt(url: str) -> dict[str, Any]:
    """Check /robots.txt for crawl permissions and sitemaps."""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    result: dict[str, Any] = {
        "has_robots_txt": False,
        "allows_crawling": True,
        "sitemap_urls": [],
        "blocked_paths": [],
        "issues": [],
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(robots_url, follow_redirects=True,
                                    headers={"User-Agent": _DESKTOP_UA})
        if resp.status_code != 200:
            result["issues"].append("robots.txt not found")
            return result

        result["has_robots_txt"] = True
        body = resp.text

        rp = RobotFileParser()
        rp.parse(body.splitlines())

        if not rp.can_fetch("Googlebot", "/"):
            result["allows_crawling"] = False
            result["issues"].append("Googlebot is blocked from crawling /")

        # Extract sitemap directives
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("sitemap:"):
                sitemap_url = stripped.split(":", 1)[1].strip()
                result["sitemap_urls"].append(sitemap_url)
            # Track disallow for Googlebot / *
            if stripped.lower().startswith("disallow:"):
                path = stripped.split(":", 1)[1].strip()
                if path and path != "/":
                    result["blocked_paths"].append(path)

        if result["blocked_paths"]:
            critical = [p for p in result["blocked_paths"] if p in ("/", "/blog", "/products", "/services")]
            if critical:
                result["issues"].append(f"Important paths blocked: {', '.join(critical)}")

        # GEO: Check AI bot access
        bots_allowed = []
        bots_blocked = []
        bots_not_mentioned = []
        body_lower = body.lower()
        for bot in _AI_BOTS:
            # Check if bot is explicitly mentioned in robots.txt
            if f"user-agent: {bot.lower()}" in body_lower:
                if rp.can_fetch(bot, "/"):
                    bots_allowed.append(bot)
                else:
                    bots_blocked.append(bot)
            else:
                # Not mentioned = default allow (no specific rule)
                bots_not_mentioned.append(bot)

        result["ai_bots_access"] = {
            "bots_allowed": bots_allowed,
            "bots_blocked": bots_blocked,
            "bots_not_mentioned": bots_not_mentioned,
        }

    except Exception:
        result["issues"].append("Could not fetch robots.txt")
    return result


async def _check_llms_txt(url: str) -> dict[str, Any]:
    """Check for /llms.txt file (AI content optimization standard).

    llms.txt is a proposed standard that helps AI models understand site content.
    Its presence signals GEO awareness.
    """
    parsed = urlparse(url)
    llms_url = f"{parsed.scheme}://{parsed.netloc}/llms.txt"
    result: dict[str, Any] = {
        "has_llms_txt": False,
        "sections": [],
        "has_llms_full": False,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(llms_url, follow_redirects=True,
                                    headers={"User-Agent": _DESKTOP_UA})
        if resp.status_code == 200:
            body = resp.text
            result["has_llms_txt"] = True
            # Extract section headers (lines starting with #)
            for line in body.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    result["sections"].append(stripped[:100])
            # Check for llms-full.txt reference
            if "llms-full.txt" in body.lower():
                result["has_llms_full"] = True
    except Exception:
        pass
    return result


async def _check_sitemap(base_url: str, declared_sitemaps: list[str] | None = None) -> dict[str, Any]:
    """Check sitemap.xml availability and basic stats."""
    result: dict[str, Any] = {
        "has_sitemap": False,
        "url_count": 0,
        "has_lastmod": False,
        "is_index": False,
        "issues": [],
    }

    # Try declared sitemaps first, then fall back to /sitemap.xml
    urls_to_try = list(declared_sitemaps or [])
    parsed = urlparse(base_url)
    default_sitemap = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    if default_sitemap not in urls_to_try:
        urls_to_try.append(default_sitemap)

    for sitemap_url in urls_to_try[:3]:  # Try at most 3
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(sitemap_url, follow_redirects=True,
                                        headers={"User-Agent": _DESKTOP_UA})
            if resp.status_code != 200:
                continue

            body = resp.text
            result["has_sitemap"] = True

            # Check if sitemap index
            if "<sitemapindex" in body.lower():
                result["is_index"] = True
                sitemap_count = body.lower().count("<sitemap>")
                result["url_count"] = sitemap_count
            else:
                url_count = body.lower().count("<url>")
                result["url_count"] = url_count if url_count > 0 else body.lower().count("<loc>")

            result["has_lastmod"] = "<lastmod>" in body.lower()
            break  # Found a working sitemap

        except Exception:
            continue

    if not result["has_sitemap"]:
        result["issues"].append("No sitemap.xml found")
    elif result["url_count"] == 0:
        result["issues"].append("Sitemap is empty")
    elif not result["has_lastmod"]:
        result["issues"].append("Sitemap lacks <lastmod> dates")

    return result


async def _check_ssl_security(url: str) -> dict[str, Any]:
    """Check SSL certificate and security headers (via asyncio.to_thread)."""
    result: dict[str, Any] = {
        "ssl_valid": False,
        "cert_expiry_days": None,
        "tls_version": None,
        "security_headers": {},
        "issues": [],
    }

    parsed = urlparse(url)
    hostname = parsed.netloc.split(":")[0]

    def _ssl_check() -> dict[str, Any]:
        inner: dict[str, Any] = {"ssl_valid": False, "cert_expiry_days": None, "tls_version": None}
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((hostname, 443), timeout=5) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    inner["tls_version"] = ssock.version()
                    cert = ssock.getpeercert()
                    if cert:
                        inner["ssl_valid"] = True
                        not_after = cert.get("notAfter", "")
                        if not_after:
                            # Format: 'Sep  9 00:00:00 2025 GMT'
                            from email.utils import parsedate_to_datetime
                            try:
                                expiry = parsedate_to_datetime(not_after)
                                days = (expiry - datetime.now(timezone.utc)).days
                                inner["cert_expiry_days"] = days
                            except Exception:
                                pass
        except Exception:
            pass
        return inner

    try:
        ssl_info = await asyncio.to_thread(_ssl_check)
        result.update(ssl_info)
    except Exception:
        pass

    if not result["ssl_valid"]:
        result["issues"].append("SSL certificate is invalid or missing")
    elif result["cert_expiry_days"] is not None and result["cert_expiry_days"] < 30:
        result["issues"].append(f"SSL certificate expires in {result['cert_expiry_days']} days")

    # Security headers are checked from _fetch_page_enhanced headers
    # They'll be injected by the caller
    return result


def _check_mobile_friendliness(soup: BeautifulSoup, html: str) -> dict[str, Any]:
    """Check mobile-friendliness signals from HTML."""
    result: dict[str, Any] = {
        "has_viewport": False,
        "has_responsive_meta": False,
        "has_media_queries": False,
        "touch_icon": False,
        "score": 0,
        "issues": [],
    }

    # Viewport meta tag
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if viewport:
        content = (viewport.get("content") or "").lower()
        result["has_viewport"] = True
        if "width=device-width" in content:
            result["has_responsive_meta"] = True

    # Media queries in inline styles
    style_tags = soup.find_all("style")
    all_styles = " ".join(tag.string or "" for tag in style_tags)
    if "@media" in all_styles:
        result["has_media_queries"] = True

    # Also check in HTML (some templates inline media queries)
    if "@media" in html and not result["has_media_queries"]:
        result["has_media_queries"] = True

    # Apple touch icon
    touch_icon = soup.find("link", attrs={"rel": lambda v: v and "apple-touch-icon" in str(v).lower()})
    if touch_icon:
        result["touch_icon"] = True

    # Calculate score (0-15 matching the mobile category max)
    score = 0
    if result["has_viewport"]:
        score += 5
    if result["has_responsive_meta"]:
        score += 3
    if result["has_media_queries"]:
        score += 3
    if result["touch_icon"]:
        score += 3
    result["score"] = score

    # Issues
    if not result["has_viewport"]:
        result["issues"].append("Missing viewport meta tag")
    elif not result["has_responsive_meta"]:
        result["issues"].append("Viewport missing width=device-width")
    if not result["has_media_queries"]:
        result["issues"].append("No responsive CSS media queries detected")

    return result


def _analyze_content_quality(
    text: str,
    title: str | None,
    h1s: list[str],
    keyword_density: dict[str, float],
) -> dict[str, Any]:
    """Analyze content quality: depth, readability, keyword placement."""
    result: dict[str, Any] = {
        "word_count": 0,
        "content_depth": "thin",
        "readability_score": 0.0,
        "keyword_in_title": False,
        "keyword_in_h1": False,
        "keyword_in_first_paragraph": False,
        "keyword_stuffing": False,
        "stuffed_keywords": [],
        "issues": [],
    }

    words = text.split()
    result["word_count"] = len(words)

    # Content depth
    wc = len(words)
    if wc < 300:
        result["content_depth"] = "thin"
        result["issues"].append(f"Thin content ({wc} words, recommend 800+)")
    elif wc < 1000:
        result["content_depth"] = "normal"
    else:
        result["content_depth"] = "comprehensive"

    # Readability
    result["readability_score"] = _flesch_kincaid_score(text)

    # Top keyword (highest density)
    if keyword_density:
        top_kw = max(keyword_density, key=keyword_density.get)  # type: ignore[arg-type]
        top_density = keyword_density[top_kw]

        if title and top_kw.lower() in title.lower():
            result["keyword_in_title"] = True
        if h1s and any(top_kw.lower() in h.lower() for h in h1s):
            result["keyword_in_h1"] = True

        # Check first ~200 words
        first_para = " ".join(words[:200]).lower()
        if top_kw.lower() in first_para:
            result["keyword_in_first_paragraph"] = True

        # Keyword stuffing check (>3% density)
        stuffed = [kw for kw, d in keyword_density.items() if d > 3.0]
        if stuffed:
            result["keyword_stuffing"] = True
            result["stuffed_keywords"] = stuffed[:5]
            result["issues"].append(f"Keyword stuffing detected: {', '.join(stuffed[:3])}")

    return result


# ---------------------------------------------------------------------------
# Phase 2b: GEO (Generative Engine Optimization) readiness analysis
# ---------------------------------------------------------------------------

def _analyze_geo_readiness(
    soup: BeautifulSoup,
    main_text: str,
    robots_result: dict[str, Any],
    llms_result: dict[str, Any],
    schema_data: dict[str, Any],
    content_quality: dict[str, Any],
    links: dict[str, Any],
    response_headers: dict[str, Any],
) -> dict[str, Any]:
    """Analyze GEO (Generative Engine Optimization) readiness.

    Evaluates how well a page is optimized for AI-powered search engines
    (ChatGPT, Perplexity, Google AI Overviews).  Uses already-parsed data —
    no additional HTTP requests.

    Scoring: 4 categories, 100 points total.
    """
    word_count = content_quality.get("word_count", len(main_text.split()))

    # ── (i) AI Crawler Access (0-25) ──────────────────────────────────
    ai_access = robots_result.get("ai_bots_access", {})
    bots_allowed = ai_access.get("bots_allowed", [])
    bots_blocked = ai_access.get("bots_blocked", [])
    bots_not_mentioned = ai_access.get("bots_not_mentioned", [])

    if not robots_result.get("has_robots_txt"):
        # No robots.txt = no restrictions = all bots allowed
        ai_crawler_score = 25
        bots_not_mentioned = list(_AI_BOTS)
        bots_allowed = []
        bots_blocked = []
    else:
        # allowed + not_mentioned = effectively accessible
        accessible_count = len(bots_allowed) + len(bots_not_mentioned)
        ai_crawler_score = round(25 * accessible_count / len(_AI_BOTS))

    ai_crawler_detail = {
        "score": ai_crawler_score,
        "max": 25,
        "bots_allowed": bots_allowed,
        "bots_blocked": bots_blocked,
        "bots_not_mentioned": bots_not_mentioned,
    }

    # ── (ii) Content Structure (0-25) ─────────────────────────────────
    cs_score = 0

    # FAQ detection (10p max)
    faq_schema = any(
        t.lower() in ("faqpage", "faq") for t in schema_data.get("schema_types", [])
    )
    has_details_summary = bool(soup.find("details"))
    faq_heading_pattern = re.compile(r'\b(FAQ|SSS|Sıkça\s+Sorulan|Sık\s+Sorulan|Frequently\s+Asked)\b', re.I)
    has_faq_heading = bool(soup.find(re.compile(r'^h[1-6]$'), string=faq_heading_pattern))

    if faq_schema:
        cs_score += 5
    if has_details_summary:
        cs_score += 3
    if has_faq_heading:
        cs_score += 2

    # Tables & lists (8p max)
    tables_count = len(soup.find_all("table"))
    ul_count = len(soup.find_all("ul"))
    ol_count = len(soup.find_all("ol"))

    if tables_count > 0:
        cs_score += 3
    if ul_count >= 2:
        cs_score += 2
    if ol_count > 0:
        cs_score += 3

    # Question headings (7p max)
    question_headings_count = 0
    for tag in soup.find_all(re.compile(r'^h[23]$')):
        text = tag.get_text(strip=True)
        if "?" in text:
            question_headings_count += 1
    cs_score += min(7, question_headings_count * 2)

    cs_score = min(25, cs_score)

    content_structure_detail = {
        "score": cs_score,
        "max": 25,
        "has_faq_section": faq_schema or has_details_summary or has_faq_heading,
        "faq_schema": faq_schema,
        "tables_count": tables_count,
        "lists_count": ul_count + ol_count,
        "question_headings_count": question_headings_count,
    }

    # ── (iii) Citation & Data Density (0-25) ──────────────────────────
    cd_score = 0

    # External citation density (13p)
    ext_links_count = links.get("external_links", 0)
    words_per_1k = word_count / 1000 if word_count > 0 else 1
    citation_density = ext_links_count / words_per_1k if words_per_1k > 0 else 0

    if citation_density >= 3:
        cd_score += 13
    elif citation_density >= 2:
        cd_score += 10
    elif citation_density >= 1:
        cd_score += 7
    elif citation_density >= 0.5:
        cd_score += 4

    # Statistics/numerical data density (12p)
    # Match: percentages, years, currency, units
    stat_pattern = re.compile(
        r'(?:'
        r'\d+[.,]?\d*\s*%'           # percentages
        r'|(?:19|20)\d{2}'           # years
        r'|\$\d+|\€\d+|₺\d+'        # currency
        r'|\d+\s*(?:kg|m²|km|lt|cm)' # units
        r'|\d{1,3}(?:[.,]\d{3})+'    # large numbers (1.000, 2,500)
        r')',
        re.I,
    )
    statistics_count = len(stat_pattern.findall(main_text))
    stats_density = statistics_count / words_per_1k if words_per_1k > 0 else 0

    if stats_density >= 5:
        cd_score += 12
    elif stats_density >= 3:
        cd_score += 9
    elif stats_density >= 1.5:
        cd_score += 6
    elif stats_density >= 0.5:
        cd_score += 3

    cd_score = min(25, cd_score)

    citation_detail = {
        "score": cd_score,
        "max": 25,
        "external_citations": ext_links_count,
        "citation_density_per_1k": round(citation_density, 2),
        "statistics_count": statistics_count,
        "statistics_density_per_1k": round(stats_density, 2),
    }

    # ── (iv) AI Discovery (0-25) ──────────────────────────────────────
    ad_score = 0

    # llms.txt (8p)
    if llms_result.get("has_llms_txt"):
        ad_score += 6
        if llms_result.get("has_llms_full"):
            ad_score += 2

    # GEO-critical schema types (10p)
    geo_schema_types = {"FAQPage", "HowTo", "Organization", "LocalBusiness",
                        "Person", "Article", "Product"}
    present_types = geo_schema_types & set(schema_data.get("schema_types", []))
    missing_types = geo_schema_types - present_types
    ad_score += min(10, len(present_types) * 2)

    # Freshness signals (7p)
    freshness_signals = []
    if soup.find("time"):
        freshness_signals.append("time_element")
        ad_score += 2

    # Check schema for datePublished/dateModified
    has_date_schema = False
    for sd in schema_data.get("schema_data", []):
        if isinstance(sd, dict) and ("datePublished" in sd or "dateModified" in sd):
            has_date_schema = True
            break
    if has_date_schema:
        freshness_signals.append("schema_date")
        ad_score += 3

    if response_headers.get("last-modified"):
        freshness_signals.append("last_modified_header")
        ad_score += 2

    ad_score = min(25, ad_score)

    ai_discovery_detail = {
        "score": ad_score,
        "max": 25,
        "has_llms_txt": llms_result.get("has_llms_txt", False),
        "geo_schema_types_present": sorted(present_types),
        "geo_schema_types_missing": sorted(missing_types),
        "freshness_signals": freshness_signals,
    }

    # ── Total GEO Score ───────────────────────────────────────────────
    total = ai_crawler_score + cs_score + cd_score + ad_score

    result = {
        "geo_readiness_score": total,
        "ai_crawler_access": ai_crawler_detail,
        "content_structure": content_structure_detail,
        "citation_data": citation_detail,
        "ai_discovery": ai_discovery_detail,
    }
    result["recommendations"] = _generate_geo_recommendations(result)
    return result


# ---------------------------------------------------------------------------
# Phase 2c: GEO recommendation generator
# ---------------------------------------------------------------------------

def _generate_geo_recommendations(geo_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate user-friendly Turkish recommendations from GEO readiness scores.

    Examines each GEO category and produces actionable advice for low-scoring
    areas.  Returns a list of dicts with category/priority/action/reason.
    """
    recs: list[dict[str, Any]] = []

    # ── AI Crawler Access ───────────────────────────────────────────────
    ai = geo_result.get("ai_crawler_access", {})
    if ai.get("bots_blocked"):
        recs.append({
            "category": "AI Erişimi",
            "priority": "high",
            "action": "Yapay zeka arama motorlarının sitenize erişmesine izin verin",
            "reason": "ChatGPT ve benzeri araçlar sitenizi öneremedikçe potansiyel müşterilerinizi kaçırırsınız.",
        })
    elif ai.get("score", 25) < 15:
        recs.append({
            "category": "AI Erişimi",
            "priority": "medium",
            "action": "robots.txt dosyanızda AI botlarına erişim izni verin",
            "reason": "Yapay zeka araçları sitenize tam erişemediğinde sizi öneremez.",
        })

    # ── Content Structure ───────────────────────────────────────────────
    cs = geo_result.get("content_structure", {})
    if not cs.get("has_faq_section"):
        recs.append({
            "category": "İçerik Yapısı",
            "priority": "high",
            "action": "Sıkça Sorulan Sorular (SSS) bölümü ekleyin",
            "reason": "Yapay zeka araçları soru-cevap formatındaki içerikleri çok sever ve kullanıcılara doğrudan sunar.",
        })
    if cs.get("tables_count", 0) == 0 and cs.get("lists_count", 0) == 0:
        recs.append({
            "category": "İçerik Yapısı",
            "priority": "medium",
            "action": "Bilgileri listeler ve tablolarla sunun",
            "reason": "Yapay zeka araçları düzenli bilgileri daha kolay okur ve önerir.",
        })
    if cs.get("question_headings_count", 0) == 0:
        recs.append({
            "category": "İçerik Yapısı",
            "priority": "medium",
            "action": "Başlıklarınızı soru formatında yazın",
            "reason": "Yapay zeka araçları soru-cevap içeriklerini doğrudan yanıt olarak gösterir.",
        })

    # ── Citation & Data Density ─────────────────────────────────────────
    cd = geo_result.get("citation_data", {})
    if cd.get("citation_density_per_1k", 0) < 1:
        recs.append({
            "category": "Kaynak ve Veri",
            "priority": "medium",
            "action": "İçeriğinize güvenilir kaynak linkleri ekleyin",
            "reason": "Yapay zeka araçları kaynaklarla desteklenen içerikleri daha güvenilir bulur.",
        })
    if cd.get("statistics_density_per_1k", 0) < 1:
        recs.append({
            "category": "Kaynak ve Veri",
            "priority": "medium",
            "action": "İçeriğinize istatistikler ve rakamsal veriler ekleyin",
            "reason": "Yapay zeka araçları verilerle desteklenen içerikleri tercih eder ve daha sık önerir.",
        })

    # ── AI Discovery ────────────────────────────────────────────────────
    ad = geo_result.get("ai_discovery", {})
    if not ad.get("has_llms_txt"):
        recs.append({
            "category": "AI Keşfedilebilirlik",
            "priority": "low",
            "action": "Sitenize bir llms.txt dosyası ekleyin",
            "reason": "Bu dosya yapay zeka araçlarına sitenizi ve içeriklerinizi tanıtır.",
        })
    if len(ad.get("geo_schema_types_missing", [])) > 0:
        recs.append({
            "category": "AI Keşfedilebilirlik",
            "priority": "medium",
            "action": "İşletme bilgilerinizi yapılandırılmış veri olarak ekleyin",
            "reason": "Yapay zeka araçları bilgilerinizi daha doğru ve güvenilir şekilde aktarır.",
        })
    if not ad.get("freshness_signals"):
        recs.append({
            "category": "AI Keşfedilebilirlik",
            "priority": "medium",
            "action": "İçeriklerinize tarih bilgisi ekleyin",
            "reason": "Güncel içerikler yapay zeka tarafından daha çok önerilir.",
        })

    return recs


# ---------------------------------------------------------------------------
# Phase 3: New scoring algorithm (v2)
# ---------------------------------------------------------------------------

def _calculate_seo_score_v2(analysis: dict[str, Any]) -> dict[str, Any]:
    """Calculate SEO score using 6-category system (100 points max).

    Returns dict with total_score and per-category breakdown.
    """
    meta = analysis.get("meta_tags", {})
    headings = analysis.get("headings", {})
    images = analysis.get("images", {})
    links = analysis.get("links", {})
    schema = analysis.get("schema_markup", {})
    url_analysis = analysis.get("url_analysis", {})
    robots = analysis.get("robots_txt", {})
    sitemap = analysis.get("sitemap", {})
    ssl_info = analysis.get("ssl_security", {})
    mobile = analysis.get("mobile_analysis", {})
    content = analysis.get("content_quality", {})
    ttfb_ms = analysis.get("ttfb_ms", 0)

    breakdown: dict[str, Any] = {}
    penalties: list[dict[str, Any]] = []

    # --- Category 1: Technical SEO (25 max) ---
    tech = 0
    tech_details = {}
    # robots.txt (5)
    if robots.get("has_robots_txt"):
        tech += 3
        if robots.get("allows_crawling"):
            tech += 2
        tech_details["robots_txt"] = min(5, tech)
    else:
        tech_details["robots_txt"] = 0

    # sitemap (5)
    sm = 0
    if sitemap.get("has_sitemap"):
        sm += 3
        if sitemap.get("url_count", 0) > 0:
            sm += 1
        if sitemap.get("has_lastmod"):
            sm += 1
    tech_details["sitemap"] = sm
    tech += sm

    # SSL + security headers (5)
    sec = 0
    if ssl_info.get("ssl_valid"):
        sec += 2
    if url_analysis.get("is_https"):
        sec += 1
    # Security headers: HSTS, X-Frame-Options, CSP, X-Content-Type-Options
    sec_headers = analysis.get("response_headers", {})
    header_count = sum(1 for h in ("strict-transport-security", "x-frame-options",
                                    "content-security-policy", "x-content-type-options")
                       if sec_headers.get(h))
    sec += min(2, header_count)  # Max 2 points for headers
    tech_details["ssl_security"] = min(5, sec)
    tech += min(5, sec)

    # Redirect chain (3) - fewer is better
    redirect_count = analysis.get("redirect_count", 0)
    if redirect_count == 0:
        redir_score = 3
    elif redirect_count == 1:
        redir_score = 2
    elif redirect_count == 2:
        redir_score = 1
    else:
        redir_score = 0
    tech_details["redirects"] = redir_score
    tech += redir_score

    # TTFB (4) - lower is better
    if ttfb_ms > 0:
        if ttfb_ms < 500:
            ttfb_score = 4
        elif ttfb_ms < 1000:
            ttfb_score = 3
        elif ttfb_ms < 2000:
            ttfb_score = 2
        elif ttfb_ms < 3000:
            ttfb_score = 1
        else:
            ttfb_score = 0
    else:
        ttfb_score = 0
    tech_details["ttfb"] = ttfb_score
    tech += ttfb_score

    # Canonical (3)
    canonical_score = 3 if meta.get("canonical") else 0
    tech_details["canonical"] = canonical_score
    tech += canonical_score

    tech = min(25, tech)
    breakdown["technical_seo"] = {"score": tech, "max": 25, "details": tech_details}

    # --- Category 2: On-Page SEO (25 max) ---
    onpage = 0
    onpage_details = {}

    # Title (5)
    title_len = meta.get("title_length", 0)
    if meta.get("title") and 30 <= title_len <= 60:
        t_score = 5
    elif meta.get("title") and title_len > 0:
        t_score = 2
    else:
        t_score = 0
    onpage_details["title"] = t_score
    onpage += t_score

    # Meta description (5)
    desc_len = meta.get("description_length", 0)
    if meta.get("description") and 120 <= desc_len <= 160:
        d_score = 5
    elif meta.get("description") and desc_len > 0:
        d_score = 2
    else:
        d_score = 0
    onpage_details["meta_description"] = d_score
    onpage += d_score

    # H1 (5)
    h1_count = headings.get("h1_count", 0)
    if h1_count == 1:
        h1_score = 5
    elif h1_count > 1:
        h1_score = 2
    else:
        h1_score = 0
    onpage_details["h1"] = h1_score
    onpage += h1_score

    # Heading hierarchy (3)
    hier_score = 0
    if headings.get("h2"):
        hier_score += 2
    if headings.get("h3"):
        hier_score += 1
    onpage_details["heading_hierarchy"] = hier_score
    onpage += hier_score

    # Image alt (4)
    total_images = images.get("total_images", 0)
    if total_images > 0:
        alt_ratio = images.get("images_with_alt", 0) / total_images
        img_score = round(alt_ratio * 4)
    else:
        img_score = 2  # No images is neutral
    onpage_details["image_alt"] = img_score
    onpage += img_score

    # URL structure (3)
    url_score = 0
    if url_analysis.get("is_seo_friendly"):
        url_score += 2
    if url_analysis.get("has_keywords"):
        url_score += 1
    onpage_details["url_structure"] = url_score
    onpage += url_score

    onpage = min(25, onpage)
    breakdown["on_page_seo"] = {"score": onpage, "max": 25, "details": onpage_details}

    # --- Category 3: Content Quality (20 max) ---
    cq = 0
    cq_details = {}

    # Word count (5)
    wc = content.get("word_count", analysis.get("word_count", 0))
    if wc >= 1000:
        wc_score = 5
    elif wc >= 600:
        wc_score = 4
    elif wc >= 300:
        wc_score = 3
    elif wc >= 100:
        wc_score = 1
    else:
        wc_score = 0
    cq_details["word_count"] = wc_score
    cq += wc_score

    # Readability (3)
    readability = content.get("readability_score", 0)
    if 5 <= readability <= 12:
        r_score = 3  # Good range
    elif 3 <= readability < 5 or 12 < readability <= 16:
        r_score = 2  # Acceptable
    elif readability > 0:
        r_score = 1
    else:
        r_score = 0
    cq_details["readability"] = r_score
    cq += r_score

    # Keyword in title (3)
    kw_title = 3 if content.get("keyword_in_title") else 0
    cq_details["keyword_in_title"] = kw_title
    cq += kw_title

    # Keyword in H1 (3)
    kw_h1 = 3 if content.get("keyword_in_h1") else 0
    cq_details["keyword_in_h1"] = kw_h1
    cq += kw_h1

    # Keyword in first paragraph (2)
    kw_fp = 2 if content.get("keyword_in_first_paragraph") else 0
    cq_details["keyword_in_first_para"] = kw_fp
    cq += kw_fp

    # No stuffing (4) — awarded when clean
    stuff_score = 0 if content.get("keyword_stuffing") else 4
    cq_details["no_stuffing"] = stuff_score
    cq += stuff_score

    cq = min(20, cq)
    breakdown["content_quality"] = {"score": cq, "max": 20, "details": cq_details}

    # --- Category 4: Mobile & Performance (15 max) ---
    mob = 0
    mob_details = {}

    # Viewport (5)
    vp_score = 5 if mobile.get("has_viewport") else 0
    mob_details["viewport"] = vp_score
    mob += vp_score

    # Responsive (3)
    resp_score = 0
    if mobile.get("has_responsive_meta"):
        resp_score += 2
    if mobile.get("has_media_queries"):
        resp_score += 1
    mob_details["responsive"] = resp_score
    mob += resp_score

    # Touch icon (3)
    ti_score = 3 if mobile.get("touch_icon") else 0
    mob_details["touch_icon"] = ti_score
    mob += ti_score

    # Mobile TTFB (4) — uses ttfb from mobile fetch if available
    mobile_ttfb = analysis.get("mobile_ttfb_ms", 0)
    if mobile_ttfb > 0:
        if mobile_ttfb < 600:
            mt_score = 4
        elif mobile_ttfb < 1200:
            mt_score = 3
        elif mobile_ttfb < 2500:
            mt_score = 2
        elif mobile_ttfb < 4000:
            mt_score = 1
        else:
            mt_score = 0
    else:
        # Fall back to desktop TTFB with slight penalty
        mt_score = max(0, ttfb_score - 1)
    mob_details["mobile_ttfb"] = mt_score
    mob += mt_score

    mob = min(15, mob)
    breakdown["mobile_performance"] = {"score": mob, "max": 15, "details": mob_details}

    # --- Category 5: Schema & Structured Data (10 max) ---
    sd = 0
    sd_details = {}

    # JSON-LD (5)
    if schema.get("has_schema"):
        sd += 5
        sd_details["json_ld"] = 5
    else:
        sd_details["json_ld"] = 0

    # Schema types (3) — more types = better
    num_types = len(schema.get("schema_types", []))
    st_score = min(3, num_types)
    sd_details["schema_types"] = st_score
    sd += st_score

    # OG tags (2)
    og_score = 0
    if meta.get("og_title"):
        og_score += 1
    if meta.get("og_description"):
        og_score += 1
    sd_details["og_tags"] = og_score
    sd += og_score

    sd = min(10, sd)
    breakdown["schema_structured_data"] = {"score": sd, "max": 10, "details": sd_details}

    # --- Category 6: Authority Signals (5 max) ---
    auth = 0
    auth_details = {}

    # External links (2)
    ext_score = min(2, links.get("external_links", 0))
    auth_details["external_links"] = ext_score
    auth += ext_score

    # Internal links (2) — good internal linking
    int_links = links.get("internal_links", 0)
    if int_links >= 10:
        il_score = 2
    elif int_links >= 3:
        il_score = 1
    else:
        il_score = 0
    auth_details["internal_links"] = il_score
    auth += il_score

    # Social links (1) — presence of social media links
    social_domains = {"instagram.com", "facebook.com", "twitter.com", "x.com",
                      "linkedin.com", "youtube.com", "tiktok.com"}
    ext_domains = set(d.lower() for d in links.get("external_link_domains", []))
    has_social = bool(ext_domains & social_domains)
    soc_score = 1 if has_social else 0
    auth_details["social_links"] = soc_score
    auth += soc_score

    auth = min(5, auth)
    breakdown["authority_signals"] = {"score": auth, "max": 5, "details": auth_details}

    # --- Penalties ---
    raw_total = tech + onpage + cq + mob + sd + auth

    if not meta.get("title"):
        penalties.append({"reason": "Missing title tag", "points": -15})
    if headings.get("h1_count", 0) == 0:
        penalties.append({"reason": "Missing H1 heading", "points": -10})
    if not url_analysis.get("is_https"):
        penalties.append({"reason": "Not using HTTPS", "points": -10})
    if headings.get("h1_count", 0) > 1:
        penalties.append({"reason": "Multiple H1 tags", "points": -5})
    if content.get("keyword_stuffing"):
        penalties.append({"reason": "Keyword stuffing detected", "points": -5})
    if robots.get("blocked_paths"):
        critical_blocked = [p for p in robots.get("blocked_paths", [])
                           if p in ("/", "/blog", "/products", "/services")]
        if critical_blocked:
            penalties.append({"reason": f"robots.txt blocks important paths: {', '.join(critical_blocked)}", "points": -5})
    if not sitemap.get("has_sitemap"):
        penalties.append({"reason": "No sitemap.xml found", "points": -3})
    if ssl_info.get("cert_expiry_days") is not None and 0 < ssl_info["cert_expiry_days"] < 30:
        penalties.append({"reason": f"SSL expires in {ssl_info['cert_expiry_days']} days", "points": -3})
    if analysis.get("redirect_count", 0) >= 3:
        penalties.append({"reason": f"Redirect chain ({analysis['redirect_count']} hops)", "points": -2})

    penalty_total = sum(p["points"] for p in penalties)
    final_score = max(0, min(100, raw_total + penalty_total))

    result = {
        "total_score": final_score,
        "raw_score": raw_total,
        "penalty_total": penalty_total,
        "breakdown": breakdown,
        "penalties": penalties,
    }
    result["recommendations"] = _generate_seo_recommendations(breakdown, penalties)
    return result


# ---------------------------------------------------------------------------
# Phase 3b: SEO recommendation generator
# ---------------------------------------------------------------------------

def _generate_seo_recommendations(
    breakdown: dict[str, Any],
    penalties: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate user-friendly Turkish recommendations from SEO score breakdown.

    Examines each category's sub-metrics and produces actionable advice for
    low-scoring areas.  Returns a list of dicts with
    category / priority / action / reason.
    """
    recs: list[dict[str, Any]] = []

    # ── Technical SEO ───────────────────────────────────────────────────
    tech = breakdown.get("technical_seo", {}).get("details", {})

    if tech.get("robots_txt", 0) == 0:
        recs.append({
            "category": "Teknik Altyapı",
            "priority": "high",
            "action": "Web sitenize bir robots.txt dosyası ekleyin",
            "reason": "Arama motorları sitenizi nasıl tarayacağını bilemiyor.",
        })
    if tech.get("sitemap", 0) == 0:
        recs.append({
            "category": "Teknik Altyapı",
            "priority": "high",
            "action": "Site haritası (sitemap) oluşturun",
            "reason": "Arama motorları sayfalarınızı daha kolay bulsun.",
        })
    if tech.get("ssl_security", 0) <= 1:
        recs.append({
            "category": "Teknik Altyapı",
            "priority": "high",
            "action": "Sitenizi HTTPS ile güvenli hale getirin",
            "reason": "Ziyaretçiler güvende olmadığını düşünebilir ve Google güvenli siteleri tercih eder.",
        })
    if tech.get("ttfb", 0) <= 1:
        recs.append({
            "category": "Teknik Altyapı",
            "priority": "medium",
            "action": "Sitenizin açılış hızını artırın",
            "reason": "Siteniz yavaş açılıyor, ziyaretçiler beklemeden çıkabilir.",
        })
    if tech.get("canonical", 0) == 0:
        recs.append({
            "category": "Teknik Altyapı",
            "priority": "low",
            "action": "Her sayfanın orijinal adresini belirtin (canonical tag)",
            "reason": "Aynı içerik farklı adreslerde görünüp sıralamanızı düşürebilir.",
        })

    # ── On-Page SEO ─────────────────────────────────────────────────────
    onpage = breakdown.get("on_page_seo", {}).get("details", {})

    if onpage.get("title", 0) == 0:
        recs.append({
            "category": "Sayfa İçi SEO",
            "priority": "high",
            "action": "Sayfa başlığınızı 50-60 karakter arasında yazın",
            "reason": "Başlık, Google'da ilk görünen şeydir ve tıklanma oranını doğrudan etkiler.",
        })
    elif onpage.get("title", 0) <= 2:
        recs.append({
            "category": "Sayfa İçi SEO",
            "priority": "medium",
            "action": "Sayfa başlığınızı 50-60 karakter arasında optimize edin",
            "reason": "Başlığınız var ama ideal uzunlukta değil, Google'da tam görünmeyebilir.",
        })
    if onpage.get("meta_description", 0) == 0:
        recs.append({
            "category": "Sayfa İçi SEO",
            "priority": "high",
            "action": "Sayfa açıklamanızı 120-160 karakter arasında yazın",
            "reason": "İnsanlar Google'da bu açıklamayı görüp tıklayıp tıklamamaya karar verir.",
        })
    elif onpage.get("meta_description", 0) <= 2:
        recs.append({
            "category": "Sayfa İçi SEO",
            "priority": "medium",
            "action": "Sayfa açıklamanızı 120-160 karakter arasında düzenleyin",
            "reason": "Açıklamanız var ama ideal uzunlukta değil.",
        })
    if onpage.get("h1", 0) == 0:
        recs.append({
            "category": "Sayfa İçi SEO",
            "priority": "high",
            "action": "Her sayfanın bir ana başlığı (H1) olsun",
            "reason": "Ana başlık sayfanın ne hakkında olduğunu hem ziyaretçilere hem Google'a anlatır.",
        })
    if onpage.get("image_alt", 0) <= 1:
        recs.append({
            "category": "Sayfa İçi SEO",
            "priority": "medium",
            "action": "Resimlere açıklayıcı metin (alt text) ekleyin",
            "reason": "Arama motorları resimlerin ne olduğunu anlayamaz, siz anlatmalısınız.",
        })

    # ── Content Quality ─────────────────────────────────────────────────
    cq = breakdown.get("content_quality", {}).get("details", {})

    if cq.get("word_count", 0) <= 1:
        recs.append({
            "category": "İçerik Kalitesi",
            "priority": "high",
            "action": "Sayfalarınıza daha fazla içerik ekleyin",
            "reason": "Kısa içerikler Google'da üst sıralara çıkmakta zorlanır.",
        })
    if cq.get("no_stuffing", 4) == 0:
        recs.append({
            "category": "İçerik Kalitesi",
            "priority": "high",
            "action": "Anahtar kelimeleri daha doğal kullanın, tekrardan kaçının",
            "reason": "Aynı kelimeyi çok fazla tekrarlamak Google tarafından cezalandırılır.",
        })
    if cq.get("keyword_in_title", 0) == 0 and cq.get("keyword_in_h1", 0) == 0:
        recs.append({
            "category": "İçerik Kalitesi",
            "priority": "medium",
            "action": "Anahtar kelimenizi başlıkta ve ana başlıkta kullanın",
            "reason": "Google sayfanızın konusunu anlamak için başlıklara bakar.",
        })

    # ── Mobile & Performance ────────────────────────────────────────────
    mob = breakdown.get("mobile_performance", {}).get("details", {})

    if mob.get("viewport", 0) == 0:
        recs.append({
            "category": "Mobil Uyumluluk",
            "priority": "high",
            "action": "Sitenizi mobil uyumlu yapın",
            "reason": "İnsanların çoğu sitenize telefondan giriyor, mobil uyumsuz siteler Google'da düşer.",
        })
    if mob.get("touch_icon", 0) == 0:
        recs.append({
            "category": "Mobil Uyumluluk",
            "priority": "low",
            "action": "Telefonlar için bir site ikonu ekleyin",
            "reason": "Favori olarak eklendiğinde ikonunuz görünsün, profesyonel görünüm sağlar.",
        })

    # ── Schema & Structured Data ────────────────────────────────────────
    sd = breakdown.get("schema_structured_data", {}).get("details", {})

    if sd.get("json_ld", 0) == 0:
        recs.append({
            "category": "Yapılandırılmış Veri",
            "priority": "medium",
            "action": "İşletme bilgilerinizi Google'a tanıtın (yapılandırılmış veri)",
            "reason": "Adres, telefon, çalışma saatleri gibi bilgiler Google'da direkt görünsün.",
        })
    if sd.get("og_tags", 0) == 0:
        recs.append({
            "category": "Yapılandırılmış Veri",
            "priority": "low",
            "action": "Sosyal medya paylaşım bilgilerinizi ekleyin",
            "reason": "Siteniz paylaşıldığında güzel bir önizleme göstersin.",
        })

    # ── Authority Signals ───────────────────────────────────────────────
    auth = breakdown.get("authority_signals", {}).get("details", {})

    if auth.get("external_links", 0) == 0:
        recs.append({
            "category": "Otorite Sinyalleri",
            "priority": "low",
            "action": "Güvenilir kaynaklara referans linkler verin",
            "reason": "Google güvenilir kaynaklara referans veren siteleri sever.",
        })
    if auth.get("internal_links", 0) == 0:
        recs.append({
            "category": "Otorite Sinyalleri",
            "priority": "medium",
            "action": "Sayfalarınız arasında bağlantılar verin",
            "reason": "Ziyaretçiler diğer sayfalarınızı da keşfetsin ve sitenizde daha uzun kalsın.",
        })

    # ── Penalties → additional high-priority recs ───────────────────────
    _PENALTY_MAP = {
        "Missing title tag": {
            "category": "Sayfa İçi SEO",
            "priority": "high",
            "action": "Sayfanıza bir başlık etiketi ekleyin",
            "reason": "Başlık etiketi olmadan Google sayfanızı doğru listeleyemez.",
        },
        "Missing H1 heading": {
            "category": "Sayfa İçi SEO",
            "priority": "high",
            "action": "Sayfanıza bir ana başlık (H1) ekleyin",
            "reason": "Ana başlık olmadan sayfanızın konusu belirsiz kalır.",
        },
        "Not using HTTPS": {
            "category": "Teknik Altyapı",
            "priority": "high",
            "action": "Sitenizi HTTPS'e geçirin",
            "reason": "Güvenli olmayan siteler Google'da daha düşük sıralanır ve ziyaretçiler uyarı görür.",
        },
        "Multiple H1 tags": {
            "category": "Sayfa İçi SEO",
            "priority": "medium",
            "action": "Her sayfada yalnızca bir ana başlık (H1) kullanın",
            "reason": "Birden fazla H1 kullanmak arama motorlarını karıştırır.",
        },
        "Keyword stuffing detected": {
            "category": "İçerik Kalitesi",
            "priority": "high",
            "action": "Anahtar kelime tekrarını azaltın, doğal bir dil kullanın",
            "reason": "Google anahtar kelime doldurmayı tespit eder ve sitenizi cezalandırır.",
        },
        "No sitemap.xml found": {
            "category": "Teknik Altyapı",
            "priority": "medium",
            "action": "Bir sitemap.xml dosyası oluşturun",
            "reason": "Arama motorları sitenizdeki tüm sayfaları keşfedebilsin.",
        },
    }

    for pen in penalties:
        reason_key = pen.get("reason", "")
        # Exact match first
        if reason_key in _PENALTY_MAP:
            recs.append(_PENALTY_MAP[reason_key])
        else:
            # Pattern-based fallback for dynamic penalty messages
            if "SSL expires" in reason_key:
                recs.append({
                    "category": "Teknik Altyapı",
                    "priority": "high",
                    "action": "SSL sertifikanızı yenileyin",
                    "reason": "SSL sertifikanızın süresi dolmak üzere, siteniz güvensiz olarak işaretlenebilir.",
                })
            elif "Redirect chain" in reason_key:
                recs.append({
                    "category": "Teknik Altyapı",
                    "priority": "medium",
                    "action": "Yönlendirme zincirlerini kısaltın",
                    "reason": "Çok fazla yönlendirme sitenizin yavaş açılmasına neden olur.",
                })
            elif "robots.txt blocks" in reason_key:
                recs.append({
                    "category": "Teknik Altyapı",
                    "priority": "high",
                    "action": "robots.txt dosyanızda önemli sayfaların engellenmediğinden emin olun",
                    "reason": "Önemli sayfalarınız arama motorları tarafından taranamıyor.",
                })

    return recs


async def _serper_search(
    query: str,
    num: int = 10,
    search_type: str = "text",
    gl: str = "tr",
    hl: str = "tr",
) -> dict[str, Any]:
    """Shared helper for Serper.dev Google Search API.

    Args:
        query: Search query.
        num: Number of results.
        search_type: "text" or "news".
        gl: Country code for geolocation (default "tr").
        hl: Language code (default "tr").

    Returns:
        Raw JSON response from Serper.dev.

    Raises:
        ValueError: If SERPER_API_KEY is not configured.
        httpx.HTTPStatusError: On non-2xx responses.
    """
    settings = get_settings()
    if not settings.serper_api_key:
        raise ValueError("SERPER_API_KEY not configured")

    endpoint = (
        "https://google.serper.dev/news"
        if search_type == "news"
        else "https://google.serper.dev/search"
    )

    headers = {
        "X-API-KEY": settings.serper_api_key,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": num, "gl": gl, "hl": hl}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            endpoint, headers=headers, content=json.dumps(payload),
        )
        resp.raise_for_status()
        return resp.json()


@function_tool
async def web_search(
    query: str,
    num_results: int = 5,
    search_type: str = "text",
) -> dict[str, Any]:
    """
    Search the web using Google (via Serper.dev API).

    Args:
        query: Search query string.
        num_results: Number of results to return (default 5, max 10).
        search_type: Type of search - "text" (default) or "news" for recent news.

    Returns:
        Dictionary with search results including titles, URLs, and snippets.
    """
    try:
        num_results = min(num_results, 10)

        data = await _serper_search(query, num=num_results, search_type=search_type)

        results = []

        if search_type == "news":
            for r in data.get("news", []):
                results.append({
                    "url": r.get("link", ""),
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "date": r.get("date", ""),
                    "source": r.get("source", ""),
                })
        else:
            for r in data.get("organic", []):
                results.append({
                    "url": r.get("link", ""),
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                })

        return {
            "success": True,
            "query": query,
            "search_type": search_type,
            "result_count": len(results),
            "results": results,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "query": query,
            "results": [],
        }


@function_tool
async def scrape_website(
    url: str,
    extract_type: str = "business_analysis",
) -> dict[str, Any]:
    """
    Scrape a website and extract information for business analysis.

    Args:
        url: The URL to scrape.
        extract_type: Type of extraction - "business_analysis" (default) or "content".

    Returns:
        Dictionary with extracted data including title, description, contact info, social links.
    """
    try:
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme:
            url = f"https://{url}"
            parsed = urlparse(url)
        
        if not parsed.netloc:
            return {
                "success": False,
                "error": "Invalid URL provided",
                "url": url,
            }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                url,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                }
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "url": url,
                }

            soup = BeautifulSoup(response.text, "html.parser")

            # Extract basic info
            title = None
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)

            # Meta description
            description = None
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                description = meta_desc.get("content", "")

            # OG tags
            og_title = soup.find("meta", property="og:title")
            og_description = soup.find("meta", property="og:description")
            og_image = soup.find("meta", property="og:image")

            # Extract contact information
            contact_info = _extract_contact_info(soup, response.text)

            # Extract social media links
            social_links = _extract_social_links(soup)

            # Extract main content text (for analysis)
            main_content = _extract_main_content(soup)

            # Try to identify business type/industry keywords
            keywords = _extract_keywords(soup)

            return {
                "success": True,
                "url": str(response.url),
                "title": title,
                "description": description,
                "og_data": {
                    "title": og_title.get("content") if og_title else None,
                    "description": og_description.get("content") if og_description else None,
                    "image": og_image.get("content") if og_image else None,
                },
                "contact_info": contact_info,
                "social_links": social_links,
                "keywords": keywords,
                "main_content_preview": main_content[:1000] if main_content else None,
                "content_length": len(main_content) if main_content else 0,
            }

    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timeout - website took too long to respond",
            "url": url,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url": url,
        }


def _extract_contact_info(soup: BeautifulSoup, html_text: str) -> dict[str, Any]:
    """Extract contact information from the page."""
    contact = {
        "emails": [],
        "phones": [],
        "address": None,
    }

    # Email patterns
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = set(re.findall(email_pattern, html_text))
    # Filter out common non-contact emails
    contact["emails"] = [
        e for e in emails 
        if not any(x in e.lower() for x in ["example", "test", "placeholder", "domain"])
    ][:5]  # Limit to 5

    # Phone patterns (Turkish and international)
    phone_patterns = [
        r'\+90\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}',  # +90 XXX XXX XX XX
        r'0\d{3}\s*\d{3}\s*\d{2}\s*\d{2}',  # 0XXX XXX XX XX
        r'\(\d{3}\)\s*\d{3}[-.\s]?\d{2}[-.\s]?\d{2}',  # (XXX) XXX XX XX
        r'\+\d{1,3}[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # International
    ]
    phones = set()
    for pattern in phone_patterns:
        phones.update(re.findall(pattern, html_text))
    contact["phones"] = list(phones)[:5]

    # Try to find address in common patterns
    address_tags = soup.find_all(["address", "p", "span", "div"], 
                                  class_=lambda x: x and any(addr in str(x).lower() for addr in ["address", "adres", "location", "konum"]))
    if address_tags:
        contact["address"] = address_tags[0].get_text(strip=True)[:200]

    return contact


def _extract_social_links(soup: BeautifulSoup) -> dict[str, str | None]:
    """Extract social media links from the page."""
    social = {
        "instagram": None,
        "facebook": None,
        "twitter": None,
        "linkedin": None,
        "youtube": None,
        "tiktok": None,
    }

    all_links = soup.find_all("a", href=True)
    for link in all_links:
        href = link["href"].lower()
        if "instagram.com" in href and not social["instagram"]:
            social["instagram"] = link["href"]
        elif "facebook.com" in href and not social["facebook"]:
            social["facebook"] = link["href"]
        elif "twitter.com" in href or "x.com" in href and not social["twitter"]:
            social["twitter"] = link["href"]
        elif "linkedin.com" in href and not social["linkedin"]:
            social["linkedin"] = link["href"]
        elif "youtube.com" in href and not social["youtube"]:
            social["youtube"] = link["href"]
        elif "tiktok.com" in href and not social["tiktok"]:
            social["tiktok"] = link["href"]

    return social


def _extract_main_content(soup: BeautifulSoup) -> str:
    """Extract main text content from the page."""
    # Remove script and style elements
    for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
        element.decompose()

    # Get text
    text = soup.get_text(separator=" ", strip=True)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text


def _extract_keywords(soup: BeautifulSoup) -> list[str]:
    """Extract keywords from meta tags."""
    keywords = []
    
    # Meta keywords
    meta_keywords = soup.find("meta", attrs={"name": "keywords"})
    if meta_keywords and meta_keywords.get("content"):
        keywords.extend([k.strip() for k in meta_keywords["content"].split(",")])

    # Limit to 10 keywords
    return keywords[:10]


def _extract_headings(soup: BeautifulSoup) -> dict[str, Any]:
    """Extract heading hierarchy for SEO analysis."""
    headings = {
        "h1": [],
        "h2": [],
        "h3": [],
        "h4": [],
        "h5": [],
        "h6": [],
        "h1_count": 0,
        "has_single_h1": False,
    }

    for level in range(1, 7):
        tag_name = f"h{level}"
        tags = soup.find_all(tag_name)
        headings[tag_name] = [tag.get_text(strip=True)[:200] for tag in tags[:20]]  # Limit

    headings["h1_count"] = len(headings["h1"])
    headings["has_single_h1"] = headings["h1_count"] == 1

    return headings


def _extract_images_seo(soup: BeautifulSoup) -> dict[str, Any]:
    """Extract image alt text analysis for SEO."""
    images = soup.find_all("img")

    result = {
        "total_images": len(images),
        "images_with_alt": 0,
        "images_without_alt": 0,
        "alt_texts": [],
        "missing_alt_srcs": [],
    }

    for img in images[:50]:  # Limit to 50 images
        alt = img.get("alt", "").strip()
        src = img.get("src", "")[:200]

        if alt:
            result["images_with_alt"] += 1
            result["alt_texts"].append(alt[:100])
        else:
            result["images_without_alt"] += 1
            if src:
                result["missing_alt_srcs"].append(src)

    # Limit lists
    result["alt_texts"] = result["alt_texts"][:20]
    result["missing_alt_srcs"] = result["missing_alt_srcs"][:10]

    return result


def _extract_links_seo(soup: BeautifulSoup, base_url: str) -> dict[str, Any]:
    """Extract link analysis for SEO."""
    from urllib.parse import urljoin

    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc.lower()

    links = soup.find_all("a", href=True)

    result = {
        "total_links": len(links),
        "internal_links": 0,
        "external_links": 0,
        "nofollow_links": 0,
        "internal_link_urls": [],
        "external_link_domains": set(),
    }

    for link in links:
        href = link.get("href", "")
        rel = link.get("rel", [])

        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        # Check nofollow
        if isinstance(rel, list) and "nofollow" in rel:
            result["nofollow_links"] += 1
        elif isinstance(rel, str) and "nofollow" in rel:
            result["nofollow_links"] += 1

        # Resolve relative URLs
        full_url = urljoin(base_url, href)
        parsed_link = urlparse(full_url)
        link_domain = parsed_link.netloc.lower()

        if link_domain == base_domain or not link_domain:
            result["internal_links"] += 1
            if len(result["internal_link_urls"]) < 30:
                result["internal_link_urls"].append(full_url)
        else:
            result["external_links"] += 1
            result["external_link_domains"].add(link_domain)

    # Convert set to list
    result["external_link_domains"] = list(result["external_link_domains"])[:20]

    return result


def _extract_schema_markup(soup: BeautifulSoup) -> dict[str, Any]:
    """Extract JSON-LD schema markup."""
    import json

    result = {
        "has_schema": False,
        "schema_types": [],
        "schema_data": [],
    }

    # Find JSON-LD scripts
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts[:10]:  # Limit
        try:
            content = script.string
            if content:
                data = json.loads(content)
                result["has_schema"] = True

                # Handle single object or array
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "@type" in item:
                            result["schema_types"].append(item["@type"])
                        result["schema_data"].append(item)
                elif isinstance(data, dict):
                    if "@type" in data:
                        result["schema_types"].append(data["@type"])
                    result["schema_data"].append(data)
        except (json.JSONDecodeError, TypeError):
            continue

    # Deduplicate schema types
    result["schema_types"] = list(set(result["schema_types"]))

    return result


def _analyze_url_seo(url: str) -> dict[str, Any]:
    """Analyze URL for SEO-friendliness."""
    parsed = urlparse(url)

    result = {
        "url": url,
        "is_https": parsed.scheme == "https",
        "is_seo_friendly": True,
        "has_keywords": False,
        "length": len(url),
        "issues": [],
    }

    path = parsed.path.lower()

    # Check for SEO issues
    if len(url) > 75:
        result["issues"].append("URL too long (>75 chars)")
        result["is_seo_friendly"] = False

    if re.search(r'[A-Z]', parsed.path):
        result["issues"].append("URL contains uppercase letters")

    if re.search(r'[_]', path):
        result["issues"].append("URL contains underscores (use hyphens instead)")

    if re.search(r'\d{5,}', path):
        result["issues"].append("URL contains long numeric IDs")
        result["is_seo_friendly"] = False

    if "?" in url and len(parsed.query) > 50:
        result["issues"].append("URL has long query parameters")
        result["is_seo_friendly"] = False

    if not result["is_https"]:
        result["issues"].append("Not using HTTPS")
        result["is_seo_friendly"] = False

    # Check if URL path contains keywords (non-empty, meaningful words)
    path_words = [w for w in re.split(r'[-/]', path) if len(w) > 2]
    if path_words:
        result["has_keywords"] = True

    return result


def _calculate_keyword_density(text: str, top_n: int = 15) -> dict[str, float]:
    """Calculate keyword density for top N words."""
    import re
    from collections import Counter

    # Tokenize and clean
    words = re.findall(r'\b[a-zA-ZçğıöşüÇĞİÖŞÜ]{3,}\b', text.lower())

    # Common stop words (Turkish + English)
    stop_words = {
        "the", "and", "for", "are", "but", "not", "you", "all", "can", "has", "her",
        "was", "one", "our", "out", "his", "had", "been", "have", "from", "this",
        "that", "with", "will", "what", "when", "your", "which", "their", "there",
        "bir", "ile", "için", "olan", "gibi", "daha", "ise", "olan", "den", "dan",
        "veya", "ama", "ancak", "hem", "kadar", "sonra", "önce", "ayrıca", "şekilde",
        "olarak", "diğer", "bütün", "her", "bazı", "çok", "diye", "henüz", "bile",
    }

    # Filter stop words
    filtered_words = [w for w in words if w not in stop_words]

    if not filtered_words:
        return {}

    # Count and calculate density
    total_words = len(filtered_words)
    word_counts = Counter(filtered_words)

    density = {}
    for word, count in word_counts.most_common(top_n):
        density[word] = round((count / total_words) * 100, 2)

    return density


def _calculate_seo_score(analysis: dict[str, Any]) -> int:
    """Calculate overall SEO score (0-100)."""
    score = 50  # Base score

    meta = analysis.get("meta_tags", {})
    headings = analysis.get("headings", {})
    images = analysis.get("images", {})
    links = analysis.get("links", {})
    schema = analysis.get("schema_markup", {})
    url_analysis = analysis.get("url_analysis", {})

    # Meta tags (+20 max)
    if meta.get("title") and 30 <= meta.get("title_length", 0) <= 60:
        score += 5
    if meta.get("description") and 120 <= meta.get("description_length", 0) <= 160:
        score += 5
    if meta.get("keywords"):
        score += 2
    if meta.get("canonical"):
        score += 3
    if meta.get("og_title") and meta.get("og_description"):
        score += 5

    # Headings (+15 max)
    if headings.get("has_single_h1"):
        score += 8
    elif headings.get("h1_count", 0) > 0:
        score += 3
    if headings.get("h2"):
        score += 4
    if headings.get("h3"):
        score += 3

    # Images (+10 max)
    total_images = images.get("total_images", 0)
    if total_images > 0:
        alt_ratio = images.get("images_with_alt", 0) / total_images
        score += int(alt_ratio * 10)

    # Schema markup (+10 max)
    if schema.get("has_schema"):
        score += 5
        if len(schema.get("schema_types", [])) > 1:
            score += 5

    # URL analysis (+5 max)
    if url_analysis.get("is_https"):
        score += 2
    if url_analysis.get("is_seo_friendly"):
        score += 3

    # Links (+5 max)
    internal = links.get("internal_links", 0)
    if internal >= 5:
        score += 3
    if links.get("external_links", 0) > 0:
        score += 2

    # Penalties
    if not meta.get("title"):
        score -= 10
    if not meta.get("description"):
        score -= 5
    if headings.get("h1_count", 0) == 0:
        score -= 10
    if headings.get("h1_count", 0) > 1:
        score -= 5

    return max(0, min(100, score))


async def _fetch_page(url: str) -> tuple[str | None, str | None]:
    """Fetch a single page and return (html_content, final_url).

    Thin wrapper around _fetch_page_enhanced for backward compatibility.
    """
    result = await _fetch_page_enhanced(url)
    if result["success"]:
        return result["html"], result["final_url"]
    return None, None


def _analyze_single_page_seo(
    html: str,
    url: str,
    *,
    enhanced_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze a single page for SEO factors.

    Args:
        html: Raw HTML string.
        url: Page URL.
        enhanced_data: Optional dict from _fetch_page_enhanced and async checks
            (robots_txt, sitemap, ssl_security, ttfb_ms, redirect_count,
             response_headers, mobile_ttfb_ms).  When provided, the new
             v2 scoring algorithm is used.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Extract meta tags
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    meta_desc = soup.find("meta", attrs={"name": "description"})
    description = meta_desc.get("content", "") if meta_desc else None

    meta_keywords = soup.find("meta", attrs={"name": "keywords"})
    keywords = []
    if meta_keywords and meta_keywords.get("content"):
        keywords = [k.strip() for k in meta_keywords["content"].split(",")][:15]

    meta_robots = soup.find("meta", attrs={"name": "robots"})
    robots_meta = meta_robots.get("content") if meta_robots else None

    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    canonical = canonical_tag.get("href") if canonical_tag else None

    og_title = soup.find("meta", property="og:title")
    og_description = soup.find("meta", property="og:description")
    og_image = soup.find("meta", property="og:image")

    meta_tags = {
        "title": title,
        "title_length": len(title) if title else 0,
        "description": description,
        "description_length": len(description) if description else 0,
        "keywords": keywords,
        "robots": robots_meta,
        "canonical": canonical,
        "og_title": og_title.get("content") if og_title else None,
        "og_description": og_description.get("content") if og_description else None,
        "og_image": og_image.get("content") if og_image else None,
    }

    # Extract other SEO factors
    headings = _extract_headings(soup)
    images = _extract_images_seo(soup)
    links = _extract_links_seo(soup, url)
    schema = _extract_schema_markup(soup)
    url_analysis = _analyze_url_seo(url)

    # Extract content for analysis (clone soup to avoid mutating for mobile check)
    content_soup = BeautifulSoup(html, "html.parser")
    for element in content_soup(["script", "style", "nav", "header", "footer", "aside"]):
        element.decompose()
    main_text = content_soup.get_text(separator=" ", strip=True)
    main_text = re.sub(r'\s+', ' ', main_text)

    word_count = len(main_text.split())
    keyword_density = _calculate_keyword_density(main_text)

    analysis: dict[str, Any] = {
        "url": url,
        "meta_tags": meta_tags,
        "headings": headings,
        "images": images,
        "links": links,
        "schema_markup": schema,
        "url_analysis": url_analysis,
        "content_length": len(main_text),
        "word_count": word_count,
        "keyword_density": keyword_density,
    }

    if enhanced_data:
        # Merge in data from async checks
        analysis["robots_txt"] = enhanced_data.get("robots_txt", {})
        analysis["sitemap"] = enhanced_data.get("sitemap", {})
        analysis["ssl_security"] = enhanced_data.get("ssl_security", {})
        analysis["response_headers"] = enhanced_data.get("response_headers", {})
        analysis["ttfb_ms"] = enhanced_data.get("ttfb_ms", 0)
        analysis["redirect_count"] = enhanced_data.get("redirect_count", 0)
        analysis["redirect_chain"] = enhanced_data.get("redirect_chain", [])

        # Synchronous checks on parsed HTML
        mobile_result = _check_mobile_friendliness(soup, html)
        analysis["mobile_analysis"] = mobile_result

        content_quality = _analyze_content_quality(
            main_text, title, headings.get("h1", []), keyword_density,
        )
        analysis["content_quality"] = content_quality

        # Mobile TTFB (if provided)
        analysis["mobile_ttfb_ms"] = enhanced_data.get("mobile_ttfb_ms", 0)

        # GEO readiness analysis (uses already-parsed data, no extra HTTP)
        geo_analysis = _analyze_geo_readiness(
            soup, main_text, enhanced_data.get("robots_txt", {}),
            enhanced_data.get("llms_txt", {}), schema, content_quality, links,
            enhanced_data.get("response_headers", {}),
        )
        analysis["geo_analysis"] = geo_analysis

        # Inject response headers for SSL scoring
        ssl_data = enhanced_data.get("ssl_security", {})
        ssl_data["security_headers"] = enhanced_data.get("response_headers", {})
        analysis["ssl_security"] = ssl_data

        # Use v2 scoring
        score_result = _calculate_seo_score_v2(analysis)
        analysis["seo_score"] = score_result["total_score"]
        analysis["score_breakdown"] = score_result
    else:
        # Fallback: legacy v1 scoring for competitor scraping etc.
        analysis["seo_score"] = _calculate_seo_score(analysis)

    return analysis


@function_tool(strict_mode=False)
async def scrape_for_seo(
    url: str,
    include_subpages: bool = False,
    max_subpages: int = 5,
) -> dict[str, Any]:
    """
    Scrape a website for comprehensive SEO analysis.

    Performs enhanced analysis including technical SEO checks (robots.txt,
    sitemap, SSL, redirect chains, TTFB), mobile-friendliness, content
    quality, and calculates a rigorous 6-category SEO score (v2).

    Args:
        url: The URL to scrape.
        include_subpages: If True, also analyze internal subpages (default False).
        max_subpages: Maximum number of subpages to analyze (default 5).

    Returns:
        Dictionary with detailed SEO analysis including:
        - meta_tags: title, description, keywords, robots, canonical, og_data
        - headings: H1-H6 hierarchy with counts
        - images: alt text analysis
        - links: internal/external link analysis
        - schema_markup: JSON-LD structured data
        - url_analysis: SEO-friendliness score
        - content_metrics: word count, keyword density
        - technical_seo: robots.txt, sitemap, SSL, redirect, TTFB results
        - mobile_analysis: viewport, responsive, media queries
        - content_quality: depth, readability, keyword placement
        - score_breakdown: 6-category scoring with per-category details
        - seo_score: Overall score (0-100, v2 algorithm)
        - geo_analysis: GEO readiness analysis (AI crawler access, content structure, citation density, AI discovery)
        - subpages: Analysis of subpages (if include_subpages=True)
    """
    try:
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme:
            url = f"https://{url}"
            parsed = urlparse(url)

        if not parsed.netloc:
            return {
                "success": False,
                "error": "Invalid URL provided",
                "url": url,
            }

        # 1. Enhanced fetch (TTFB + redirect + headers)
        fetch_result = await _fetch_page_enhanced(url)

        if not fetch_result["success"] or not fetch_result["html"]:
            return {
                "success": False,
                "error": fetch_result.get("error", "Failed to fetch page"),
                "url": url,
            }

        html = fetch_result["html"]
        final_url = fetch_result["final_url"] or url

        # 2. Run async technical checks in parallel (including GEO llms.txt)
        robots_task = _check_robots_txt(url)
        ssl_task = _check_ssl_security(url)
        llms_task = _check_llms_txt(url)

        robots_result, ssl_result, llms_result = await asyncio.gather(
            robots_task, ssl_task, llms_task,
        )

        # Sitemap depends on robots.txt sitemaps
        sitemap_result = await _check_sitemap(url, robots_result.get("sitemap_urls"))

        # 3. Optional: mobile TTFB
        mobile_fetch = await _fetch_page_enhanced(url, mobile=True)
        mobile_ttfb = mobile_fetch.get("ttfb_ms", 0)

        # 4. Build enhanced_data for _analyze_single_page_seo
        enhanced_data = {
            "robots_txt": robots_result,
            "sitemap": sitemap_result,
            "ssl_security": ssl_result,
            "llms_txt": llms_result,
            "response_headers": fetch_result["response_headers"],
            "ttfb_ms": fetch_result["ttfb_ms"],
            "redirect_count": fetch_result["redirect_count"],
            "redirect_chain": fetch_result["redirect_chain"],
            "mobile_ttfb_ms": mobile_ttfb,
        }

        # 5. Analyze main page with enhanced data (v2 scoring)
        main_analysis = _analyze_single_page_seo(
            html, final_url, enhanced_data=enhanced_data,
        )

        # 6. Build result with new top-level fields for easy access
        result: dict[str, Any] = {
            "success": True,
            **main_analysis,
            # Expose technical data at top level for agent convenience
            "technical_seo": {
                "robots_txt": robots_result,
                "sitemap": sitemap_result,
                "ssl": ssl_result,
                "ttfb_ms": fetch_result["ttfb_ms"],
                "redirect_count": fetch_result["redirect_count"],
                "redirect_chain": fetch_result["redirect_chain"],
                "response_headers": fetch_result["response_headers"],
            },
        }

        # 7. Analyze subpages if requested
        if include_subpages and max_subpages > 0:
            internal_links = main_analysis.get("links", {}).get("internal_link_urls", [])

            # Filter to unique, meaningful subpages
            base_domain = parsed.netloc.lower()
            subpage_urls = []
            seen_paths = {parsed.path}

            for link in internal_links:
                link_parsed = urlparse(link)
                if link_parsed.netloc.lower() == base_domain:
                    path = link_parsed.path
                    if (path not in seen_paths and
                        not any(path.endswith(ext) for ext in ['.jpg', '.png', '.gif', '.pdf', '.css', '.js']) and
                        not any(skip in path.lower() for skip in ['/wp-admin', '/login', '/cart', '/checkout', '/tag/', '/page/'])):
                        seen_paths.add(path)
                        subpage_urls.append(link)
                        if len(subpage_urls) >= max_subpages:
                            break

            subpages = []
            for subpage_url in subpage_urls:
                sub_html, sub_final_url = await _fetch_page(subpage_url)
                if sub_html:
                    sub_analysis = _analyze_single_page_seo(sub_html, sub_final_url or subpage_url)
                    subpages.append({
                        "url": sub_analysis["url"],
                        "seo_score": sub_analysis["seo_score"],
                        "meta_tags": sub_analysis["meta_tags"],
                        "headings": {
                            "h1": sub_analysis["headings"]["h1"],
                            "h1_count": sub_analysis["headings"]["h1_count"],
                        },
                        "word_count": sub_analysis["word_count"],
                        "keyword_density": sub_analysis["keyword_density"],
                    })

            result["subpages"] = subpages
            result["subpages_analyzed"] = len(subpages)

            if subpages:
                all_scores = [main_analysis["seo_score"]] + [sp["seo_score"] for sp in subpages]
                result["average_seo_score"] = round(sum(all_scores) / len(all_scores))

        return result

    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timeout - website took too long to respond",
            "url": url,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url": url,
        }


@function_tool(strict_mode=False)
async def scrape_competitors(
    urls: list[str] | None = None,
    max_concurrent: int = 5,
) -> dict[str, Any]:
    """
    Scrape multiple competitor websites for SEO analysis in a single call.

    This is more efficient than calling scrape_for_seo multiple times.
    Scrapes all URLs concurrently and returns aggregated results.

    IMPORTANT: The 'urls' parameter is REQUIRED. You MUST provide at least one URL.

    Args:
        urls: REQUIRED - List of competitor URLs to scrape (max 15).
            Example: urls=["https://competitor1.com", "https://competitor2.com"]
        max_concurrent: Maximum concurrent requests (default 5, max 10).

    Returns:
        Dictionary with:
        - results: List of successful scrape results
        - failed: List of URLs that failed
        - common_keywords: Keywords found across multiple sites
        - avg_seo_score: Average SEO score of all competitors
        - schema_types_used: Schema types used by competitors
    """
    import asyncio

    if urls is None or not isinstance(urls, list) or len(urls) < 1:
        return {
            "success": False,
            "error": "REQUIRED PARAMETER MISSING: 'urls' must be a list with at least 1 URL. "
                     "Example: urls=[\"https://competitor1.com\", \"https://competitor2.com\"]",
        }

    # Limit URLs and concurrency
    urls = urls[:15]
    max_concurrent = min(max(1, max_concurrent), 10)

    async def scrape_single(url: str) -> dict[str, Any]:
        """Scrape a single competitor."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = f"https://{url}"

            html, final_url = await _fetch_page(url)
            if not html:
                return {"url": url, "success": False, "error": "Failed to fetch"}

            analysis = _analyze_single_page_seo(html, final_url or url)

            # Lightweight mobile/content checks for competitors
            comp_soup = BeautifulSoup(html, "html.parser")
            viewport_tag = comp_soup.find("meta", attrs={"name": "viewport"})
            mobile_viewport = viewport_tag is not None

            wc = analysis.get("word_count", 0)
            if wc < 300:
                content_depth = "thin"
            elif wc < 1000:
                content_depth = "normal"
            else:
                content_depth = "comprehensive"

            return {
                "url": final_url or url,
                "success": True,
                "domain": urlparse(final_url or url).netloc,
                "seo_score": analysis.get("seo_score", 0),
                "title": analysis.get("meta_tags", {}).get("title"),
                "description": analysis.get("meta_tags", {}).get("description"),
                "h1": analysis.get("headings", {}).get("h1", []),
                "word_count": analysis.get("word_count", 0),
                "keyword_density": analysis.get("keyword_density", {}),
                "schema_types": analysis.get("schema_markup", {}).get("schema_types", []),
                "has_schema": analysis.get("schema_markup", {}).get("has_schema", False),
                "mobile_viewport": mobile_viewport,
                "content_depth": content_depth,
            }
        except Exception as e:
            return {"url": url, "success": False, "error": str(e)}

    # Scrape with concurrency limit
    semaphore = asyncio.Semaphore(max_concurrent)

    async def limited_scrape(url: str) -> dict[str, Any]:
        async with semaphore:
            return await scrape_single(url)

    # Run all scrapes concurrently
    tasks = [limited_scrape(url) for url in urls]
    all_results = await asyncio.gather(*tasks)

    # Separate successful and failed
    successful = [r for r in all_results if r.get("success")]
    failed = [{"url": r["url"], "error": r.get("error")} for r in all_results if not r.get("success")]

    # Aggregate common keywords
    from collections import Counter
    all_keywords: Counter[str] = Counter()
    for result in successful:
        kd = result.get("keyword_density", {})
        for keyword in kd.keys():
            all_keywords[keyword] += 1

    # Keywords appearing in 2+ sites
    common_keywords = [kw for kw, count in all_keywords.most_common(30) if count >= 2]

    # Collect schema types
    all_schema_types = set()
    for result in successful:
        all_schema_types.update(result.get("schema_types", []))

    # Calculate average SEO score
    scores = [r.get("seo_score", 0) for r in successful if r.get("seo_score")]
    avg_score = round(sum(scores) / len(scores)) if scores else 0

    return {
        "success": True,
        "total_urls": len(urls),
        "successful_count": len(successful),
        "failed_count": len(failed),
        "results": successful,
        "failed": failed,
        "common_keywords": common_keywords,
        "avg_seo_score": avg_score,
        "schema_types_used": list(all_schema_types),
    }


@function_tool(strict_mode=False)
async def check_serp_position(
    domain: str,
    keywords: list[str] | None = None,
    num_results: int = 10,
) -> dict[str, Any]:
    """
    Check real Google search visibility for a domain across keywords.

    Searches Google (via Serper.dev) for each keyword and checks if the domain
    appears in the top results.  This is the ultimate validation of SEO
    effectiveness: a site can have perfect on-page SEO but still be invisible
    in search.

    IMPORTANT: The 'keywords' parameter is REQUIRED. Provide 5-10 keywords.

    Args:
        domain: The domain to check (e.g., "example.com"). Do NOT include protocol.
        keywords: REQUIRED - List of keywords to check (max 10).
            Example: keywords=["istanbul pastane", "butik pasta", "doğum günü pastası"]
        num_results: Number of search results to check per keyword (default 10, max 20).

    Returns:
        Dictionary with:
        - results: Per-keyword position data
        - visibility_score: 0-100 overall search visibility
        - found_count: How many keywords the domain was found for
        - not_found_keywords: Keywords where domain was NOT in results
    """
    settings = get_settings()
    if not settings.serper_api_key:
        return {
            "success": False,
            "error": "SERPER_API_KEY not configured",
        }

    if not keywords or not isinstance(keywords, list) or len(keywords) < 1:
        return {
            "success": False,
            "error": "REQUIRED PARAMETER MISSING: 'keywords' must be a list with at least 1 keyword. "
                     "Example: keywords=[\"istanbul pastane\", \"butik pasta\"]",
        }

    # Normalize domain
    domain = domain.lower().replace("https://", "").replace("http://", "").strip("/")
    keywords = keywords[:10]
    num_results = min(max(5, num_results), 20)

    results = []
    found_count = 0
    not_found_keywords = []

    for i, keyword in enumerate(keywords):
        # Rate limit: 0.3s between searches (Serper supports 300 req/s)
        if i > 0:
            await asyncio.sleep(0.3)

        kw_result: dict[str, Any] = {
            "keyword": keyword,
            "position": None,
            "found": False,
            "found_url": None,
            "top_results": [],
        }

        try:
            data = await _serper_search(keyword, num=num_results)

            for pos, r in enumerate(data.get("organic", []), 1):
                result_url = r.get("link", "")
                result_domain = urlparse(result_url).netloc.lower()

                kw_result["top_results"].append({
                    "position": pos,
                    "domain": result_domain,
                    "title": r.get("title", ""),
                })

                # Check if our domain matches
                if not kw_result["found"] and (
                    domain in result_domain or result_domain.endswith("." + domain)
                ):
                    kw_result["position"] = pos
                    kw_result["found"] = True
                    kw_result["found_url"] = result_url
                    found_count += 1

        except Exception as e:
            kw_result["error"] = str(e)

        if not kw_result["found"]:
            not_found_keywords.append(keyword)

        # Only keep top 5 results to reduce response size
        kw_result["top_results"] = kw_result["top_results"][:5]
        results.append(kw_result)

    # Calculate visibility score (0-100)
    # Position 1 = 100 points, position 2 = 90, ... position 10 = 10, not found = 0
    total_points = 0
    max_points = len(keywords) * 100
    for r in results:
        if r["found"] and r["position"]:
            pos = r["position"]
            # Scoring: pos 1 → 100, pos 2 → 90, ..., pos 10 → 10
            points = max(0, (num_results + 1 - pos) * (100 // num_results))
            total_points += points

    visibility_score = round(total_points / max_points * 100) if max_points > 0 else 0

    return {
        "success": True,
        "domain": domain,
        "keywords_checked": len(keywords),
        "found_count": found_count,
        "not_found_count": len(not_found_keywords),
        "not_found_keywords": not_found_keywords,
        "visibility_score": visibility_score,
        "results": results,
    }


def get_seo_tools() -> list:
    """Return SEO-related tools for the Analysis Agent."""
    return [web_search, scrape_for_seo, scrape_competitors, check_serp_position]


__all__ = [
    "web_search", "scrape_website", "scrape_for_seo",
    "scrape_competitors", "check_serp_position", "get_seo_tools",
]
