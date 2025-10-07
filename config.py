"""Configuration management."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

class Config:
    # LiveKit
    LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
    LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
    LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")
    
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    
    # Deepgram
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
    
    # ElevenLabs
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
    
    # Google Sheets
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    EQUIPMENT_SHEET_ID = os.getenv("EQUIPMENT_SHEET_ID", "")
    EQUIPMENT_SHEET_NAME = os.getenv("EQUIPMENT_SHEET_NAME", "Sheet1")
    
    # CSV Fallback
    EQUIPMENT_CSV_PATH = os.getenv("EQUIPMENT_CSV_PATH", str(BASE_DIR / "data" / "equipment_inventory.csv"))
    
    # Agent Config
    AGENT_NAME = os.getenv("AGENT_NAME", "Metro Equipment Rental Agent")
    COMPANY_NAME = os.getenv("COMPANY_NAME", "Metro Equipment Rentals")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

config = Config()
