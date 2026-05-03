"""
Tests for the LLM factory.
"""

from unittest.mock import patch, MagicMock
import pytest
from langchain_core.language_models import BaseChatModel

from pulse.llm import get_llm
import pulse.llm

@pytest.fixture(autouse=True)
def reset_llm_instance():
    """Reset the singleton instance before each test."""
    pulse.llm._llm_instance = None
    yield
    pulse.llm._llm_instance = None

def test_get_llm_google():
    """Test loading Google provider."""
    with patch("pulse.config.settings.LLM_PROVIDER", "google"), \
         patch("pulse.config.settings.GEMINI_API_KEY", "test_key"), \
         patch("pulse.config.settings.LLM_MODEL_NAME", "gemini-test"), \
         patch("langchain_google_genai.ChatGoogleGenerativeAI") as MockChat:
         
        mock_instance = MagicMock(spec=BaseChatModel)
        MockChat.return_value = mock_instance
        
        llm = get_llm(temperature=0.5)
        
        assert llm == mock_instance
        MockChat.assert_called_once_with(
            model="gemini-test",
            google_api_key="test_key",
            temperature=0.5,
            convert_system_message_to_human=True,
            max_retries=1,
        )

def test_get_llm_ollama():
    """Test loading Ollama provider."""
    with patch("pulse.config.settings.LLM_PROVIDER", "ollama"), \
         patch("pulse.config.settings.OLLAMA_BASE_URL", "http://test:11434"), \
         patch("pulse.config.settings.LLM_MODEL_NAME", "llama3"), \
         patch("langchain_community.chat_models.ChatOllama") as MockOllama:
         
        mock_instance = MagicMock(spec=BaseChatModel)
        MockOllama.return_value = mock_instance
        
        llm = get_llm(temperature=0.1)
        
        assert llm == mock_instance
        MockOllama.assert_called_once_with(
            model="llama3",
            base_url="http://test:11434",
            temperature=0.1,
        )

def test_get_llm_google_missing_key():
    """Test error when Google API key is missing."""
    with patch("pulse.config.settings.LLM_PROVIDER", "google"), \
         patch("pulse.config.settings.GEMINI_API_KEY", None):
         
        with pytest.raises(ValueError, match="GEMINI_API_KEY must be set"):
            get_llm()

def test_get_llm_unsupported_provider():
    """Test error on unsupported provider."""
    with patch("pulse.config.settings.LLM_PROVIDER", "unsupported"):
        with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
            get_llm()
