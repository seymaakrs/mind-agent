"""
Web tools for web search and website scraping.

Tools:
- web_search: Search the web using DuckDuckGo
- scrape_website: Scrape a website for business analysis
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from agents import function_tool

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None


@function_tool
async def web_search(
    query: str,
    num_results: int = 5,
    search_type: str = "text",
) -> dict[str, Any]:
    """
    Search the web using DuckDuckGo.

    Args:
        query: Search query string.
        num_results: Number of results to return (default 5, max 10).
        search_type: Type of search - "text" (default) or "news" for recent news.

    Returns:
        Dictionary with search results including titles, URLs, and snippets.
    """
    if DDGS is None:
        return {
            "success": False,
            "error": "ddgs not installed. Run: pip install ddgs",
            "query": query,
            "results": [],
        }

    try:
        # Limit results
        num_results = min(num_results, 10)

        results = []

        with DDGS() as ddgs:
            if search_type == "news":
                # News search for recent articles
                search_results = ddgs.news(query, max_results=num_results)
            else:
                # Regular text search
                search_results = ddgs.text(query, max_results=num_results)

            for r in search_results:
                if search_type == "news":
                    results.append({
                        "url": r.get("url", ""),
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "date": r.get("date", ""),
                        "source": r.get("source", ""),
                    })
                else:
                    results.append({
                        "url": r.get("href", ""),
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
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
    """Fetch a single page and return (html_content, final_url)."""
    try:
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
            if response.status_code == 200:
                return response.text, str(response.url)
    except Exception:
        pass
    return None, None


def _analyze_single_page_seo(html: str, url: str) -> dict[str, Any]:
    """Analyze a single page for SEO factors."""
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
    robots = meta_robots.get("content") if meta_robots else None

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
        "robots": robots,
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

    # Extract content for analysis
    for element in soup(["script", "style", "nav", "header", "footer", "aside"]):
        element.decompose()
    main_text = soup.get_text(separator=" ", strip=True)
    main_text = re.sub(r'\s+', ' ', main_text)

    word_count = len(main_text.split())
    keyword_density = _calculate_keyword_density(main_text)

    analysis = {
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

    Extracts detailed SEO factors including meta tags, heading hierarchy,
    image alt texts, internal/external links, schema markup, and calculates
    an overall SEO score.

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
        - seo_score: Overall score (0-100)
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

        # Fetch main page
        html, final_url = await _fetch_page(url)

        if not html:
            return {
                "success": False,
                "error": "Failed to fetch page",
                "url": url,
            }

        # Analyze main page
        main_analysis = _analyze_single_page_seo(html, final_url or url)

        result = {
            "success": True,
            **main_analysis,
        }

        # Analyze subpages if requested
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
                    # Skip anchors, assets, common non-content pages
                    if (path not in seen_paths and
                        not any(path.endswith(ext) for ext in ['.jpg', '.png', '.gif', '.pdf', '.css', '.js']) and
                        not any(skip in path.lower() for skip in ['/wp-admin', '/login', '/cart', '/checkout', '/tag/', '/page/'])):
                        seen_paths.add(path)
                        subpage_urls.append(link)
                        if len(subpage_urls) >= max_subpages:
                            break

            # Analyze subpages
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

            # Calculate average score including subpages
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


def get_seo_tools() -> list:
    """Return SEO-related tools for the Analysis Agent."""
    return [web_search, scrape_for_seo, scrape_competitors]


__all__ = ["web_search", "scrape_website", "scrape_for_seo", "scrape_competitors", "get_seo_tools"]
