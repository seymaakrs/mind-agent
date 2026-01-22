from __future__ import annotations

import re
from typing import Any

from agents import FunctionTool, function_tool

from src.infra.firebase_client import get_storage_client, get_document_client, save_media_record
from src.infra.google_ai_client import get_image_generation_client
from src.models.prompts import ImagePrompt




@function_tool(
    name_override="generate_image",
    description_override=(
        "Generates or edits images based on structured prompt data. This is the ONLY tool for image tasks. "
        "\n\n"
        "INPUT - prompt_data (ImagePrompt): You MUST provide ALL required fields: "
        "- scene: Main scene description (2-3 sentences) "
        "- subject: Primary subject/focal point "
        "- style: Artistic style (e.g., 'minimalist flat design', 'photorealistic') "
        "- colors: List of dominant colors (use brand colors, be specific like '#FF5733') "
        "- mood: Emotional atmosphere (e.g., 'professional and calm') "
        "- composition: Visual arrangement (e.g., 'rule of thirds', 'centered') "
        "- lighting: Lighting setup (e.g., 'soft natural daylight', 'dramatic rim lighting') "
        "- background: Background details "
        "- text_elements: (optional) Text to include "
        "- additional_details: (optional) Extra effects or requirements "
        "\n\n"
        "business_id: REQUIRED if available in context. The business ID for organizing files. "
        "\n\n"
        "WHEN TO USE source_file_path: "
        "If the task mentions using an existing image (logo, asset) - provide the Firebase Storage path. "
        "Keywords: 'use logo', 'place logo', 'include logo', 'combine with', 'overlay'. "
        "\n\n"
        "WHEN TO LEAVE source_file_path EMPTY: "
        "If creating a completely NEW image from scratch without referencing existing images."
        "\n\n"
        "aspect_ratio: Image aspect ratio. Options: '1:1' (square), '16:9' (widescreen), '9:16' (portrait), '4:3', '3:4'. Default: '1:1'."
    ),
    strict_mode=False,
)
async def generate_image(
    prompt_data: ImagePrompt,
    file_name: str,
    business_id: str | None = None,
    source_file_path: str | None = None,
    aspect_ratio: str = "1:1",
) -> dict[str, str | bool]:
    """
    Generate a new image or edit/combine with an existing image.

    Args:
        prompt_data: Structured ImagePrompt with all visual details.
        file_name: Name to save the generated image as in Firebase Storage.
        business_id: Business ID for organizing files under business/{id}/images/.
        source_file_path: Optional. Firebase Storage path of source image to use (e.g., logo).
                          If provided, the image will be edited/combined with this source.
                          If None, a completely new image will be generated.
        aspect_ratio: Image aspect ratio ("1:1", "16:9", "9:16", "4:3", "3:4"). Default is "1:1".
    """
    image_client = get_image_generation_client()
    storage_client = get_storage_client()

    # Convert structured prompt to string
    prompt = prompt_data.to_prompt_string()

    try:
        if source_file_path:
            # Edit/combine mode - use existing image as source
            source_image = storage_client.download_file(source_file_path)
            images = await image_client.edit_image(
                prompt=prompt,
                source_image=source_image,
                aspect_ratio=aspect_ratio,
            )
            message = "Gorsel duzenlendi ve kaydedildi"
        else:
            # Generate mode - create new image from scratch
            images = await image_client.generate_image(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
            )
            message = "Gorsel olusturuldu"

        if not images:
            return {"success": False, "error": "Gorsel uretilemedi."}

        # Upload first image to Firebase Storage
        image_data = images[0]
        if business_id:
            destination_path = f"images/{business_id}/{file_name}"
        else:
            destination_path = f"images/{file_name}"
        upload_result = storage_client.upload_file(
            file_data=image_data,
            destination_path=destination_path,
            content_type="image/png",
        )

        # Media kaydini Firestore'a yaz (business_id varsa)
        if business_id:
            try:
                save_media_record(
                    business_id=business_id,
                    media_type="image",
                    storage_path=upload_result["path"],
                    public_url=upload_result["public_url"],
                    file_name=file_name,
                    prompt_summary=prompt_data.scene[:200] if prompt_data.scene else None,
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
        return {"success": False, "error": f"Servis hatasi (image): {type(exc).__name__}: {exc}"}


def get_image_tools() -> list[FunctionTool]:
    """Image agent icin kullanilabilir tool listesi."""
    return [generate_image]


__all__ = ["generate_image", "get_image_tools"]
