"""Configuration settings for Crypto.com Trader & Strategy Hub."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Server configuration
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5050"))
    DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    SECRET_KEY = os.getenv("SECRET_KEY", "cryptocom-pro-trader-secret-key-2026")

    # Optional Basic / Simple Password Authentication
    AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")
    APP_PASSWORD = os.getenv("APP_PASSWORD", "trader2026")

    # Crypto.com Exchange API Credentials
    CRYPTO_COM_API_KEY = os.getenv("CRYPTO_COM_API_KEY", "")
    CRYPTO_COM_API_SECRET = os.getenv("CRYPTO_COM_API_SECRET", "")

    # AI Model API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
