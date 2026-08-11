# app/config.py
import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY") or ""
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY") or ""

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env")
if not TAVILY_API_KEY:
    raise ValueError("TAVILY_API_KEY not found in .env")

LLM_MODEL = "gemini-2.5-flash"


def get_llm(temperature: float = 0.3) -> ChatGoogleGenerativeAI:
    """Return a ChatGoogleGenerativeAI instance for the configured model."""
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        temperature=temperature,
        google_api_key=GOOGLE_API_KEY,
    )
