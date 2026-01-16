#!/usr/bin/env python3
"""
Cloudflare Tunnel URL degisikliklerini izler ve Firebase'i otomatik gunceller.
Docker container olarak calisir, cloudflared loglarini surekli izler.
"""

import os
import re
import time

import docker
import firebase_admin
from firebase_admin import credentials, firestore

# Global state
current_url = None
db = None
docker_client = None


def init_firebase():
    """Firebase baglantisini baslat."""
    global db

    cred_path = os.environ.get("FIREBASE_CREDENTIALS_FILE", "/app/credentials/serviceAccount.json")

    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)

    db = firestore.client()
    print("[INIT] Firebase connected")


def init_docker():
    """Docker client baslat."""
    global docker_client

    try:
        docker_client = docker.from_env()
        print("[INIT] Docker connected")
        return True
    except Exception as e:
        print(f"[ERROR] Docker connection failed: {e}")
        return False


def update_firebase_url(url: str) -> bool:
    """Firebase'e URL kaydet (test server icin)."""
    global db

    try:
        settings_ref = db.collection("settings").document("app_settings")
        settings_ref.set({"testServerUrl": url}, merge=True)
        print(f"[FIREBASE] Updated testServerUrl = {url}")
        return True
    except Exception as e:
        print(f"[ERROR] Firebase update failed: {e}")
        return False


def is_valid_tunnel_url(url: str) -> bool:
    """
    Validate that URL is a real tunnel URL (4 words separated by hyphens).
    Rejects: api.trycloudflare.com, www.trycloudflare.com, etc.
    Accepts: miles-age-performing-lemon.trycloudflare.com
    """
    # Extract subdomain
    match = re.match(r'https://([\w-]+)\.trycloudflare\.com', url)
    if not match:
        return False

    subdomain = match.group(1)
    # Real tunnel URLs have 4 random words separated by hyphens
    parts = subdomain.split('-')
    return len(parts) >= 3 and all(p.isalpha() for p in parts)


def get_latest_url_from_logs() -> str | None:
    """Docker loglarindan en son tunnel URL'ini al."""
    global docker_client

    try:
        # Find cloudflared container - use partial match for compose naming
        containers = docker_client.containers.list()
        cloudflared_container = None
        for c in containers:
            if "cloudflared" in c.name:
                cloudflared_container = c
                break

        if not cloudflared_container:
            print("[WARN] cloudflared container not found")
            return None

        # Get logs (last 100 lines)
        logs = cloudflared_container.logs(tail=100).decode("utf-8", errors="ignore")

        # Find all URLs, filter valid ones, return the last valid one
        matches = re.findall(r'https://[\w-]+\.trycloudflare\.com', logs)
        valid_urls = [url for url in matches if is_valid_tunnel_url(url)]
        if valid_urls:
            return valid_urls[-1]

    except Exception as e:
        print(f"[ERROR] Failed to read logs: {e}")

    return None


def watch_tunnel():
    """Tunnel URL degisikliklerini izle ve Firebase'i guncelle."""
    global current_url

    print("[WATCHER] Starting tunnel URL watcher...")
    print("[WATCHER] Waiting for cloudflared to start...")

    # Initial wait for cloudflared
    time.sleep(10)

    while True:
        try:
            new_url = get_latest_url_from_logs()

            if new_url and new_url != current_url:
                print(f"[WATCHER] New URL detected: {new_url}")
                if update_firebase_url(new_url):
                    current_url = new_url

            # Check every 5 seconds
            time.sleep(5)

        except KeyboardInterrupt:
            print("[WATCHER] Stopping...")
            break
        except Exception as e:
            print(f"[ERROR] Watcher error: {e}")
            time.sleep(5)


def main():
    print("=" * 50)
    print("  Cloudflare Tunnel URL Watcher")
    print("=" * 50)

    init_firebase()

    if not init_docker():
        print("[ERROR] Cannot connect to Docker. Exiting.")
        return

    watch_tunnel()


if __name__ == "__main__":
    main()
