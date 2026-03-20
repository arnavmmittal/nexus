"""Researcher module for web search, content fetching, and AI-powered research.

This module provides tools for:
- Web searching using DuckDuckGo
- Fetching and converting web pages to markdown
- Explaining concepts using Claude
- Multi-source research and report compilation
- Article summarization
- Comparing multiple options
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from anthropic import AsyncAnthropic
from bs4 import BeautifulSoup, Tag

try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    HTML2TEXT_AVAILABLE = False

from app.core.config import settings


# Constants
DEFAULT_TIMEOUT = 30.0
MAX_CONTENT_LENGTH = 100000  # Max chars to process from a page
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"


@dataclass
class ResearchResult:
    """Container for research results."""

    success: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    estimated_cost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "requires_confirmation": self.requires_confirmation,
            "estimated_cost": self.estimated_cost,
        }


# Tool definitions for Claude
RESEARCHER_TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web using DuckDuckGo. Returns a list of search results with titles, URLs, and snippets. Use this to find information, articles, documentation, or any web content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 10, max: 25)",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_webpage",
        "description": "Fetch a webpage and convert its content to clean markdown. Use this to read articles, documentation, or any web page content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL of the webpage to fetch"
                },
                "include_links": {
                    "type": "boolean",
                    "description": "Whether to include links in the markdown output (default: true)",
                    "default": True
                },
                "include_images": {
                    "type": "boolean",
                    "description": "Whether to include image references (default: false)",
                    "default": False
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "explain_concept",
        "description": "Generate a clear explanation of a concept using AI. This uses Claude to provide educational explanations. Cost: ~$0.01 per explanation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "concept": {
                    "type": "string",
                    "description": "The concept, topic, or question to explain"
                },
                "level": {
                    "type": "string",
                    "enum": ["beginner", "intermediate", "advanced", "expert"],
                    "description": "The complexity level of the explanation (default: intermediate)",
                    "default": "intermediate"
                },
                "context": {
                    "type": "string",
                    "description": "Optional context or specific angle to focus the explanation"
                }
            },
            "required": ["concept"]
        }
    },
    {
        "name": "research_topic",
        "description": "Conduct comprehensive research on a topic using multiple sources. Searches the web, fetches relevant pages, and compiles a research report. Cost: ~$0.05 per research (includes AI summarization).",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic to research"
                },
                "depth": {
                    "type": "string",
                    "enum": ["quick", "standard", "deep"],
                    "description": "Research depth - quick (3 sources), standard (5 sources), deep (10 sources)",
                    "default": "standard"
                },
                "focus_areas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional specific areas to focus on within the topic"
                }
            },
            "required": ["topic"]
        }
    },
    {
        "name": "summarize_article",
        "description": "Summarize an article from a URL or provided text. Uses AI to generate a concise summary. Cost: ~$0.01 per summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the article to summarize (provide this OR text)"
                },
                "text": {
                    "type": "string",
                    "description": "Text content to summarize (provide this OR url)"
                },
                "style": {
                    "type": "string",
                    "enum": ["brief", "detailed", "bullet_points", "key_takeaways"],
                    "description": "Summary style (default: brief)",
                    "default": "brief"
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum length of summary in words (default: 200)",
                    "default": 200
                }
            },
            "required": []
        }
    },
    {
        "name": "compare_options",
        "description": "Research and compare multiple options (products, technologies, approaches, etc.). Gathers information on each option and provides a comparison. Cost: ~$0.03-0.10 depending on number of options.",
        "input_schema": {
            "type": "object",
            "properties": {
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of options to compare (2-5 options)"
                },
                "criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific criteria to compare on (optional)"
                },
                "context": {
                    "type": "string",
                    "description": "Context for the comparison (e.g., 'for a small startup', 'for mobile development')"
                }
            },
            "required": ["options"]
        }
    },
]


class ResearcherTools:
    """Tools for web research, content fetching, and AI-powered analysis."""

    def __init__(self, anthropic_client: Optional[AsyncAnthropic] = None):
        """
        Initialize researcher tools.

        Args:
            anthropic_client: Optional Anthropic client for AI-powered features.
                            If not provided, will create one using settings.
        """
        self._client: Optional[AsyncAnthropic] = anthropic_client
        self._http_client: Optional[httpx.AsyncClient] = None
        self._html_converter: Optional[Any] = None

    @property
    def client(self) -> AsyncAnthropic:
        """Get or create the Anthropic client."""
        if self._client is None:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            )
        return self._http_client

    @property
    def html_converter(self) -> Any:
        """Get or create the HTML to markdown converter."""
        if self._html_converter is None and HTML2TEXT_AVAILABLE:
            self._html_converter = html2text.HTML2Text()
            self._html_converter.ignore_links = False
            self._html_converter.ignore_images = True
            self._html_converter.ignore_emphasis = False
            self._html_converter.body_width = 0  # No wrapping
        return self._html_converter

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self) -> "ResearcherTools":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

    # ============ WEB SEARCH ============

    async def web_search(
        self,
        query: str,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """
        Search the web using DuckDuckGo HTML search.

        Args:
            query: Search query string
            max_results: Maximum number of results (1-25)

        Returns:
            Dict with success, message, and search results data
        """
        try:
            max_results = min(max(1, max_results), 25)

            # Prepare the search request
            form_data = {"q": query}

            response = await self.http_client.post(
                DUCKDUCKGO_URL,
                data=form_data,
            )
            response.raise_for_status()

            # Parse the HTML response
            soup = BeautifulSoup(response.text, "html.parser")

            results: List[Dict[str, str]] = []

            # DuckDuckGo HTML results are in .result class elements
            for result in soup.select(".result"):
                if len(results) >= max_results:
                    break

                # Extract title and URL
                title_elem = result.select_one(".result__title a")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                url = title_elem.get("href", "")

                # DuckDuckGo wraps URLs, need to extract the actual URL
                if url and "uddg=" in url:
                    # Extract the actual URL from the redirect
                    import urllib.parse
                    parsed = urllib.parse.urlparse(url)
                    params = urllib.parse.parse_qs(parsed.query)
                    if "uddg" in params:
                        url = urllib.parse.unquote(params["uddg"][0])

                # Extract snippet
                snippet_elem = result.select_one(".result__snippet")
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                if title and url:
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                    })

            return ResearchResult(
                success=True,
                message=f"Found {len(results)} results for '{query}'",
                data={
                    "query": query,
                    "results": results,
                    "result_count": len(results),
                },
                requires_confirmation=False,
                estimated_cost=0.0,
            ).to_dict()

        except httpx.TimeoutException:
            return ResearchResult(
                success=False,
                message="Search request timed out. Please try again.",
                data={"query": query},
            ).to_dict()
        except httpx.HTTPStatusError as e:
            return ResearchResult(
                success=False,
                message=f"Search request failed: HTTP {e.response.status_code}",
                data={"query": query},
            ).to_dict()
        except Exception as e:
            return ResearchResult(
                success=False,
                message=f"Search failed: {str(e)}",
                data={"query": query},
            ).to_dict()

    # ============ FETCH WEBPAGE ============

    async def fetch_webpage(
        self,
        url: str,
        include_links: bool = True,
        include_images: bool = False,
    ) -> Dict[str, Any]:
        """
        Fetch a webpage and convert to markdown.

        Args:
            url: URL to fetch
            include_links: Whether to include hyperlinks in output
            include_images: Whether to include image references

        Returns:
            Dict with success, message, and page content
        """
        try:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme in ("http", "https"):
                return ResearchResult(
                    success=False,
                    message="Invalid URL scheme. Only HTTP/HTTPS are supported.",
                    data={"url": url},
                ).to_dict()

            response = await self.http_client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type.lower() and "text/plain" not in content_type.lower():
                return ResearchResult(
                    success=False,
                    message=f"Unsupported content type: {content_type}",
                    data={"url": url, "content_type": content_type},
                ).to_dict()

            html_content = response.text

            # Parse and clean HTML
            soup = BeautifulSoup(html_content, "html.parser")

            # Remove script, style, and other non-content elements
            for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
                element.decompose()

            # Extract title
            title = ""
            title_elem = soup.find("title")
            if title_elem:
                title = title_elem.get_text(strip=True)

            # Extract main content
            # Try to find main content areas
            main_content = None
            for selector in ["main", "article", "[role='main']", ".content", "#content", ".post", ".article"]:
                main_content = soup.select_one(selector)
                if main_content:
                    break

            if main_content is None:
                main_content = soup.body if soup.body else soup

            # Convert to markdown
            if HTML2TEXT_AVAILABLE and self.html_converter:
                converter = html2text.HTML2Text()
                converter.ignore_links = not include_links
                converter.ignore_images = not include_images
                converter.body_width = 0
                markdown_content = converter.handle(str(main_content))
            else:
                # Fallback: extract text only
                markdown_content = main_content.get_text(separator="\n\n", strip=True)

            # Truncate if too long
            if len(markdown_content) > MAX_CONTENT_LENGTH:
                markdown_content = markdown_content[:MAX_CONTENT_LENGTH] + "\n\n[Content truncated...]"

            # Clean up excessive whitespace
            markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)
            markdown_content = markdown_content.strip()

            return ResearchResult(
                success=True,
                message=f"Successfully fetched: {title or url}",
                data={
                    "url": url,
                    "title": title,
                    "content": markdown_content,
                    "content_length": len(markdown_content),
                },
                requires_confirmation=False,
                estimated_cost=0.0,
            ).to_dict()

        except httpx.TimeoutException:
            return ResearchResult(
                success=False,
                message="Request timed out while fetching the webpage.",
                data={"url": url},
            ).to_dict()
        except httpx.HTTPStatusError as e:
            return ResearchResult(
                success=False,
                message=f"Failed to fetch webpage: HTTP {e.response.status_code}",
                data={"url": url},
            ).to_dict()
        except Exception as e:
            return ResearchResult(
                success=False,
                message=f"Failed to fetch webpage: {str(e)}",
                data={"url": url},
            ).to_dict()

    # ============ EXPLAIN CONCEPT ============

    async def explain_concept(
        self,
        concept: str,
        level: str = "intermediate",
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate an explanation of a concept using Claude.

        Args:
            concept: The concept to explain
            level: Complexity level (beginner, intermediate, advanced, expert)
            context: Optional context to focus the explanation

        Returns:
            Dict with success, message, and explanation
        """
        try:
            level_prompts = {
                "beginner": "Explain this to someone completely new to the topic. Use simple language, avoid jargon, and use relatable analogies.",
                "intermediate": "Explain this to someone with some background knowledge. Include relevant technical terms but explain them clearly.",
                "advanced": "Explain this to someone with solid knowledge of the field. Use appropriate technical terminology and discuss nuances.",
                "expert": "Explain this at an expert level. Include technical depth, edge cases, and advanced considerations.",
            }

            level_instruction = level_prompts.get(level, level_prompts["intermediate"])

            prompt = f"""Please explain the following concept:

**Concept:** {concept}

**Level:** {level}
{f"**Context:** {context}" if context else ""}

{level_instruction}

Provide a clear, well-structured explanation. Use markdown formatting for clarity."""

            response = await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            explanation = response.content[0].text if response.content else ""

            # Estimate cost (Haiku: $0.25/1M input, $1.25/1M output)
            input_tokens = response.usage.input_tokens if response.usage else 0
            output_tokens = response.usage.output_tokens if response.usage else 0
            estimated_cost = (input_tokens * 0.25 / 1_000_000) + (output_tokens * 1.25 / 1_000_000)

            return ResearchResult(
                success=True,
                message=f"Generated explanation for: {concept}",
                data={
                    "concept": concept,
                    "level": level,
                    "explanation": explanation,
                    "tokens_used": input_tokens + output_tokens,
                },
                requires_confirmation=True,  # AI-generated content
                estimated_cost=estimated_cost,
            ).to_dict()

        except Exception as e:
            return ResearchResult(
                success=False,
                message=f"Failed to generate explanation: {str(e)}",
                data={"concept": concept},
            ).to_dict()

    # ============ RESEARCH TOPIC ============

    async def research_topic(
        self,
        topic: str,
        depth: str = "standard",
        focus_areas: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Conduct comprehensive research on a topic.

        Args:
            topic: The topic to research
            depth: Research depth (quick, standard, deep)
            focus_areas: Optional specific areas to focus on

        Returns:
            Dict with success, message, and research report
        """
        try:
            source_counts = {"quick": 3, "standard": 5, "deep": 10}
            num_sources = source_counts.get(depth, 5)

            # Build search query
            search_query = topic
            if focus_areas:
                search_query += " " + " ".join(focus_areas[:2])  # Add first 2 focus areas

            # Search for sources
            search_result = await self.web_search(search_query, max_results=num_sources * 2)

            if not search_result.get("success"):
                return ResearchResult(
                    success=False,
                    message="Failed to search for research sources.",
                    data={"topic": topic},
                ).to_dict()

            results = search_result.get("data", {}).get("results", [])

            # Fetch content from top sources
            sources_content: List[Dict[str, Any]] = []
            fetch_tasks = []

            for result in results[:num_sources]:
                url = result.get("url", "")
                if url:
                    fetch_tasks.append(self.fetch_webpage(url))

            fetched_pages = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            for i, page_result in enumerate(fetched_pages):
                if isinstance(page_result, Exception):
                    continue
                if isinstance(page_result, dict) and page_result.get("success"):
                    sources_content.append({
                        "title": page_result.get("data", {}).get("title", ""),
                        "url": page_result.get("data", {}).get("url", ""),
                        "content": page_result.get("data", {}).get("content", "")[:5000],  # Limit per source
                    })

            if not sources_content:
                return ResearchResult(
                    success=False,
                    message="Could not fetch any source content.",
                    data={"topic": topic, "search_results": results},
                ).to_dict()

            # Compile research report using AI
            sources_text = "\n\n---\n\n".join([
                f"**Source: {s['title']}**\nURL: {s['url']}\n\n{s['content'][:3000]}"
                for s in sources_content
            ])

            focus_instruction = ""
            if focus_areas:
                focus_instruction = f"\n\nFocus particularly on these aspects: {', '.join(focus_areas)}"

            prompt = f"""You are a research analyst. Based on the following sources, compile a comprehensive research report on: **{topic}**
{focus_instruction}

**SOURCES:**
{sources_text[:15000]}

**INSTRUCTIONS:**
1. Synthesize information from all sources
2. Identify key facts, findings, and insights
3. Note any conflicting information between sources
4. Organize the report with clear sections
5. Include citations to sources where appropriate
6. End with key takeaways

Format the report in markdown with clear headings and bullet points where appropriate."""

            response = await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )

            report = response.content[0].text if response.content else ""

            # Estimate cost
            input_tokens = response.usage.input_tokens if response.usage else 0
            output_tokens = response.usage.output_tokens if response.usage else 0
            estimated_cost = (input_tokens * 0.25 / 1_000_000) + (output_tokens * 1.25 / 1_000_000)

            return ResearchResult(
                success=True,
                message=f"Completed research on: {topic}",
                data={
                    "topic": topic,
                    "depth": depth,
                    "sources_used": len(sources_content),
                    "sources": [{"title": s["title"], "url": s["url"]} for s in sources_content],
                    "report": report,
                    "tokens_used": input_tokens + output_tokens,
                },
                requires_confirmation=True,
                estimated_cost=estimated_cost,
            ).to_dict()

        except Exception as e:
            return ResearchResult(
                success=False,
                message=f"Research failed: {str(e)}",
                data={"topic": topic},
            ).to_dict()

    # ============ SUMMARIZE ARTICLE ============

    async def summarize_article(
        self,
        url: Optional[str] = None,
        text: Optional[str] = None,
        style: str = "brief",
        max_length: int = 200,
    ) -> Dict[str, Any]:
        """
        Summarize an article from URL or text.

        Args:
            url: URL of article to summarize
            text: Text content to summarize
            style: Summary style (brief, detailed, bullet_points, key_takeaways)
            max_length: Maximum summary length in words

        Returns:
            Dict with success, message, and summary
        """
        try:
            if not url and not text:
                return ResearchResult(
                    success=False,
                    message="Please provide either a URL or text to summarize.",
                    data={},
                ).to_dict()

            # Fetch content if URL provided
            content = text
            title = "Provided Text"
            source_url = url

            if url:
                fetch_result = await self.fetch_webpage(url)
                if not fetch_result.get("success"):
                    return ResearchResult(
                        success=False,
                        message=f"Failed to fetch article: {fetch_result.get('message')}",
                        data={"url": url},
                    ).to_dict()
                content = fetch_result.get("data", {}).get("content", "")
                title = fetch_result.get("data", {}).get("title", "Article")

            if not content:
                return ResearchResult(
                    success=False,
                    message="No content to summarize.",
                    data={"url": url},
                ).to_dict()

            # Build style instructions
            style_instructions = {
                "brief": f"Provide a concise summary in {max_length} words or less.",
                "detailed": f"Provide a detailed summary covering all main points, in approximately {max_length * 2} words.",
                "bullet_points": f"Summarize the main points as a bullet list with {max_length // 20} to {max_length // 10} key points.",
                "key_takeaways": f"Extract the {max_length // 25} to {max_length // 15} most important takeaways from this content.",
            }

            style_instruction = style_instructions.get(style, style_instructions["brief"])

            prompt = f"""Summarize the following content:

**Title:** {title}

**Content:**
{content[:10000]}

**Instructions:**
{style_instruction}

Provide the summary in markdown format."""

            response = await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            summary = response.content[0].text if response.content else ""

            # Estimate cost
            input_tokens = response.usage.input_tokens if response.usage else 0
            output_tokens = response.usage.output_tokens if response.usage else 0
            estimated_cost = (input_tokens * 0.25 / 1_000_000) + (output_tokens * 1.25 / 1_000_000)

            return ResearchResult(
                success=True,
                message=f"Generated {style} summary",
                data={
                    "title": title,
                    "url": source_url,
                    "style": style,
                    "summary": summary,
                    "original_length": len(content),
                    "tokens_used": input_tokens + output_tokens,
                },
                requires_confirmation=True,
                estimated_cost=estimated_cost,
            ).to_dict()

        except Exception as e:
            return ResearchResult(
                success=False,
                message=f"Summarization failed: {str(e)}",
                data={"url": url},
            ).to_dict()

    # ============ COMPARE OPTIONS ============

    async def compare_options(
        self,
        options: List[str],
        criteria: Optional[List[str]] = None,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Research and compare multiple options.

        Args:
            options: List of options to compare (2-5)
            criteria: Specific criteria to compare on
            context: Context for the comparison

        Returns:
            Dict with success, message, and comparison data
        """
        try:
            if len(options) < 2:
                return ResearchResult(
                    success=False,
                    message="Please provide at least 2 options to compare.",
                    data={"options": options},
                ).to_dict()

            if len(options) > 5:
                options = options[:5]  # Limit to 5 options

            # Research each option
            option_research: List[Dict[str, Any]] = []

            for option in options:
                search_query = f"{option} overview features pros cons"
                if context:
                    search_query += f" {context}"

                search_result = await self.web_search(search_query, max_results=3)

                if search_result.get("success"):
                    results = search_result.get("data", {}).get("results", [])

                    # Fetch first result
                    content = ""
                    if results and results[0].get("url"):
                        fetch_result = await self.fetch_webpage(results[0]["url"])
                        if fetch_result.get("success"):
                            content = fetch_result.get("data", {}).get("content", "")[:3000]

                    option_research.append({
                        "option": option,
                        "snippets": [r.get("snippet", "") for r in results[:3]],
                        "content": content,
                    })
                else:
                    option_research.append({
                        "option": option,
                        "snippets": [],
                        "content": "",
                    })

            # Build comparison prompt
            research_text = "\n\n".join([
                f"**{r['option']}:**\n" +
                "\n".join([f"- {s}" for s in r['snippets']]) +
                (f"\n\nAdditional info:\n{r['content'][:2000]}" if r['content'] else "")
                for r in option_research
            ])

            criteria_text = ""
            if criteria:
                criteria_text = f"\n\n**Compare specifically on these criteria:** {', '.join(criteria)}"

            context_text = ""
            if context:
                context_text = f"\n\n**Context for comparison:** {context}"

            prompt = f"""Compare the following options and help make a decision:

**Options to compare:**
{', '.join(options)}
{criteria_text}
{context_text}

**Research gathered:**
{research_text}

**Instructions:**
1. Provide an overview of each option
2. Compare them on relevant criteria (use the provided criteria if given)
3. List pros and cons for each
4. Provide a recommendation based on the context (if provided) or general use case
5. Format as a clear, readable comparison

Use markdown formatting with tables where appropriate."""

            response = await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )

            comparison = response.content[0].text if response.content else ""

            # Estimate cost
            input_tokens = response.usage.input_tokens if response.usage else 0
            output_tokens = response.usage.output_tokens if response.usage else 0
            estimated_cost = (input_tokens * 0.25 / 1_000_000) + (output_tokens * 1.25 / 1_000_000)

            return ResearchResult(
                success=True,
                message=f"Compared {len(options)} options",
                data={
                    "options": options,
                    "criteria": criteria,
                    "context": context,
                    "comparison": comparison,
                    "sources_per_option": 3,
                    "tokens_used": input_tokens + output_tokens,
                },
                requires_confirmation=True,
                estimated_cost=estimated_cost,
            ).to_dict()

        except Exception as e:
            return ResearchResult(
                success=False,
                message=f"Comparison failed: {str(e)}",
                data={"options": options},
            ).to_dict()


class ResearcherExecutor:
    """Executor for researcher tools, following the same pattern as ToolExecutor."""

    def __init__(self, anthropic_client: Optional[AsyncAnthropic] = None):
        """
        Initialize the researcher executor.

        Args:
            anthropic_client: Optional Anthropic client for AI features
        """
        self.tools = ResearcherTools(anthropic_client)

    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """
        Execute a researcher tool and return the result as a string.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool

        Returns:
            JSON string of the result
        """
        try:
            method = getattr(self.tools, tool_name, None)
            if method is None:
                return json.dumps({
                    "success": False,
                    "message": f"Unknown researcher tool: '{tool_name}'",
                    "data": {},
                })
            result = await method(**tool_input)
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({
                "success": False,
                "message": f"Error executing {tool_name}: {str(e)}",
                "data": {},
            })

    async def close(self) -> None:
        """Clean up resources."""
        await self.tools.close()
