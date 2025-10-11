#!/usr/bin/env python3
"""
Debug script to test Railway deployment
"""
import os
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("=== RAILWAY DEBUG SCRIPT STARTED ===")
    
    # Check Python version
    logger.info(f"Python version: {sys.version}")
    
    # Check environment variables
    logger.info("=== ENVIRONMENT VARIABLES ===")
    env_vars = [
        'LIVEKIT_URL',
        'LIVEKIT_API_KEY', 
        'LIVEKIT_API_SECRET',
        'OPENAI_API_KEY',
        'DEEPGRAM_API_KEY',
        'ELEVEN_API_KEY'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            masked_value = value[:8] + "..." if len(value) > 8 else "***"
            logger.info(f"{var}: {masked_value}")
        else:
            logger.warning(f"{var}: NOT SET")
    
    # Check if we can import required modules
    logger.info("=== MODULE IMPORTS ===")
    try:
        import livekit
        logger.info("✅ livekit imported successfully")
    except ImportError as e:
        logger.error(f"❌ Failed to import livekit: {e}")
    
    try:
        import livekit.agents
        logger.info("✅ livekit.agents imported successfully")
    except ImportError as e:
        logger.error(f"❌ Failed to import livekit.agents: {e}")
    
    try:
        import livekit.plugins.openai
        logger.info("✅ livekit.plugins.openai imported successfully")
    except ImportError as e:
        logger.error(f"❌ Failed to import livekit.plugins.openai: {e}")
    
    try:
        import livekit.plugins.deepgram
        logger.info("✅ livekit.plugins.deepgram imported successfully")
    except ImportError as e:
        logger.error(f"❌ Failed to import livekit.plugins.deepgram: {e}")
    
    # Try to import our agent
    try:
        import agent
        logger.info("✅ agent.py imported successfully")
    except ImportError as e:
        logger.error(f"❌ Failed to import agent.py: {e}")
    except Exception as e:
        logger.error(f"❌ Error importing agent.py: {e}")
    
    logger.info("=== DEBUG SCRIPT COMPLETED ===")

if __name__ == "__main__":
    main()
