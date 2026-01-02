"""
Basit test scripti - Postman'daki exact request'i test eder.
"""
import asyncio
import base64
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_AI_API_KEY")
MODEL = os.getenv("IMAGE_MODEL", "gemini-2.5-flash-image")

async def test_image_generation():
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

    headers = {
        "x-goog-api-key": API_KEY,
        "Content-Type": "application/json",
    }

    # Postman'daki exact payload - generationConfig YOK
    payload = {
        "contents": [{
            "parts": [
                {"text": "Create a picture of a nano banana dish in a fancy restaurant with a Gemini theme"}
            ]
        }]
    }

    print(f"URL: {url}")
    print(f"Model: {MODEL}")
    print(f"API Key: {API_KEY[:10]}..." if API_KEY else "API Key: None")
    print(f"Payload: {payload}")
    print("-" * 50)

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, headers=headers, json=payload)

        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print("-" * 50)

        if response.status_code != 200:
            print(f"ERROR Response: {response.text}")
            return

        data = response.json()
        print(f"Response Keys: {list(data.keys())}")

        candidates = data.get("candidates", [])
        print(f"Candidates count: {len(candidates)}")

        if candidates:
            content = candidates[0].get("content", {})
            print(f"Content keys: {list(content.keys())}")

            parts = content.get("parts", [])
            print(f"Parts count: {len(parts)}")

            for i, part in enumerate(parts):
                print(f"\nPart {i}:")
                print(f"  Keys: {list(part.keys())}")

                if "text" in part:
                    print(f"  Text: {part['text'][:200]}...")

                if "inlineData" in part:
                    inline = part["inlineData"]
                    print(f"  Inline data mimeType: {inline.get('mimeType')}")
                    data_str = inline.get("data", "")
                    print(f"  Inline data length: {len(data_str)} chars")

                    # Save image
                    if data_str:
                        image_bytes = base64.b64decode(data_str)
                        with open("test_output.png", "wb") as f:
                            f.write(image_bytes)
                        print(f"  Image saved to test_output.png ({len(image_bytes)} bytes)")
        else:
            print(f"Full response: {data}")

if __name__ == "__main__":
    asyncio.run(test_image_generation())
