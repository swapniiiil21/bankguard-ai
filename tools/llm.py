"""
tools/llm.py
Groq LLM client setup with model selection and retry logic.
"""

import logging
import os
from functools import lru_cache

from dotenv import load_dotenv
from groq import Groq
from langchain_groq import ChatGroq

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DEFAULT_MODEL = "llama-3.3-70b-versatile"
FAST_MODEL = "llama-3.1-8b-instant"


@lru_cache(maxsize=1)
def get_groq_client() -> Groq:
    """Return a cached Groq SDK client."""
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set — LLM calls will fail.")
    return Groq(api_key=GROQ_API_KEY)


def get_langchain_llm(model: str = DEFAULT_MODEL, temperature: float = 0.1) -> ChatGroq:
    """Return a LangChain-compatible ChatGroq LLM instance."""
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model_name=model,
        temperature=temperature,
        max_retries=3,
    )


def call_llm(prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.1) -> str:
    """
    Call Groq LLM with a plain string prompt and return the text response.

    Args:
        prompt: The full prompt string.
        model: Groq model name.
        temperature: Sampling temperature.

    Returns:
        LLM response as a string.
    """
    client = get_groq_client()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=2048,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        return f"[LLM ERROR] {exc}"
