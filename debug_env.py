#!/usr/bin/env python3
"""
Debug script to check environment variables in Railway
"""
import os
from dotenv import load_dotenv

# Load .env file (for local testing)
load_dotenv()

print("=== Environment Variables Debug (Railway Test) ===")
livekit_url = os.getenv('LIVEKIT_URL', 'NOT SET')
print(f"LIVEKIT_URL: {livekit_url}")
if livekit_url != 'NOT SET':
    print(f"URL Analysis: {livekit_url}")
    if 'p_45gsu90kw0u' in livekit_url:
        print("⚠️  WARNING: This URL format might be incorrect!")
        print("   Expected format: wss://your-project-name.livekit.cloud")
print(f"LIVEKIT_API_KEY: {os.getenv('LIVEKIT_API_KEY', 'NOT SET')}")
print(f"LIVEKIT_API_SECRET: {os.getenv('LIVEKIT_API_SECRET', 'NOT SET')}")
print(f"OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY', 'NOT SET')}")
print(f"DEEPGRAM_API_KEY: {os.getenv('DEEPGRAM_API_KEY', 'NOT SET')}")
print(f"ELEVENLABS_API_KEY: {os.getenv('ELEVENLABS_API_KEY', 'NOT SET')}")
print(f"ELEVEN_API_KEY: {os.getenv('ELEVEN_API_KEY', 'NOT SET')}")

print("\n=== All Environment Variables ===")
for key, value in os.environ.items():
    if 'LIVEKIT' in key or 'OPENAI' in key or 'DEEPGRAM' in key or 'ELEVEN' in key:
        print(f"{key}: {value[:10]}..." if len(value) > 10 else f"{key}: {value}")
