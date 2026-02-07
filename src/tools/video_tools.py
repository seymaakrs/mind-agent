from __future__ import annotations

from agents import FunctionTool, function_tool

from src.app.config import get_settings
from src.infra.firebase_client import get_storage_client, save_media_record, save_dry_run_log
from src.infra.google_ai_client import get_video_generation_client
from src.models.prompts import VideoPrompt


def _count_tokens(text: str) -> int:
    """Tahmini token sayisini hesaplar (tiktoken cl100k_base encoding)."""
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except ImportError:
        # tiktoken yoksa basit tahmin: ~4 karakter = 1 token
        return len(text) // 4


@function_tool(
    name_override="generate_video",
    description_override=(
        "Generates a video based on structured prompt data using Google Veo 3.1. "
        "The video will be saved to Firebase Storage and the URL will be returned. "
        "\n\n"
        "INPUT - prompt_data (VideoPrompt): You MUST provide ALL required fields: "
        "- concept: Overall video concept (2-3 sentences) "
        "- opening_scene: How the video starts (first 1-2 seconds) "
        "- main_action: Primary action/movement that occurs "
        "- closing_scene: How the video ends (final frames) "
        "- visual_style: Overall aesthetic (e.g., 'cinematic', 'motion graphics') "
        "- color_palette: List of primary colors (use brand colors) "
        "- mood_atmosphere: Emotional tone (e.g., 'inspiring', 'professional') "
        "- camera_movement: Camera behavior (e.g., 'slow push in', 'tracking shot') "
        "- lighting_style: Lighting approach (e.g., 'bright and airy', 'dramatic') "
        "- pacing: Speed and rhythm (e.g., 'slow and contemplative', 'fast-paced') "
        "- transitions: (optional) Effects between scenes "
        "- text_overlays: (optional) Text/titles to appear "
        "- audio_suggestion: (optional) Music style suggestion "
        "- additional_effects: (optional) Special effects "
        "\n\n"
        "aspect_ratio: Video aspect ratio. Use '9:16' for Instagram Reels/Stories (VERTICAL), '16:9' for YouTube (HORIZONTAL). Default is '9:16' for social media."
        "\n\n"
        "duration_seconds: Video length in seconds. Default is 8 seconds. Instagram Reels can be up to 90 seconds."
        "\n\n"
        "business_id: REQUIRED if available in context. The business ID for organizing files. "
        "\n\n"
        "WHEN TO USE source_file_path: "
        "If you want to create a video from an existing image (image-to-video). "
        "\n\n"
        "Returns the generated video info including path and public_url."
    ),
    strict_mode=False,
)
async def generate_video(
    prompt_data: VideoPrompt,
    file_name: str,
    business_id: str | None = None,
    source_file_path: str | None = None,
    aspect_ratio: str = "9:16",  # Default vertical for Instagram Reels
    duration_seconds: int = 8,
) -> dict[str, str | bool]:
    """
    Generate a video using Google Veo 3.1.

    Args:
        prompt_data: Structured VideoPrompt with all cinematic details.
        file_name: Name to save the generated video as in Firebase Storage.
        business_id: Business ID for organizing files under videos/{id}/.
        source_file_path: Optional. Firebase Storage path of source image for image-to-video.
        aspect_ratio: Video aspect ratio ("9:16" for vertical, "16:9" for horizontal).
        duration_seconds: Video length in seconds (default 8).

    Returns:
        dict with success, path, public_url, and fileName.
    """
    settings = get_settings()

    # Convert structured prompt to string
    prompt = prompt_data.to_prompt_string()

    # DRY-RUN MODE: Log prompt without calling Google API
    if settings.dry_run:
        token_count = _count_tokens(prompt)
        print(f"[DRY-RUN] Video prompt token count: {token_count}")
        print(f"[DRY-RUN] Full prompt:\n{prompt[:500]}...")

        # Save to Firestore for analysis
        if business_id:
            try:
                save_dry_run_log(
                    business_id=business_id,
                    media_type="video",
                    prompt_data=prompt_data.model_dump(),
                    full_prompt=prompt,
                    token_count=token_count,
                    file_name=file_name,
                    aspect_ratio=aspect_ratio,
                    duration_seconds=duration_seconds,
                )
            except Exception as e:
                print(f"[DRY-RUN] Firestore log hatasi: {e}")

        return {
            "success": True,
            "message": f"[DRY-RUN] Video uretimi simule edildi. Token sayisi: {token_count}",
            "path": f"[DRY-RUN] videos/{business_id or 'unknown'}/{file_name}",
            "public_url": "[DRY-RUN] No actual video generated",
            "fileName": file_name,
            "dry_run": True,
            "token_count": token_count,
        }

    # NORMAL MODE: Call Google API
    video_client = get_video_generation_client()
    storage_client = get_storage_client()

    try:
        # source_file_path sadece gercek bir path ise kullan
        use_image_to_video = bool(source_file_path and source_file_path.strip())

        if use_image_to_video:
            # Image-to-video mode (using Vertex AI)
            print(f"[video_tools] Image-to-video mode: source={source_file_path}")
            video_data = await video_client.generate_video_from_image(
                prompt=prompt,
                source_image_path=source_file_path.strip(),
                aspect_ratio=aspect_ratio,
                duration_seconds=duration_seconds,
            )
            message = "Video gorsel uzerinden olusturuldu"
        else:
            # Text-to-video mode (using Veo 3.1)
            print(f"[video_tools] Text-to-video mode: aspect={aspect_ratio}, duration={duration_seconds}s")
            video_data = await video_client.generate_video(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                duration_seconds=duration_seconds,
            )
            message = "Video olusturuldu"

        # Upload video to Firebase Storage
        if business_id:
            destination_path = f"videos/{business_id}/{file_name}"
        else:
            destination_path = f"videos/{file_name}"
        upload_result = storage_client.upload_file(
            file_data=video_data,
            destination_path=destination_path,
            content_type="video/mp4",
        )

        # Media kaydini Firestore'a yaz (business_id varsa)
        if business_id:
            try:
                save_media_record(
                    business_id=business_id,
                    media_type="video",
                    storage_path=upload_result["path"],
                    public_url=upload_result["public_url"],
                    file_name=file_name,
                    prompt_summary=prompt_data.concept[:200] if prompt_data.concept else None,
                )
            except Exception:
                pass  # Media kaydi basarisiz olsa bile ana islem basarili

        return {
            "success": True,
            "message": message,
            "path": upload_result["path"],
            "public_url": upload_result["public_url"],
            "fileName": file_name,
        }

    except Exception as exc:
        return {
            "success": False,
            "error": f"Servis hatasi (video): {type(exc).__name__}: {exc}",
        }


