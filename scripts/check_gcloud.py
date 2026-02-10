#!/usr/bin/env python3
"""Check if gcloud is available and provide installation help"""

import subprocess
import sys
import platform

def check_gcloud():
    """Check if gcloud is available"""
    try:
        result = subprocess.run(
            ["gcloud", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        print("✓ gcloud CLI found:")
        print(result.stdout)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ gcloud CLI not found in PATH")
        
        if platform.system() == "Windows":
            print("\nWindows detected. Common locations:")
            print("  C:\\Program Files (x86)\\Google\\Cloud SDK\\google-cloud-sdk\\bin")
            print("  C:\\Users\\<USERNAME>\\AppData\\Local\\Google\\Cloud SDK\\google-cloud-sdk\\bin")
            
            print("\nOptions:")
            print("1. Run setup from Google Cloud SDK Shell")
            print("2. Add gcloud to PATH:")
            print("   - Search 'Environment Variables' in Windows")
            print("   - Edit System PATH")
            print("   - Add: C:\\Program Files (x86)\\Google\\Cloud SDK\\google-cloud-sdk\\bin")
            print("   - Restart terminal")
            
        return False

if __name__ == "__main__":
    if check_gcloud():
        sys.exit(0)
    else:
        sys.exit(1)
