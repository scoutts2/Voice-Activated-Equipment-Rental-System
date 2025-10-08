#!/usr/bin/env python3
"""
Show all environment variables
"""
import os

print("=== ALL Environment Variables ===")
for key, value in sorted(os.environ.items()):
    print(f"{key}: {value}")