@function_tool(
    name_override="add_audio_to_video",
    description_override=(
        "Adds AI-generated audio/sound effects to an existing video using fal.ai MMAudio V2. "
        "The model analyzes the video content and generates synchronized audio based on the text prompt. "
        "\n\n"
        "PARAMETERS:\n"
        "- video_url (REQUIRED): Public URL of the video (mp4, mov, webm, m4v, gif). "
        "Use the public_url from generate_video output or any publicly accessible video URL.\n"
        "- prompt (REQUIRED): Description of desired audio (e.g., 'gentle ocean waves', 'upbeat electronic music').\n"
        "- business_id: Business ID for saving result to Firebase Storage. "
        "If provided with file_name, the result video will be uploaded for persistence.\n"
        "- file_name: File name for Firebase Storage upload (e.g., 'video_with_audio.mp4').\n"
        "- negative_prompt: Sounds to exclude (e.g., 'no speech, no music'). Default: empty.\n"
        "- num_steps: Inference quality steps (4-50, higher=better but slower). Default: 25.\n"
        "- duration: Audio duration in seconds (1-30). Should match the video length. Default: 8.\n"
        "- cfg_strength: Prompt vs video balance (0-20). "
        "Higher = follows prompt more, lower = follows video content more. Default: 4.5.\n"
        "\n\n"
        "Returns the video URL with generated audio. If business_id and file_name are provided, "
        "also uploads to Firebase Storage and returns the persistent public_url."
    ),
    strict_mode=False,
)
async def add_audio_to_video(
    video_url: str,
    prompt: str,
    business_id: str | None = None,
    file_name: str | None = None,
    negative_prompt: str = "",
    num_steps: int = 25,
    duration: float = 8,
    cfg_strength: float = 4.5,
) -> dict[str, str | bool]:
    """
    Add AI-generated audio to a video using fal.ai MMAudio V2.

    Args:
        video_url: Public URL of the source video.
        prompt: Description of desired audio/sounds.
        business_id: Optional business ID for Firebase Storage upload.
        file_name: Optional file name for Firebase Storage upload.
        negative_prompt: Sounds to avoid.
        num_steps: Inference steps (4-50).
        duration: Audio duration in seconds (1-30).
        cfg_strength: Prompt adherence (0-20).

    Returns:
        dict with success, video_url, and optionally path/public_url if uploaded to Firebase.
    """
    import asyncio
    import os

    settings = get_settings()

    # DRY-RUN MODE
    if settings.dry_run:
        return {
            "success": True,
            "message": f"[DRY-RUN] Audio ekleme simule edildi. Prompt: {prompt[:100]}",
            "video_url": "[DRY-RUN] No actual audio generated",
            "dry_run": True,
        }

    # Ensure FAL_KEY is set in environment for fal-client library
    if settings.fal_key and not os.getenv("FAL_KEY"):
        os.environ["FAL_KEY"] = settings.fal_key

    try:
        import fal_client
    except ImportError:
        return {
            "success": False,
            "error": "fal-client kutuphanesi yuklenmemis. 'pip install fal-client' calistirin.",
        }

    try:
        print(f"[video_tools] Adding audio to video: prompt='{prompt[:60]}...', duration={duration}s")

        # Call fal.ai MMAudio V2 via queue (subscribe handles polling automatically)
        result = await asyncio.to_thread(
            fal_client.subscribe,
            "fal-ai/mmaudio-v2",
            arguments={
                "video_url": video_url,
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "num_steps": num_steps,
                "duration": duration,
                "cfg_strength": cfg_strength,
            },
        )

        result_video_url = result["video"]["url"]

        response: dict[str, str | bool | int | None] = {
            "success": True,
            "message": "Video'ya ses eklendi",
            "video_url": result_video_url,
            "file_size": result["video"].get("file_size"),
        }

        # Upload to Firebase Storage for persistence (fal.ai CDN URLs are temporary)
        if business_id and file_name:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=120) as client:
                    dl_resp = await client.get(result_video_url)
                    dl_resp.raise_for_status()
                    video_data = dl_resp.content

                storage_client = get_storage_client()
                destination_path = f"videos/{business_id}/{file_name}"
                upload_result = storage_client.upload_file(
                    file_data=video_data,
                    destination_path=destination_path,
                    content_type="video/mp4",
                )

                try:
                    save_media_record(
                        business_id=business_id,
                        media_type="video",
                        storage_path=upload_result["path"],
                        public_url=upload_result["public_url"],
                        file_name=file_name,
                        prompt_summary=f"Audio added: {prompt[:200]}",
                    )
                except Exception:
                    pass

                response["path"] = upload_result["path"]
                response["public_url"] = upload_result["public_url"]
                response["fileName"] = file_name
                response["message"] = "Video'ya ses eklendi ve Firebase'e yuklendi"

            except Exception as e:
                response["upload_error"] = f"Firebase yukleme hatasi: {e}"
                response["message"] = "Video'ya ses eklendi (Firebase yukleme basarisiz, fal.ai URL gecici)"

        return response

    except Exception as exc:
        return {
            "success": False,
            "error": f"Ses ekleme hatasi: {type(exc).__name__}: {exc}",
        }


def get_video_tools() -> list[FunctionTool]:
    """Video agent icin kullanilabilir tool listesi."""
    return [generate_video, add_audio_to_video]


__all__ = ["generate_video", "add_audio_to_video", "get_video_tools"]
