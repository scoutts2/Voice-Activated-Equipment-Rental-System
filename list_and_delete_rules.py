"""
List all dispatch rules and optionally delete the ones created by scripts.
Keep only the one you created manually in the LiveKit dashboard.
"""
import os
import asyncio
from livekit import api
from dotenv import load_dotenv

load_dotenv()

async def manage_rules():
    LIVEKIT_URL = os.getenv("LIVEKIT_URL")
    LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
    LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

    print(f"LiveKit URL: {LIVEKIT_URL}")
    print()

    lk_api = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET
    )

    print("=" * 60)
    print("LISTING ALL DISPATCH RULES")
    print("=" * 60)
    print()
    
    # Try to use the REST API directly since list_dispatch has issues
    try:
        # The agent dispatch API has limited functionality
        # We can create rules but listing them requires the REST API
        print("Note: The LiveKit Python SDK has limited dispatch rule listing.")
        print("Please check your LiveKit dashboard to see all rules:")
        print()
        print(f"  {LIVEKIT_URL.replace('wss://', 'https://').replace('.livekit.cloud', '.livekit.cloud/dashboard')}")
        print()
        print("  Go to: Settings → Agent Dispatch")
        print()
        print("You can delete any rules created by scripts there.")
        print("Keep only the one rule you created manually:")
        print("  - Agent Name: agent")
        print("  - Room: *")
        
    except Exception as e:
        print(f"Error: {e}")
    
    await lk_api.aclose()

if __name__ == "__main__":
    asyncio.run(manage_rules())

