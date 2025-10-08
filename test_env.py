#!/usr/bin/env python3
"""
Test script to check environment variables
"""
import os

print("=== Environment Variables Test ===")
print(f"LIVEKIT_URL: {os.getenv('LIVEKIT_URL', 'NOT SET')}")
print(f"All env vars with LIVEKIT:")
for key, value in os.environ.items():
    if 'LIVEKIT' in key:
        print(f"  {key}: {value}")
