import asyncio
from livekit import api
from config import config

async def fix_dispatch_rules():
    """Create dispatch rules for common playground room patterns."""
    livekit_api = api.LiveKitAPI(
        url=config.LIVEKIT_URL,
        api_key=config.LIVEKIT_API_KEY,
        api_secret=config.LIVEKIT_API_SECRET
    )
    
    try:
        # Create dispatch rules for common playground room patterns
        room_patterns = [
            "playground-test-room",
            "playground-*", 
            "test-*",
            "room-*",
            "*test*",
            "*playground*"
        ]
        
        agent_names = ["agent", "default", "equipment-rental-agent"]
        
        for agent_name in agent_names:
            for room in room_patterns:
                try:
                    print(f"Creating dispatch rule: {agent_name} -> {room}")
                    dispatch_rule = api.CreateAgentDispatchRequest(
                        agent_name=agent_name,
                        room=room
                    )
                    
                    result = await livekit_api.agent_dispatch.create_dispatch(dispatch_rule)
                    print(f"✅ Created: {result.id}")
                    
                except Exception as e:
                    print(f"❌ Failed {agent_name} -> {room}: {e}")
                    
    except Exception as e:
        print(f"General error: {e}")
    
    await livekit_api.aclose()

if __name__ == "__main__":
    asyncio.run(fix_dispatch_rules())
