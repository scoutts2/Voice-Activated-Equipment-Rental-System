import asyncio
from livekit import api
from config import config

async def create_catch_all_dispatch():
    """Create catch-all dispatch rules that will work for any room the playground creates."""
    livekit_api = api.LiveKitAPI(
        url=config.LIVEKIT_URL,
        api_key=config.LIVEKIT_API_KEY,
        api_secret=config.LIVEKIT_API_SECRET
    )
    
    try:
        # Create catch-all dispatch rules that will match ANY room
        catch_all_patterns = [
            "*",  # Match ALL rooms
            "playground-*",  # Match any playground room
            "room-*",  # Match any room-* pattern
            "test-*",  # Match any test room
            "*-*",  # Match any room with hyphens
        ]
        
        agent_names = ["agent", "default", "equipment-rental-agent", "assistant"]
        
        for pattern in catch_all_patterns:
            for agent_name in agent_names:
                try:
                    print(f"Creating catch-all dispatch rule: {agent_name} -> {pattern}")
                    dispatch_rule = api.CreateAgentDispatchRequest(
                        agent_name=agent_name,
                        room=pattern
                    )
                    
                    result = await livekit_api.agent_dispatch.create_dispatch(dispatch_rule)
                    print(f"✅ Created: {result.id}")
                    
                except Exception as e:
                    print(f"❌ Failed {agent_name} -> {pattern}: {e}")
                    
        print("\n🎉 Now ANY room the playground creates should connect to your agent!")
                    
    except Exception as e:
        print(f"General error: {e}")
    
    await livekit_api.aclose()

if __name__ == "__main__":
    asyncio.run(create_catch_all_dispatch())
