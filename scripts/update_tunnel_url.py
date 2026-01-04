#!/usr/bin/env python3
"""
Cloudflare Quick Tunnel URL'ini alip Firebase'e kaydeder.
Docker-compose up sonrasi calistirilmali.
"""

import re
import subprocess
import sys
import time

import firebase_admin
from firebase_admin import credentials, firestore


def get_tunnel_url(max_retries: int = 10, retry_delay: float = 2.0) -> str | None:
    """Docker logs'dan Cloudflare tunnel URL'ini ceker (en son URL'i alir)."""

    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                ["docker-compose", "logs", "cloudflared", "--tail", "100"],
                capture_output=True,
                text=True,
                cwd=r"D:\agents-sdk"
            )

            # URL pattern: https://xxx.trycloudflare.com - find ALL matches, return LAST one
            matches = re.findall(r'https://[\w-]+\.trycloudflare\.com', result.stdout)
            if matches:
                return matches[-1]  # Return the most recent URL

            print(f"Attempt {attempt + 1}/{max_retries}: URL not found yet, waiting...")
            time.sleep(retry_delay)

        except Exception as e:
            print(f"Error reading logs: {e}")
            time.sleep(retry_delay)

    return None


def update_firebase_url(url: str) -> bool:
    """Firebase settings/app_settings'e serverUrl kaydeder."""

    try:
        # Firebase Admin SDK init
        if not firebase_admin._apps:
            cred = credentials.Certificate(r"D:\agents-sdk\serviceAccount.json")
            firebase_admin.initialize_app(cred)

        db = firestore.client()

        # Update settings document
        settings_ref = db.collection("settings").document("app_settings")
        settings_ref.set({"serverUrl": url}, merge=True)

        print(f"[OK] Firebase updated: serverUrl = {url}")
        return True

    except Exception as e:
        print(f"[ERROR] Firebase update failed: {e}")
        return False


def main():
    print("Getting Cloudflare Tunnel URL...")

    url = get_tunnel_url()

    if not url:
        print("[ERROR] Tunnel URL not found!")
        sys.exit(1)

    print(f"[OK] Tunnel URL: {url}")

    print("Updating Firebase...")
    success = update_firebase_url(url)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
