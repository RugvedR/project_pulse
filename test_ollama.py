"""
Local Migration Tester — Verifies Ollama connectivity and the LLM factory.

This script helps you verify that your local model migration (Phase 4)
is working correctly. It checks if Ollama is reachable and if the 
Pulse LLM factory can successfully communicate with it.

Usage:
    1. Ensure Ollama is running (`ollama serve`)
    2. Ensure a model is pulled (`ollama pull llama3`)
    3. Run this script: `python test_ollama.py`
"""

import asyncio
import logging
import sys
from unittest.mock import patch

from pulse.llm import get_llm, extract_text
from pulse.config import settings

# Setup simple logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

async def test_ollama_connectivity():
    print("\n--- Pulse Local Migration Test ---")
    
    # 1. Temporarily switch settings to Ollama for this test
    print(f"[*] Testing with LLM_PROVIDER=ollama")
    print(f"[*] Target Model: {settings.LLM_MODEL_NAME}")
    print(f"[*] Ollama URL:   {settings.OLLAMA_BASE_URL}")
    
    with patch("pulse.config.settings.LLM_PROVIDER", "ollama"):
        try:
            # 2. Get the LLM instance
            llm = get_llm(temperature=0.0)
            print("[+] LLM Factory initialized Ollama successfully.")
            
            # 3. Try a simple invocation
            print("[*] Sending test prompt to Ollama... (this might take a few seconds)")
            response = await llm.ainvoke("Hello! Reply with only the word 'READY' if you are working.")
            
            text = extract_text(response).strip()
            print(f"[+] Ollama response: {text}")
            
            if "READY" in text.upper():
                print("\n✅ SUCCESS: Local migration is fully operational!")
            else:
                print("\n⚠️ WARNING: Ollama replied, but the response was unexpected.")
                print(f"Raw response: {text}")
                
        except Exception as e:
            print(f"\n❌ ERROR: Failed to connect to Ollama.")
            print(f"Details: {str(e)}")
            print("\nTroubleshooting:")
            print("1. Is Ollama running? Try: `curl http://localhost:11434` in your terminal.")
            print(f"2. Have you pulled the model? Try: `ollama pull {settings.LLM_MODEL_NAME}`")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_ollama_connectivity())
