"""
Investigator Node — Researches unknown vendors and categorizes them.

If the Scribe node flags `needs_research`, this node executes a web search
to determine what the vendor is, and then uses the LLM to update the
transaction category appropriately.
"""

import logging
from typing import Any, Dict

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from pulse.config import settings
from pulse.tools.search import get_search_provider, SearchQueryInput

logger = logging.getLogger(__name__)

# LLM singleton for Investigator
_llm = None

def _get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        _llm = ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL_NAME,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.0,
            max_retries=1,
        )
    return _llm


_INVESTIGATOR_SYSTEM_PROMPT = """You are a financial investigator.
A user has submitted an expense for a vendor they visited, but the category is unknown.
I will provide you with the vendor name, the current guessed category, and search results from the web about this vendor.

Based on the search results, determine the MOST accurate category for this vendor.
Your response MUST be ONLY a single word from this exact list:
Food, Transport, Entertainment, Shopping, Bills, Health, Education, Sport, Groceries, Subscriptions, Travel, Gifts, Personal, Other

Do not explain. Just output the single category name.
"""

async def investigator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Research an unknown vendor and update the transaction category.
    """
    parsed = state.get("parsed_transaction")
    
    if not parsed or not parsed.needs_research:
        # If it somehow got here without needing research, just pass it through
        return state

    vendor = parsed.vendor
    current_category = parsed.category
    logger.info("Investigator researching vendor: %s", vendor)

    try:
        # 1. Search the web
        provider = get_search_provider(settings.SEARCH_PROVIDER)
        query = SearchQueryInput(query=f"What company or service is '{vendor}'?", max_results=3)
        results = await provider.search(query)

        # Build context from results
        if not results:
            context = "No search results found."
        else:
            context = "\n".join([f"- {r['title']}: {r['snippet']}" for r in results])

        # 2. Ask LLM to categorize based on research
        human_msg = f"Vendor: {vendor}\nCurrent Guess: {current_category}\n\nSearch Results:\n{context}"
        
        messages = [
            SystemMessage(content=_INVESTIGATOR_SYSTEM_PROMPT),
            HumanMessage(content=human_msg)
        ]
        
        llm_response = await _get_llm().ainvoke(messages)
        new_category = llm_response.content.strip()

        # Simple validation
        valid_categories = {"Food", "Transport", "Entertainment", "Shopping", "Bills", "Health", "Education", "Sport", "Groceries", "Subscriptions", "Travel", "Gifts", "Personal", "Other"}
        if new_category not in valid_categories:
            logger.warning("Investigator hallucinated category: %s. Defaulting to Other.", new_category)
            new_category = "Other"

        logger.info("Investigator changed category from %s to %s for %s", current_category, new_category, vendor)

        # 3. Update the state
        parsed.category = new_category
        parsed.needs_research = False # Research complete
        state["vendor_info"] = context # Save the research info
        
        return {
            "parsed_transaction": parsed,
            "vendor_info": context
        }

    except Exception as e:
        logger.error("Investigator error: %s", e, exc_info=True)
        # On error, we just fall back to whatever the Scribe originally guessed
        parsed.needs_research = False
        return {
            "parsed_transaction": parsed,
            "vendor_info": f"Research failed: {str(e)}"
        }
