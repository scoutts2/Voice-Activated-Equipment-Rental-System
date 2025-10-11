import asyncio
import aiohttp
from livekit import rtc, api
from config import config

async def test_specific_room():
    """Test connection to the specific room the playground created."""
    
    # Create room token for the specific playground room
    token = api.AccessToken(config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET)
    token.with_identity("playground-user")
    token.with_name("Playground User")
    token.with_grants(api.VideoGrants(
        room_join=True,
        room="playground-iiqV-4BEh",  # The exact room from playground
        can_publish=True,
        can_subscribe=True
    ))
    
    room_token = token.to_jwt()
    
    # Connect to room
    room = rtc.Room()
    
    @room.on("participant_connected")
    def on_participant_connected(participant):
        print(f"✅ Participant connected: {participant.identity}")
        if "agent" in participant.identity.lower():
            print("🎉 AGENT FOUND!")
        else:
            print("👤 Regular participant")
    
    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        print(f"🔊 Track subscribed: {track.kind} from {participant.identity}")
    
    try:
        print("Testing connection to playground room...")
        print(f"URL: {config.LIVEKIT_URL}")
        print(f"Room: playground-iiqV-4BEh")
        print("Waiting for agent...")
        
        await room.connect(config.LIVEKIT_URL, room_token)
        print("✅ Connected to playground room!")
        
        # Wait for agent to connect
        print("Waiting for agent (10 seconds)...")
        await asyncio.sleep(10)
        
        print(f"Participants in room: {len(room.remote_participants)}")
        for participant in room.remote_participants.values():
            print(f"  - {participant.identity}")
            
        if len(room.remote_participants) == 0:
            print("❌ No agent connected to this specific room")
            print("We may need a more specific dispatch rule")
        else:
            print("✅ Agent connected successfully!")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    finally:
        await room.disconnect()
        print("Disconnected from room")

if __name__ == "__main__":
    asyncio.run(test_specific_room())
