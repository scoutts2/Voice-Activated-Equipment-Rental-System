#!/usr/bin/env python3
"""
Debug LiveKit credentials
"""
import os

print("=== LiveKit Credentials Debug ===")
livekit_url = os.getenv('LIVEKIT_URL', 'NOT SET')
livekit_key = os.getenv('LIVEKIT_API_KEY', 'NOT SET')
livekit_secret = os.getenv('LIVEKIT_API_SECRET', 'NOT SET')

print(f"LIVEKIT_URL: {livekit_url}")
print(f"LIVEKIT_API_KEY: {livekit_key[:10]}..." if livekit_key != 'NOT SET' else "LIVEKIT_API_KEY: NOT SET")
print(f"LIVEKIT_API_SECRET: {livekit_secret[:10]}..." if livekit_secret != 'NOT SET' else "LIVEKIT_API_SECRET: NOT SET")

# Check if they look valid
if livekit_url != 'NOT SET' and livekit_key != 'NOT SET' and livekit_secret != 'NOT SET':
    print("\n✅ All credentials are present")
    if livekit_url.startswith('wss://') and livekit_url.endswith('.livekit.cloud'):
        print("✅ URL format looks correct")
    else:
        print("❌ URL format looks incorrect")
else:
    print("\n❌ Missing credentials")
