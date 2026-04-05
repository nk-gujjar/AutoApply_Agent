"""
Configuration module for AutoApply Agent
Loads environment variables and provides configuration settings
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Optional
import logging
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

# Load environment variables from repository root .env file
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


def _safe_int_env(name: str):
    value = os.getenv(name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

class Config:
    """Configuration class for the AutoApply Agent"""
    
    # Base paths
    BASE_DIR = Path(__file__).resolve().parents[3]
    DATA_DIR = BASE_DIR / "data"
    LOGS_DIR = BASE_DIR / "logs"
    OUTPUT_DIR = BASE_DIR / "output"
    TEMPLATES_DIR = BASE_DIR / "templates"
    
    # Telegram configuration
    TELEGRAM_API_ID = _safe_int_env("TELEGRAM_API_ID")
    TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
    TELEGRAM_SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "tg_user_session")
    PHONE_NUMBER = os.getenv("PHONE_NUMBER")
    TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # AI API configuration
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
    DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "llama3.2")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
    OLLAMA_BASE_URL = "http://localhost:11434"  # default Ollama port
    DEFAULT_LLAMA_MODEL = "llama3.2"

    # Naukri configuration
    NAUKRI_EMAIL = os.getenv("NAUKRI_EMAIL")
    NAUKRI_PASSWORD = os.getenv("NAUKRI_PASSWORD")
    
    # Email configuration
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    
    # Job search configuration
    TARGET_ROLES = os.getenv("TARGET_ROLES", "SDE,Software Engineer").split(",")
    MIN_EXPERIENCE = int(os.getenv("MIN_EXPERIENCE", "0"))
    MAX_EXPERIENCE = int(os.getenv("MAX_EXPERIENCE", "5"))
    MIN_CTC = int(os.getenv("MIN_CTC", "10"))
    TARGET_CHANNELS = os.getenv("TARGET_CHANNELS", "").split(",")
    
    # Application settings
    MAX_APPLICATIONS_PER_DAY = int(os.getenv("MAX_APPLICATIONS_PER_DAY", "10"))
    DELAY_BETWEEN_APPLICATIONS = int(os.getenv("DELAY_BETWEEN_APPLICATIONS", "300"))
    AUTO_APPLY = os.getenv("AUTO_APPLY", "false").lower() == "true"
    
    # File paths
    PERSONAL_PROFILE_PATH = BASE_DIR / "personal.txt"
    TRACKER_CSV_PATH = DATA_DIR / "tracker.csv"
    HISTORY_TXT_PATH = DATA_DIR / "history.txt"
    
    @classmethod
    def validate_config(cls) -> List[str]:
        """Validate required configuration values"""
        missing_configs = []
        
        if not cls.TELEGRAM_API_ID:
            missing_configs.append("TELEGRAM_API_ID")
        if not cls.TELEGRAM_API_HASH:
            missing_configs.append("TELEGRAM_API_HASH")

        if cls.LLM_PROVIDER == "groq" and not cls.GROQ_API_KEY:
            missing_configs.append("GROQ_API_KEY (required when LLM_PROVIDER=groq)")
        elif cls.LLM_PROVIDER not in {"groq", "ollama"}:
            missing_configs.append("LLM_PROVIDER must be one of: groq, ollama")
        
        return missing_configs
    
    @classmethod
    def setup_directories(cls):
        """Create necessary directories if they don't exist"""
        for directory in [cls.DATA_DIR, cls.LOGS_DIR, cls.OUTPUT_DIR, cls.TEMPLATES_DIR]:
            directory.mkdir(exist_ok=True)
    
    @classmethod
    def setup_logging(cls):
        """Setup logging configuration"""
        cls.setup_directories()
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(cls.LOGS_DIR / 'autoapply.log'),
                logging.StreamHandler()
            ]
        )

# Initialize configuration
config = Config()
config.setup_directories()
config.setup_logging()


def create_llm(
    model: Optional[str] = None,
    temperature: float = 0,
    provider: Optional[str] = None,
):
    """Create an LLM client based on provider config.

    Selection order:
    1) Explicit `provider` argument
    2) `LLM_PROVIDER` in .env

    Supported providers:
    - `groq`
    - `ollama`
    """
    selected_provider = (provider or config.LLM_PROVIDER or "ollama").strip().lower()

    if selected_provider == "groq":
        selected_model = model or config.GROQ_MODEL or config.DEFAULT_LLM_MODEL
        return ChatGroq(
            api_key=config.GROQ_API_KEY,
            model=selected_model,
            temperature=temperature,
        )

    if selected_provider == "ollama":
        selected_model = model or config.OLLAMA_MODEL or config.DEFAULT_LLM_MODEL
        return ChatOllama(
            model=selected_model,
            temperature=temperature,
            base_url=config.OLLAMA_BASE_URL,
        )

    raise ValueError(
        f"Unsupported LLM provider '{selected_provider}'. Use one of: groq, ollama"
    )


def get_active_llm_config() -> dict:
    """Return active provider/model info for diagnostics and debug UIs."""
    provider = (config.LLM_PROVIDER or "ollama").strip().lower()
    if provider == "groq":
        return {
            "provider": "groq",
            "model": config.GROQ_MODEL or config.DEFAULT_LLM_MODEL,
        }
    return {
        "provider": "ollama",
        "model": config.OLLAMA_MODEL or config.DEFAULT_LLM_MODEL,
        "base_url": config.OLLAMA_BASE_URL,
    }

logger = logging.getLogger(__name__)

# Validate configuration on import
missing_configs = config.validate_config()
if missing_configs:
    logger.warning(f"Missing configuration values: {', '.join(missing_configs)}")
    logger.warning("Please update your .env file with the required values")