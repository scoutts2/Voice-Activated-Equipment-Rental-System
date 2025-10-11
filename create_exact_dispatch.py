import asyncio
from livekit import api
from config import config

async def create_exact_dispatch():
    """Create dispatch rule for the exact playground room pattern."""
    livekit_api = api.LiveKitAPI(
        url=config.LIVEKIT_URL,
        api_key=config.LIVEKIT_API_KEY,
        api_secret=config.LIVEKIT_API_SECRET
    )
    
    try:
        # Create dispatch rule for the exact room pattern the playground uses
        room_pattern = "playground-iiqV-4BEh"
        
        agent_names = ["agent", "default", "equipment-rental-agent"]
        
        for agent_name in agent_names:
            try:
                print(f"Creating dispatch rule: {agent_name} -> {room_pattern}")
                dispatch_rule = api.CreateAgentDispatchRequest(
                    agent_name=agent_name,
                    room=room_pattern
                )
                
                result = await livekit_api.agent_dispatch.create_dispatch(dispatch_rule)
                print(f"✅ Created: {result.id}")
                
            except Exception as e:
                print(f"❌ Failed {agent_name} -> {room_pattern}: {e}")
        
        # Also create a more general pattern for similar rooms
        general_patterns = [
            "playground-*",
            "playground-iiqV-*"
        ]
        
        for pattern in general_patterns:
            for agent_name in agent_names:
                try:
                    print(f"Creating dispatch rule: {agent_name} -> {pattern}")
                    dispatch_rule = api.CreateAgentDispatchRequest(
                        agent_name=agent_name,
                        room=pattern
                    )
                    
                    result = await livekit_api.agent_dispatch.create_dispatch(dispatch_rule)
                    print(f"✅ Created: {result.id}")
                    
                except Exception as e:
                    print(f"❌ Failed {agent_name} -> {pattern}: {e}")
                    
    except Exception as e:
        print(f"General error: {e}")
    
    await livekit_api.aclose()

if __name__ == "__main__":
    asyncio.run(create_exact_dispatch())
