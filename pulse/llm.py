"""
LLM Factory Abstraction — dynamically loads the configured LLM provider.

Provides a unified interface for the rest of the application, allowing
seamless swapping between Google Gemini (Cloud) and Ollama (Local).
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

from pulse.config import settings

logger = logging.getLogger(__name__)

# Cache for the LLM instance to avoid re-initialization
_llm_instance: BaseChatModel | None = None


def get_llm(temperature: float = 0.0) -> BaseChatModel:
    """
    Get or create the LLM instance based on configuration.
    Lazy-loaded on first call.

    Args:
        temperature: The temperature to use for the model.

    Returns:
        A LangChain BaseChatModel instance.
    """
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    provider = settings.LLM_PROVIDER.lower().strip()

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY must be set when LLM_PROVIDER is 'google'")
            
        logger.info("Initializing Google Gemini model: %s", settings.LLM_MODEL_NAME)
        _llm_instance = ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL_NAME,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=temperature,
            convert_system_message_to_human=True,
            max_retries=1,
        )
    elif provider == "ollama":
        from langchain_community.chat_models import ChatOllama
        
        logger.info(
            "Initializing Ollama local model: %s at %s", 
            settings.LLM_MODEL_NAME, settings.OLLAMA_BASE_URL
        )
        _llm_instance = ChatOllama(
            model=settings.LLM_MODEL_NAME,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=temperature,
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

    return _llm_instance

def extract_text(response: Any) -> str:
    """
    Safely extract text from an LLM response.
    Newer LangChain versions sometimes return a list of content blocks
    instead of a simple string for certain model outputs.
    """
    content = response.content
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        return "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in content])
    return str(content)
