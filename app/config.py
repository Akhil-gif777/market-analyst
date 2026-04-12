"""
Application configuration.

Loads settings from environment variables or .env file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


@dataclass
class Config:
    # API Keys
    alpha_vantage_api_key: str = ""

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "deepseek-r1:32b"
    ollama_temperature: float = 0.3
    ollama_timeout: int = 1800

    # Analysis
    analysis_max_news_articles: int = 50
    analysis_max_stocks_per_sector: int = 5

    # Database
    db_path: str = "data/market_analyst.db"

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY", ""),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "deepseek-r1:32b"),
            ollama_temperature=float(os.getenv("OLLAMA_TEMPERATURE", "0.3")),
            ollama_timeout=int(os.getenv("OLLAMA_TIMEOUT", "1800")),
            analysis_max_news_articles=int(os.getenv("MAX_NEWS_ARTICLES", "50")),
            analysis_max_stocks_per_sector=int(os.getenv("MAX_STOCKS_PER_SECTOR", "5")),
            db_path=os.getenv("DB_PATH", "data/market_analyst.db"),
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8000")),
        )


# Singleton
config = Config.from_env()
