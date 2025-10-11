import asyncio
import aiohttp
from livekit import rtc, api
from config import config

async def test_direct_connection():
    """Test direct connection to LiveKit room to verify agent is working."""
    
    # Create room token for testing
    token = api.AccessToken(config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET)
    token.with_identity("test-user")
    token.with_name("Test User")
    token.with_grants(api.VideoGrants(
        room_join=True,
        room="test-room",
        can_publish=True,
        can_subscribe=True
    ))
    
    room_token = token.to_jwt()
    
    # Connect to room
    room = rtc.Room()
    
    @room.on("participant_connected")
    def on_participant_connected(participant):
        print(f"✅ Participant connected: {participant.identity}")
        if participant.identity.startswith("agent"):
            print("🎉 AGENT FOUND!")
        else:
            print("👤 Regular participant")
    
    @room.on("participant_disconnected") 
    def on_participant_disconnected(participant):
        print(f"❌ Participant disconnected: {participant.identity}")
    
    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        print(f"🔊 Track subscribed: {track.kind} from {participant.identity}")
    
    try:
        print("Connecting to LiveKit room...")
        print(f"URL: {config.LIVEKIT_URL}")
        print(f"Room: test-room")
        
        await room.connect(config.LIVEKIT_URL, room_token)
        print("✅ Connected to room!")
        
        # Wait for participants
        print("Waiting for participants...")
        await asyncio.sleep(10)
        
        print(f"Participants in room: {len(room.remote_participants)}")
        for participant in room.remote_participants.values():
            print(f"  - {participant.identity}")
            
        if len(room.remote_participants) == 0:
            print("❌ No agent connected - dispatch rules may not be working")
        else:
            print("✅ Agent should be connected!")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    finally:
        await room.disconnect()
        print("Disconnected from room")

if __name__ == "__main__":
    asyncio.run(test_direct_connection())
