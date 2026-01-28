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


def get_web_tools() -> list:
    """Return list of web tools for the web agent."""
    from src.tools.analysis_tools import save_custom_report, get_reports
    return [web_search, scrape_website, update_business_profile, save_custom_report, get_reports]


@function_tool(strict_mode=False)
async def update_business_profile(
    business_id: str,
    profile_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Update business profile in Firebase with analyzed data.
    
    Saves the given profile data to businesses/{business_id} document's 'profile' field.
    The profile field is a map, so new fields will be merged with existing ones.
    
    Args:
        business_id: The business ID to update.
        profile_data: Dictionary containing profile fields to update. 
                      Common fields: slogan, industry, sub_category, market_position,
                      location_city, tone, brand_values, unique_points, 
                      brand_story_short, target_description, target_age_range, 
                      content_pillars, contact_info, social_links.
    
    Returns:
        Dictionary with success status and updated fields.
    """
    try:
        from src.infra.firebase_client import get_document_client
        
        if not business_id:
            return {
                "success": False,
                "error": "business_id is required",
            }
        
        if not profile_data or not isinstance(profile_data, dict):
            return {
                "success": False,
                "error": "profile_data must be a non-empty dictionary",
            }
        
        # Get document client for businesses collection
        doc_client = get_document_client("businesses")
        
        # Get current document to merge with existing profile
        current_doc = doc_client.get_document(business_id)
        if not current_doc:
            return {
                "success": False,
                "error": f"Business not found: {business_id}",
            }
        
        # Get existing profile or start fresh
        existing_profile = current_doc.get("profile", {})
        if not isinstance(existing_profile, dict):
            existing_profile = {}
        
        # Merge new data with existing profile
        updated_profile = {**existing_profile, **profile_data}
        
        # Update only the profile field using set_document with merge
        doc_client.set_document(business_id, {"profile": updated_profile}, merge=True)
        
        return {
            "success": True,
            "business_id": business_id,
            "updated_fields": list(profile_data.keys()),
            "message": f"Profile updated with {len(profile_data)} fields",
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


__all__ = ["web_search", "scrape_website", "update_business_profile", "get_web_tools"]
