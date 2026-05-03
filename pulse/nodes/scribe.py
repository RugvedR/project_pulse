"""
Scribe Node — Entry point of the Pulse agent graph.

The Scribe receives raw natural-language text from the user and uses
the configured LLM (Gemini Flash) to extract structured transaction data.

Input:  `raw_input` (str) — the user's message
Output: `parsed_transaction` (TransactionInput | None)
        `response_to_user` (str) — error message if parsing fails
        `messages` — updated conversation history
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from pulse.config import settings
from pulse.llm import get_llm, extract_text
from pulse.schemas.transaction import TransactionInput

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System Prompt — instructs the LLM to extract structured expense data
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """You are a financial transaction parser. Your job is to extract
structured expense data from natural language input.

You MUST respond with ONLY a valid JSON object matching this schema:
{
    "amount": <positive number>,
    "currency": "INR",
    "vendor": "<vendor or merchant name>",
    "category": "<one of: Food, Transport, Entertainment, Shopping, Bills, Health, Education, Sport, Groceries, Subscriptions, Travel, Gifts, Personal, Other>",
    "notes": "<optional additional context or null>",
    "needs_research": <boolean>
}

Rules:
1. Amount must be a positive number. Extract it from context (e.g., "450" from "Spent 450").
2. If no currency is mentioned, default to "INR".
3. Vendor should be the merchant or establishment name. Clean it up (capitalize properly).
4. Category must be ONE of the listed categories. Choose the best fit.
5. If the vendor is an unrecognized company/brand, or the category is a guess, set "needs_research": true. Otherwise false.
6. If the input doesn't describe a financial transaction, respond with:
   {"error": "Not a valid transaction"}
7. Do NOT include any text outside the JSON object. No markdown, no explanation.
"""


# ---------------------------------------------------------------------------
# Node Function
# ---------------------------------------------------------------------------
async def scribe_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse raw user input into a structured TransactionInput.

    This node is the entry point of the graph. It takes the user's
    natural language message and uses the LLM to extract amount,
    vendor, category, and other structured fields.

    Args:
        state: Current AgentState dict.

    Returns:
        Partial state update with:
        - parsed_transaction: TransactionInput if parsing succeeded
        - response_to_user: error message if parsing failed
        - messages: updated conversation history
    """
    raw_input = state.get("raw_input", "")
    logger.info("Scribe processing: %s", raw_input[:100])

    try:
        # Build messages for the LLM
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=raw_input),
        ]

        # Call the LLM
        response = await get_llm(temperature=0.0).ainvoke(messages)
        response_text = extract_text(response).strip()

        logger.debug("LLM raw response: %s", response_text)

        # Clean up response — strip markdown code fences if present
        if response_text.startswith("```"):
            # Remove ```json ... ``` wrapper
            lines = response_text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            response_text = "\n".join(lines).strip()

        # Parse the JSON response
        parsed = json.loads(response_text)

        # Check for explicit error from LLM
        if "error" in parsed:
            logger.warning("LLM indicated non-transaction: %s", parsed["error"])
            return {
                "parsed_transaction": None,
                "response_to_user": f"I couldn't parse that as a transaction: {parsed['error']}",
                "messages": [
                    HumanMessage(content=raw_input),
                    response,
                ],
            }

        # Validate through Pydantic
        transaction = TransactionInput(**parsed)

        logger.info(
            "Scribe parsed: %s %s at %s [%s]",
            transaction.currency,
            transaction.amount,
            transaction.vendor,
            transaction.category,
        )

        return {
            "parsed_transaction": transaction,
            "response_to_user": "",
            "messages": [
                HumanMessage(content=raw_input),
                response,
            ],
        }

    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM JSON response: %s", e)
        return {
            "parsed_transaction": None,
            "response_to_user": "Sorry, I had trouble understanding that. Could you rephrase your expense?",
            "messages": [HumanMessage(content=raw_input)],
        }
    except Exception as e:
        logger.error("Scribe node error: %s", e, exc_info=True)
        return {
            "parsed_transaction": None,
            "response_to_user": "An unexpected error occurred while parsing your expense. Please try again later.",
            "messages": [HumanMessage(content=raw_input)],
        }
