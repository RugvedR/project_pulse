"""
Search Provider Tools — MCP-compatible web search implementations.

These tools allow the LangGraph Investigator Node to securely access
the internet to resolve unknown vendors.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── Pydantic Schemas (MCP Compatible) ──────────────────────────────────
class SearchQueryInput(BaseModel):
    """Input schema for searching the web."""
    query: str = Field(..., description="The query string to search for on the internet.")
    max_results: int = Field(3, description="Maximum number of search results to return.")


# ── Provider Interface ────────────────────────────────────────────────
class BaseSearchProvider(ABC):
    """Abstract base class for all search providers."""
    
    @abstractmethod
    async def search(self, input_data: SearchQueryInput) -> List[Dict[str, str]]:
        """
        Executes a web search.
        
        Returns:
            A list of dicts, typically containing 'title', 'snippet', and 'link'.
        """
        pass


# ── DuckDuckGo Implementation ──────────────────────────────────────────
class DuckDuckGoSearchProvider(BaseSearchProvider):
    """Free search provider using duckduckgo-search."""
    
    async def search(self, input_data: SearchQueryInput) -> List[Dict[str, str]]:
        """Run the search asynchronously."""
        from ddgs import DDGS
        import asyncio

        # DuckDuckGo search is synchronous in its current library form,
        # so we run it in a thread pool to avoid blocking the async event loop.
        def _run_search():
            try:
                results = []
                with DDGS() as ddgs:
                    # using text() method
                    generator = ddgs.text(input_data.query, max_results=input_data.max_results)
                    for r in generator:
                        results.append({
                            "title": r.get("title", ""),
                            "snippet": r.get("body", ""),
                            "link": r.get("href", "")
                        })
                return results
            except Exception as e:
                import traceback
                traceback.print_exc()
                logger.error("DuckDuckGo search error: %s", e)
                return []

        # Run the blocking function in the default executor
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, _run_search)
        
        return results

# ── Factory ────────────────────────────────────────────────────────────
def get_search_provider(provider_name: str) -> BaseSearchProvider:
    """Factory to get the configured search provider."""
    if provider_name.lower() == "duckduckgo":
        return DuckDuckGoSearchProvider()
    
    # Ready for Phase 2 future extensions (Tavily, Serper, etc.)
    raise ValueError(f"Unsupported search provider: {provider_name}")
