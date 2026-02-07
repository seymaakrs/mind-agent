from __future__ import annotations

import asyncio
import base64
import httpx
from functools import lru_cache

import google.auth
import google.auth.transport.requests
from google.oauth2 import service_account

from src.app.config import get_settings, get_model_settings


class ImageGenerationClient:
    """Google AI (Gemini/Nano Banana) REST API image generation client."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    DEFAULT_MODEL = "gemini-2.5-flash-image"

    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.google_ai_api_key:
            raise ValueError("GOOGLE_AI_API_KEY env degiskeni ayarlanmamis")

    @property
    def _api_key(self) -> str:
        return self._settings.google_ai_api_key

    @property
    def _model(self) -> str:
        model_settings = get_model_settings()
        return model_settings.image_generation_model or self.DEFAULT_MODEL

    def _get_endpoint(self) -> str:
        """REST API endpoint URL'i olusturur."""
        return f"{self.BASE_URL}/{self._model}:generateContent"

    def _get_headers(self) -> dict[str, str]:
        """Request headers."""
        return {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }

    async def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "1:1",
    ) -> list[bytes]:
        """
        Text'ten gorsel uretir (text-to-image).

        Args:
            prompt: Gorsel icin aciklama.
            aspect_ratio: En-boy orani ("1:1", "16:9", "9:16", "4:3", "3:4").

        Returns:
            list[bytes]: Uretilen gorsellerin binary datasi.
        """
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "responseModalities": ["image", "text"],
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self._get_endpoint(),
                headers=self._get_headers(),
                json=payload,
            )
            if response.status_code != 200:
                error_detail = response.text
                raise RuntimeError(f"API Error {response.status_code}: {error_detail}")
            data = response.json()

        return self._extract_images(data)

    async def edit_image(
        self,
        prompt: str,
        source_image: bytes,
        aspect_ratio: str = "1:1",
    ) -> list[bytes]:
        """
        Mevcut bir gorseli duzenler (image editing).

        Args:
            prompt: Duzenleme icin aciklama.
            source_image: Kaynak gorsel (bytes).
            aspect_ratio: En-boy orani.

        Returns:
            list[bytes]: Duzenlenmis gorsellerin binary datasi.
        """
        # Kaynak gorseli base64'e cevir
        source_base64 = base64.b64encode(source_image).decode("utf-8")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": source_base64,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["image", "text"],
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self._get_endpoint(),
                headers=self._get_headers(),
                json=payload,
            )
            if response.status_code != 200:
                error_detail = response.text
                raise RuntimeError(f"API Error {response.status_code}: {error_detail}")
            data = response.json()

        return self._extract_images(data)

    def _extract_images(self, response_data: dict) -> list[bytes]:
        """Response'dan gorsel verilerini cikarir."""
        images = []

        candidates = response_data.get("candidates", [])
        if not candidates:
            return images

        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            # API camelCase donduruyor: inlineData
            inline_data = part.get("inlineData")
            if inline_data and inline_data.get("data"):
                image_bytes = base64.b64decode(inline_data["data"])
                images.append(image_bytes)

        return images


