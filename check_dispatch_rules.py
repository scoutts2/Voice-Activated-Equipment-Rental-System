"""
Check current LiveKit dispatch rules to diagnose why calls aren't being routed.
"""
import os
import asyncio
from livekit import api
from dotenv import load_dotenv

load_dotenv()

async def check_rules():
    # Get credentials
    LIVEKIT_URL = os.getenv("LIVEKIT_URL")
    LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
    LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

    print(f"LiveKit URL: {LIVEKIT_URL}")
    print(f"API Key: {LIVEKIT_API_KEY[:10]}...")
    print()

    # Create API client
    lk_api = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET
    )

    print("=" * 60)
    print("CHECKING DISPATCH RULES")
    print("=" * 60)

    try:
        # List all dispatch rules
        agent_dispatch = lk_api.agent_dispatch
        
        # Get all dispatch rules (pass empty string for room name to get all)
        rules = await agent_dispatch.list_dispatch(room_name="")
        
        print(f"\nFound {len(rules)} dispatch rule(s):\n")
        
        for i, rule in enumerate(rules, 1):
            print(f"Rule #{i}:")
            print(f"  Agent Name: {rule.agent_name}")
            print(f"  Room Pattern: {rule.room}")
            print(f"  Metadata: {rule.metadata}")
            print()
        
        if not rules:
            print("⚠️ NO DISPATCH RULES FOUND!")
            print("\nThis is why your agent isn't picking up calls.")
            print("LiveKit doesn't know which agent to route calls to.")
            
    except Exception as e:
        print(f"Error listing dispatch rules: {e}")
        print("\nTrying alternative method...")
        
    print()
    print("=" * 60)
    print("RECOMMENDED DISPATCH RULE FOR TELEPHONY")
    print("=" * 60)
    print()
    print("For Twilio/SIP calls, you need a rule like:")
    print("  Agent Name: agent")
    print("  Room Pattern: * (matches all rooms)")
    print()
    print("This ensures ALL incoming calls are routed to your agent.")
    
    await lk_api.aclose()

if __name__ == "__main__":
    asyncio.run(check_rules())

