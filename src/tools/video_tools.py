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


def get_video_tools() -> list[FunctionTool]:
    """Video agent icin kullanilabilir tool listesi."""
    return [generate_video]


__all__ = ["generate_video", "get_video_tools"]