class VideoGenerationClient:
    """Google AI (Veo) REST API video generation client with long-running operations."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    VERTEX_BASE_URL = "https://{region}-aiplatform.googleapis.com/v1"
    DEFAULT_MODEL = "veo-3.1-fast-generate-preview"
    DEFAULT_VERTEX_MODEL = "veo-3.1-fast-generate-preview"
    POLL_INTERVAL = 10  # seconds
    MAX_POLL_ATTEMPTS = 60  # 10 minutes max wait
    VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.google_ai_api_key:
            raise ValueError("GOOGLE_AI_API_KEY env degiskeni ayarlanmamis")
        self._vertex_credentials = None

    @property
    def _api_key(self) -> str:
        return self._settings.google_ai_api_key

    @property
    def _model(self) -> str:
        model_settings = get_model_settings()
        return model_settings.video_generation_model or self.DEFAULT_MODEL

    def _get_headers(self) -> dict[str, str]:
        """Request headers."""
        return {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }

    async def generate_video(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        duration_seconds: int = 8,
    ) -> bytes:
        """
        Text'ten video uretir (text-to-video) using long-running operation.

        Args:
            prompt: Video icin aciklama.
            aspect_ratio: En-boy orani ("16:9", "9:16").
            duration_seconds: Video suresi (saniye).

        Returns:
            bytes: Uretilen videonun binary datasi.
        """
        endpoint = f"{self.BASE_URL}/models/{self._model}:predictLongRunning"

        payload = {
            "instances": [
                {"prompt": prompt}
            ],
            "parameters": {
                "aspectRatio": aspect_ratio,
                "durationSeconds": duration_seconds,
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Start long-running operation
            response = await client.post(
                endpoint,
                headers=self._get_headers(),
                json=payload,
            )
            if response.status_code != 200:
                error_detail = response.text
                raise RuntimeError(f"API Error {response.status_code}: {error_detail}")

            data = response.json()
            operation_name = data.get("name")
            if not operation_name:
                raise RuntimeError(f"Operation name not found in response: {data}")

        # 2. Poll for completion
        video_uri = await self._poll_operation(operation_name)

        # 3. Download video
        video_bytes = await self._download_video(video_uri)

        return video_bytes

    def _get_vertex_access_token(self) -> str:
        """Vertex AI icin access token alir."""
        import os

        creds_file = self._settings.firebase_credentials_file
        if not creds_file:
            creds_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if creds_file and os.path.exists(creds_file):
            credentials = service_account.Credentials.from_service_account_file(
                creds_file,
                scopes=self.VERTEX_SCOPES,
            )
        else:
            credentials, _ = google.auth.default(scopes=self.VERTEX_SCOPES)

        # Refresh token if needed
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)

        return credentials.token

    def _get_vertex_endpoint(self) -> str:
        """Vertex AI endpoint URL olusturur."""
        model_settings = get_model_settings()
        region = self._settings.gcp_location or "us-central1"
        project_id = self._settings.gcp_project_id
        model_id = model_settings.vertex_video_model or self.DEFAULT_VERTEX_MODEL

        base_url = self.VERTEX_BASE_URL.format(region=region)
        return f"{base_url}/projects/{project_id}/locations/{region}/publishers/google/models/{model_id}:predictLongRunning"

    def _firebase_path_to_gcs_uri(self, firebase_path: str) -> str:
        """Firebase Storage path'i GCS URI'ye cevirir."""
        bucket = self._settings.firebase_storage_bucket
        if bucket:
            # Remove gs:// prefix if present
            bucket = bucket.replace("gs://", "")
        return f"gs://{bucket}/{firebase_path}"

    async def generate_video_from_image(
        self,
        prompt: str,
        source_image_path: str,
        aspect_ratio: str = "16:9",
        duration_seconds: int = 8,
    ) -> bytes:
        """
        Image'dan video uretir (image-to-video) using Vertex AI.

        Args:
            prompt: Video icin aciklama.
            source_image_path: Firebase Storage path (e.g., images/abc123/photo.png).
            aspect_ratio: En-boy orani.
            duration_seconds: Video suresi.

        Returns:
            bytes: Uretilen videonun binary datasi.
        """
        # Get access token
        access_token = self._get_vertex_access_token()

        # Convert Firebase path to GCS URI
        gcs_uri = self._firebase_path_to_gcs_uri(source_image_path)

        # Build request
        endpoint = self._get_vertex_endpoint()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        payload = {
            "instances": [
                {
                    "prompt": prompt,
                    "image": {
                        "gcsUri": gcs_uri
                    }
                }
            ],
            "parameters": {
                "sampleCount": 1,
                "videoLength": f"{duration_seconds}s",
                "aspectRatio": aspect_ratio,
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Start long-running operation
            response = await client.post(
                endpoint,
                headers=headers,
                json=payload,
            )
            if response.status_code != 200:
                error_detail = response.text
                # 403 hatasi icin ozel mesaj
                if response.status_code == 403 and "API has not been used" in error_detail:
                    raise RuntimeError(
                        f"Vertex AI API etkinlestirilmemis! "
                        f"GCP Console'da Vertex AI API'yi etkinlestirin: "
                        f"https://console.cloud.google.com/apis/api/aiplatform.googleapis.com "
                        f"Proje: {self._settings.gcp_project_id}. "
                        f"Detay: {error_detail}"
                    )
                raise RuntimeError(f"Vertex AI Error {response.status_code}: {error_detail}")

            data = response.json()
            operation_name = data.get("name")
            if not operation_name:
                raise RuntimeError(f"Operation name not found in response: {data}")

        # Poll for completion
        video_gcs_uri = await self._poll_vertex_operation(operation_name, access_token)

        # Download video from GCS
        video_bytes = await self._download_video_from_gcs(video_gcs_uri, access_token)

        return video_bytes

    async def _poll_vertex_operation(self, operation_name: str, access_token: str) -> str:
        """
        Vertex AI long-running operation'i poll eder ve video GCS URI dondurur.

        Args:
            operation_name: Operation name from initial request.
            access_token: Vertex AI access token.

        Returns:
            str: Video GCS URI.
        """
        region = self._settings.gcp_location or "us-central1"
        base_url = self.VERTEX_BASE_URL.format(region=region)
        poll_url = f"{base_url}/{operation_name}"

        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(self.MAX_POLL_ATTEMPTS):
                response = await client.get(poll_url, headers=headers)
                if response.status_code != 200:
                    error_detail = response.text
                    raise RuntimeError(f"Poll Error {response.status_code}: {error_detail}")

                data = response.json()
                is_done = data.get("done", False)

                if is_done:
                    # Check for error
                    if "error" in data:
                        error = data["error"]
                        raise RuntimeError(f"Video generation failed: {error}")

                    # Extract video GCS URI from response
                    # Response format: {"done": true, "response": {"predictions": [{"video": {"gcsUri": "..."}}]}}
                    predictions = data.get("response", {}).get("predictions", [])
                    if predictions:
                        video_gcs_uri = predictions[0].get("video", {}).get("gcsUri")
                        if video_gcs_uri:
                            return video_gcs_uri

                    raise RuntimeError(f"Video GCS URI not found in response: {data}")

                # Wait before next poll
                await asyncio.sleep(self.POLL_INTERVAL)

        raise TimeoutError(f"Video generation timed out after {self.MAX_POLL_ATTEMPTS * self.POLL_INTERVAL} seconds")

    async def _download_video_from_gcs(self, gcs_uri: str, access_token: str) -> bytes:
        """
        GCS URI'den video indirir.

        Args:
            gcs_uri: GCS URI (gs://bucket/path/video.mp4).
            access_token: Google Cloud access token.

        Returns:
            bytes: Video binary data.
        """
        # Parse GCS URI: gs://bucket/path/to/file
        if not gcs_uri.startswith("gs://"):
            raise ValueError(f"Invalid GCS URI: {gcs_uri}")

        path = gcs_uri[5:]  # Remove "gs://"
        bucket_name, *object_parts = path.split("/")
        object_name = "/".join(object_parts)

        # Use GCS JSON API to download
        download_url = f"https://storage.googleapis.com/storage/v1/b/{bucket_name}/o/{object_name.replace('/', '%2F')}?alt=media"

        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            response = await client.get(download_url, headers=headers)
            if response.status_code != 200:
                error_detail = response.text
                raise RuntimeError(f"GCS download error {response.status_code}: {error_detail}")

            return response.content

    async def _poll_operation(self, operation_name: str) -> str:
        """
        Long-running operation'i poll eder ve video URI dondurur.

        Args:
            operation_name: Operation name from initial request.

        Returns:
            str: Video download URI.
        """
        import asyncio

        poll_url = f"{self.BASE_URL}/{operation_name}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(self.MAX_POLL_ATTEMPTS):
                response = await client.get(
                    poll_url,
                    headers={"x-goog-api-key": self._api_key},
                )
                if response.status_code != 200:
                    error_detail = response.text
                    raise RuntimeError(f"Poll Error {response.status_code}: {error_detail}")

                data = response.json()
                is_done = data.get("done", False)

                if is_done:
                    # Check for error
                    if "error" in data:
                        error = data["error"]
                        raise RuntimeError(f"Video generation failed: {error}")

                    # Extract video URI
                    video_uri = (
                        data.get("response", {})
                        .get("generateVideoResponse", {})
                        .get("generatedSamples", [{}])[0]
                        .get("video", {})
                        .get("uri")
                    )
                    if not video_uri:
                        raise RuntimeError(f"Video URI not found in response: {data}")

                    return video_uri

                # Wait before next poll
                await asyncio.sleep(self.POLL_INTERVAL)

        raise TimeoutError(f"Video generation timed out after {self.MAX_POLL_ATTEMPTS * self.POLL_INTERVAL} seconds")

    async def _download_video(self, video_uri: str) -> bytes:
        """
        Video URI'den video indirir.

        Args:
            video_uri: Video download URI.

        Returns:
            bytes: Video binary data.
        """
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response = await client.get(
                video_uri,
                headers={"x-goog-api-key": self._api_key},
            )
            if response.status_code != 200:
                error_detail = response.text
                raise RuntimeError(f"Video download error {response.status_code}: {error_detail}")

            return response.content


@lru_cache(maxsize=1)
def get_image_generation_client() -> ImageGenerationClient:
    """ImageGenerationClient instance dondurur (cached)."""
    return ImageGenerationClient()


@lru_cache(maxsize=1)
def get_video_generation_client() -> VideoGenerationClient:
    """VideoGenerationClient instance dondurur (cached)."""
    return VideoGenerationClient()


__all__ = [
    "ImageGenerationClient",
    "VideoGenerationClient",
    "get_image_generation_client",
    "get_video_generation_client",
]
