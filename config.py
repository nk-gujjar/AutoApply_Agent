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

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for the AutoApply Agent"""
    
    # Base paths
    BASE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BASE_DIR / "data"
    LOGS_DIR = BASE_DIR / "logs"
    OUTPUT_DIR = BASE_DIR / "output"
    TEMPLATES_DIR = BASE_DIR / "templates"
    
    # Telegram configuration
    TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
    TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
    TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # AI API configuration
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "llama-3.1-8b-instant")
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
        if not cls.GEMINI_API_KEY:
            missing_configs.append("GEMINI_API_KEY")
        
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


# def create_llm(model: Optional[str] = None, temperature: float = 0):
#     """Create and return a shared-configured ChatGroq client."""
#     return ChatGroq(
#         api_key=config.GROQ_API_KEY,
#         model=model or config.DEFAULT_LLM_MODEL,
#         temperature=temperature,
#     )

def create_llm(model: Optional[str] = None, temperature: float = 0):
    """Create and return a shared-configured local Llama 3.2 client."""
    return ChatOllama(
        model=model or "llama3.2",
        temperature=temperature,
        base_url=config.OLLAMA_BASE_URL,  # e.g. "http://localhost:11434"
    )

logger = logging.getLogger(__name__)

# Validate configuration on import
missing_configs = config.validate_config()
if missing_configs:
    logger.warning(f"Missing configuration values: {', '.join(missing_configs)}")
    logger.warning("Please update your .env file with the required values")