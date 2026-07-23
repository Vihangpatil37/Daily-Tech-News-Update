import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

logger = logging.getLogger("tech-agent")

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Configuration parameters
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "").strip()

DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "agent.db")).strip()
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata").strip()

try:
    LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "24"))
except ValueError:
    LOOKBACK_HOURS = 24


def validate_config(strict: bool = False) -> list[str]:
    """
    Validates that required configuration environment variables are set.
    Returns a list of missing required variable names.
    If strict=True, raises SystemExit on missing required variables.
    """
    missing = []
    
    # Required for production email delivery
    if not GMAIL_ADDRESS:
        missing.append("GMAIL_ADDRESS")
    if not GMAIL_APP_PASSWORD:
        missing.append("GMAIL_APP_PASSWORD")
    if not RECIPIENT_EMAIL:
        missing.append("RECIPIENT_EMAIL")
        
    # Required for Gemini LLM summarization
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")

    if missing:
        msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.warning(msg)
        if strict:
            logger.error("Failing fast due to missing configuration.")
            sys.exit(1)
            
    return missing
