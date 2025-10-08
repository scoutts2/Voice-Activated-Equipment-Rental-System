#!/usr/bin/env python3
"""
Test if Railway can read custom environment variables
"""
import os

print("=== Testing Custom Environment Variables ===")
print(f"TEST_VAR: {os.getenv('TEST_VAR', 'NOT SET')}")
print(f"LIVEKIT_URL: {os.getenv('LIVEKIT_URL', 'NOT SET')}")
print(f"LIVEKIT_API_KEY: {os.getenv('LIVEKIT_API_KEY', 'NOT SET')}")
print(f"OPENAI_API_KEY: {os.getenv('OPENAI_API_KEY', 'NOT SET')}")

print("\n=== All variables containing 'LIVEKIT' ===")
for key, value in os.environ.items():
    if 'LIVEKIT' in key.upper():
        print(f"{key}: {value}")
