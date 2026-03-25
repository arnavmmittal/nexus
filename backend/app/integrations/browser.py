"""Browser automation tools using Playwright.

Provides tools for:
- Web scraping
- Form filling
- Taking screenshots
- Automated browsing
"""

import json
import logging
import os
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Check if playwright is available
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Run: pip install playwright && playwright install")


_browser_instance = None
_page_instance = None


async def get_browser():
    """Get or create browser instance."""
    global _browser_instance
    if not PLAYWRIGHT_AVAILABLE:
        return None
    if _browser_instance is None:
        playwright = await async_playwright().start()
        _browser_instance = await playwright.chromium.launch(headless=True)
    return _browser_instance


async def browse_url(url: str, extract_text: bool = True) -> str:
    """Browse a URL and extract content."""
    logger.info(f"Browsing: {url}")
    
    if not PLAYWRIGHT_AVAILABLE:
        # Fallback to simple HTTP request
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        # Basic text extraction
                        import re
                        text = re.sub(r'<[^>]+>', ' ', html)
                        text = re.sub(r'\s+', ' ', text).strip()[:5000]
                        return json.dumps({
                            "url": url,
                            "status": "success",
                            "content": text,
                            "method": "http_fallback"
                        }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e), "url": url})
    
    try:
        browser = await get_browser()
        page = await browser.new_page()
        await page.goto(url, timeout=30000)
        
        if extract_text:
            content = await page.inner_text("body")
        else:
            content = await page.content()
        
        title = await page.title()
        
        await page.close()
        
        return json.dumps({
            "url": url,
            "title": title,
            "content": content[:5000],  # Limit content size
            "status": "success",
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Browse error: {e}")
        return json.dumps({"error": str(e), "url": url})


async def screenshot_webpage(url: str, filename: str = "") -> str:
    """Take a screenshot of a webpage."""
    logger.info(f"Screenshot: {url}")
    
    if not PLAYWRIGHT_AVAILABLE:
        return json.dumps({
            "error": "Playwright not installed",
            "install": "pip install playwright && playwright install"
        })
    
    try:
        browser = await get_browser()
        page = await browser.new_page()
        await page.goto(url, timeout=30000)
        
        if not filename:
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        filepath = os.path.join("/tmp", filename)
        await page.screenshot(path=filepath, full_page=True)
        
        await page.close()
        
        return json.dumps({
            "url": url,
            "screenshot": filepath,
            "status": "success",
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        return json.dumps({"error": str(e), "url": url})


async def fill_form(
    url: str,
    form_data: Dict[str, str],
    submit_selector: str = "",
) -> str:
    """Fill out a web form."""
    logger.info(f"Filling form on: {url}")
    
    if not PLAYWRIGHT_AVAILABLE:
        return json.dumps({
            "error": "Playwright not installed",
            "install": "pip install playwright && playwright install"
        })
    
    try:
        browser = await get_browser()
        page = await browser.new_page()
        await page.goto(url, timeout=30000)
        
        # Fill each field
        for selector, value in form_data.items():
            await page.fill(selector, value)
        
        # Submit if selector provided
        if submit_selector:
            await page.click(submit_selector)
            await page.wait_for_load_state("networkidle")
        
        result_url = page.url
        await page.close()
        
        return json.dumps({
            "url": url,
            "result_url": result_url,
            "fields_filled": list(form_data.keys()),
            "status": "success",
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Form fill error: {e}")
        return json.dumps({"error": str(e), "url": url})


async def scrape_job_listing(url: str) -> str:
    """Scrape a job listing page for details."""
    logger.info(f"Scraping job: {url}")
    
    import aiohttp
    import re
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    
                    # Extract text
                    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
                    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                    text = re.sub(r'<[^>]+>', '\n', text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    
                    return json.dumps({
                        "url": url,
                        "content": text[:8000],
                        "status": "success",
                    }, indent=2)
                    
    except Exception as e:
        return json.dumps({"error": str(e), "url": url})


async def web_search_detailed(
    query: str,
    num_results: int = 5,
) -> str:
    """Perform a detailed web search."""
    logger.info(f"Web search: {query}")
    
    import aiohttp
    
    try:
        # Use DuckDuckGo HTML search
        url = f"https://html.duckduckgo.com/html/?q={query}"
        
        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": "Mozilla/5.0"}
            async with session.get(url, headers=headers, timeout=30) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    
                    # Parse results (basic extraction)
                    import re
                    results = []
                    
                    # Find result links
                    links = re.findall(r'href="(https?://[^"]+)"[^>]*>([^<]+)', html)
                    for link, title in links[:num_results]:
                        if "duckduckgo" not in link:
                            results.append({
                                "title": title.strip(),
                                "url": link,
                            })
                    
                    return json.dumps({
                        "query": query,
                        "results": results,
                        "total": len(results),
                    }, indent=2)
                    
    except Exception as e:
        return json.dumps({"error": str(e), "query": query})


BROWSER_TOOLS = [
    {
        "name": "browse_url",
        "description": "Browse a URL and extract its content. Use for reading web pages, articles, job postings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to browse"
                },
                "extract_text": {
                    "type": "boolean",
                    "description": "Extract text only (vs full HTML)"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "screenshot_webpage",
        "description": "Take a screenshot of a webpage using browser automation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to screenshot"
                },
                "filename": {
                    "type": "string",
                    "description": "Output filename"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "fill_web_form",
        "description": "Fill out a web form automatically. Can be used for job applications.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the form"
                },
                "form_data": {
                    "type": "object",
                    "description": "Form fields as CSS selector -> value pairs"
                },
                "submit_selector": {
                    "type": "string",
                    "description": "CSS selector for submit button"
                }
            },
            "required": ["url", "form_data"]
        }
    },
    {
        "name": "scrape_job_listing",
        "description": "Scrape a job listing page to extract job details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Job listing URL"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "web_search_detailed",
        "description": "Perform a detailed web search with multiple results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return"
                }
            },
            "required": ["query"]
        }
    },
]
