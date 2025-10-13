"""
Create a dispatch rule that will route ALL incoming calls to your agent.
This is critical for telephony to work.
"""
import os
import asyncio
from livekit import api
from dotenv import load_dotenv

load_dotenv()

async def create_dispatch():
    # Get credentials
    LIVEKIT_URL = os.getenv("LIVEKIT_URL")
    LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
    LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

    print(f"LiveKit URL: {LIVEKIT_URL}")
    print()

    # Create API client
    lk_api = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET
    )

    print("=" * 60)
    print("CREATING TELEPHONY DISPATCH RULE")
    print("=" * 60)
    print()

    try:
        agent_dispatch = lk_api.agent_dispatch
        
        # Create a dispatch rule that matches ALL rooms (including SIP rooms)
        request = api.CreateAgentDispatchRequest(
            agent_name="agent",  # Must match your agent_name in agent.py
            room="*",            # Wildcard - matches ALL room names
            metadata=""          # Optional metadata
        )
        
        print("Creating dispatch rule:")
        print(f"  Agent Name: agent")
        print(f"  Room Pattern: * (matches ALL rooms)")
        print()
        
        result = await agent_dispatch.create_dispatch(request)
        
        print("✅ SUCCESS! Dispatch rule created.")
        print()
        print("Your agent should now pick up ALL incoming calls,")
        print("including Twilio/SIP calls.")
        print()
        print("Try calling your Twilio number now!")
        
    except Exception as e:
        print(f"❌ Error creating dispatch rule: {e}")
        print()
        if "already exists" in str(e).lower():
            print("The dispatch rule might already exist.")
            print("Check your LiveKit dashboard:")
            print(f"  {LIVEKIT_URL.replace('wss://', 'https://')}/dashboard")
            print()
            print("Go to: Settings → Agent Dispatch Rules")
        else:
            print("Try creating the rule manually in the LiveKit dashboard:")
            print(f"  1. Go to {LIVEKIT_URL.replace('wss://', 'https://')}/dashboard")
            print("  2. Navigate to: Settings → Agent Dispatch Rules")
            print("  3. Click 'Create Rule'")
            print("  4. Set Agent Name: agent")
            print("  5. Set Room Name: *")
            print("  6. Save")
    
    await lk_api.aclose()

if __name__ == "__main__":
    asyncio.run(create_dispatch())

