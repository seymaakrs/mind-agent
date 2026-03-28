"""
Structured prompt models for image and video generation.

These models define the JSON structure that agents use internally
for prompt engineering before calling generation tools.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, Field, create_model
from pydantic.fields import FieldInfo

if TYPE_CHECKING:
    from src.app.config import AgentInstructionConfig


class ImagePrompt(BaseModel):
    """Structured prompt for image generation."""

    scene: str = Field(
        description="Main scene description in 2-3 detailed sentences. "
        "Describe what is happening, the setting, and key elements.",
        examples=[
            "A surreal, three-dimensional environment that reflects creativity and digital agency dynamism. "
            "Abstract 3D objects float in an infinite studio space, blending artistic energy with modern digital aesthetics."
        ],
    )
    subject: str = Field(
        description="Primary subject or focal point of the image. "
        "Be specific about appearance, position, and state.",
        examples=[
            "Dark matte blue (#111121) dominant 3D main objects with integrated light green (#c1ff72) "
            "design elements symbolizing creativity, positioned off-center toward rule-of-thirds intersections."
        ],
    )
    style: str = Field(
        description="Artistic style (e.g., 'minimalist flat design', 'photorealistic', "
        "'watercolor illustration', '3D render', 'corporate professional').",
        examples=["High-quality 3D render blending surrealism and pop art aesthetics"],
    )
    colors: list[str] = Field(
        description="Dominant colors to use. Include brand colors if available. "
        "Use specific names or hex codes (e.g., '#FF5733', 'deep navy blue').",
        examples=[["#c1ff72", "#eeede9", "#c0bfbf", "#111121", "#221f5f", "#322fae"]],
    )
    mood: str = Field(
        description="Emotional atmosphere (e.g., 'energetic and dynamic', "
        "'calm and professional', 'luxurious and elegant', 'friendly and approachable').",
        examples=["Energetic, innovative, and eye-catching"],
    )
    composition: str = Field(
        description="Visual arrangement (e.g., 'centered with symmetric balance', "
        "'rule of thirds with subject on left', 'diagonal dynamic composition').",
        examples=[
            "Asymmetric and energetic composition placed off-center at rule-of-thirds intersections, "
            "with leading space and diagonal support. Clean and wide negative space reserved for text overlays."
        ],
    )
    lighting: str = Field(
        description="Lighting setup (e.g., 'soft natural daylight from upper left', "
        "'dramatic rim lighting', 'flat even studio lighting', 'golden hour warm glow').",
        examples=[
            "Colorful neon rim lighting on the edges of objects using light green (#c1ff72) and blue tones, "
            "creating a vibrant glow that separates subjects from the background."
        ],
    )
    background: str = Field(
        description="Background details (e.g., 'gradient from navy to light blue', "
        "'blurred office environment', 'solid white with subtle shadow', 'abstract geometric shapes').",
        examples=[
            "Studio infinity backdrop using only light yellow (#eeede9) and light gray (#c0bfbf) tones, "
            "completely textureless with smooth, clean gradient transitions."
        ],
    )
    text_elements: str | None = Field(
        default=None,
        description="Any text to include in the image (brand name, slogan, call-to-action). "
        "Specify font style preference if relevant.",
        examples=[
            "Dark blue (#221f5f) main headline and blue (#322fae) subheading positioned in the negative space, "
            "following consistent typographic hierarchy."
        ],
    )
    additional_details: str | None = Field(
        default=None,
        description="Extra details, effects, or specific requirements "
        "(e.g., 'include subtle lens flare', 'add grain texture', 'ensure logo is prominent').",
        examples=[
            "Small bright green and blue abstract floating particles hovering around the main object, "
            "combined with a subtle digital glitch/distortion effect across the image. "
            "Color palette and tonal unity must be strictly maintained throughout."
        ],
    )

    def to_prompt_string(self) -> str:
        """Convert structured prompt to a single detailed prompt string."""
        parts = [
            f"Scene: {self.scene}",
            f"Subject: {self.subject}",
            f"Style: {self.style}",
            f"Colors: {', '.join(self.colors)}",
            f"Mood: {self.mood}",
            f"Composition: {self.composition}",
            f"Lighting: {self.lighting}",
            f"Background: {self.background}",
        ]
        if self.text_elements:
            parts.append(f"Text elements: {self.text_elements}")
        if self.additional_details:
            parts.append(f"Additional: {self.additional_details}")

        return ". ".join(parts)


class VideoPrompt(BaseModel):
    """Structured prompt for video generation."""

    concept: str = Field(
        description="Overall video concept in 2-3 sentences. "
        "Describe the narrative arc or main idea."
    )
    opening_scene: str = Field(
        description="How the video starts. Describe the first 1-2 seconds in detail."
    )
    main_action: str = Field(
        description="Primary action or movement that occurs. "
        "Be specific about what moves, transforms, or changes."
    )
    closing_scene: str = Field(
        description="How the video ends. Describe the final frames."
    )
    visual_style: str = Field(
        description="Overall visual aesthetic (e.g., 'cinematic with shallow depth of field', "
        "'clean motion graphics', 'documentary style', 'animated explainer')."
    )
    color_palette: list[str] = Field(
        description="Primary colors throughout the video. Include brand colors if available."
    )
    mood_atmosphere: str = Field(
        description="Emotional tone (e.g., 'inspiring and uplifting', "
        "'professional and trustworthy', 'exciting and energetic')."
    )
    camera_movement: str = Field(
        description="Camera behavior (e.g., 'slow push in', 'static wide shot', "
        "'orbiting around subject', 'tracking shot following action', 'smooth dolly zoom')."
    )
    lighting_style: str = Field(
        description="Lighting approach (e.g., 'bright and airy', 'moody with contrast', "
        "'natural outdoor lighting', 'studio three-point setup')."
    )
    pacing: str = Field(
        description="Speed and rhythm (e.g., 'slow and contemplative', "
        "'fast-paced with quick cuts', 'steady medium pace', 'building crescendo')."
    )
    transitions: str | None = Field(
        default=None,
        description="Transition effects if multiple scenes (e.g., 'smooth crossfade', "
        "'quick cut', 'morph transition', 'zoom through')."
    )
    text_overlays: str | None = Field(
        default=None,
        description="Any text or titles to appear (brand name, tagline, call-to-action). "
        "Specify timing and animation style."
    )
    audio_suggestion: str | None = Field(
        default=None,
        description="Suggested audio/music style to complement visuals "
        "(e.g., 'upbeat corporate music', 'ambient electronic', 'no audio needed')."
    )
    additional_effects: str | None = Field(
        default=None,
        description="Special effects or post-processing "
        "(e.g., 'subtle particle effects', 'film grain', 'light leaks', 'slow motion moments')."
    )

    def to_prompt_string(self) -> str:
        """
        Convert structured prompt to a Veo-optimized prompt string.
        
        Veo works best with:
        - Clear, action-focused descriptions
        - Natural flowing language
        - Explicit camera and lighting directions
        """
        # Build a natural, flowing prompt that Veo understands well
        parts = []
        
        # Start with the main action and concept (most important for Veo)
        parts.append(self.concept)
        parts.append(f"The video opens with: {self.opening_scene}")
        parts.append(f"Main action: {self.main_action}")
        parts.append(f"The video ends with: {self.closing_scene}")
        
        # Add cinematic details
        parts.append(f"Visual style: {self.visual_style}")
        parts.append(f"Camera movement: {self.camera_movement}")
        parts.append(f"Lighting: {self.lighting_style}")
        parts.append(f"Mood and atmosphere: {self.mood_atmosphere}")
        parts.append(f"Color palette: {', '.join(self.color_palette)}")
        parts.append(f"Pacing: {self.pacing}")
        
        # Optional elements
        if self.transitions:
            parts.append(f"Transitions: {self.transitions}")
        if self.text_overlays:
            parts.append(f"Text overlays: {self.text_overlays}")
        if self.additional_effects:
            parts.append(f"Special effects: {self.additional_effects}")

        return ". ".join(parts)


# ---------------------------------------------------------------------------
# Dynamic prompt model builders
# ---------------------------------------------------------------------------


def _extract_field_kwargs(field_info: FieldInfo) -> dict[str, Any]:
    """Mevcut FieldInfo'dan yeni Field() icin kullanilabilir keyword arg'lari cikarir."""
    kwargs: dict[str, Any] = {}
    if field_info.description is not None:
        kwargs["description"] = field_info.description
    if field_info.examples is not None:
        kwargs["examples"] = field_info.examples
    return kwargs


def _build_dynamic_model(
    base_model: type[BaseModel],
    config: AgentInstructionConfig,
    dynamic_name: str,
) -> type[BaseModel]:
    """
    Base model uzerinde Firebase config'den gelen description/examples override'lari uygular.

    Pydantic create_model ile yeni bir sinif uretir. Override yoksa orijinal model doner.
    to_prompt_string() metodu miras yoluyla korunur.
    """
    if not config.prompt_fields:
        return base_model

    field_overrides: dict[str, Any] = {}

    for field_name, field_config in config.prompt_fields.items():
        if field_name not in base_model.model_fields:
            continue  # Bilinmeyen field — sessizce atla

        original = base_model.model_fields[field_name]
        original_kwargs = _extract_field_kwargs(original)

        # Override sadece verilen alanlari degistirir
        new_kwargs = {**original_kwargs}
        if field_config.description:
            new_kwargs["description"] = field_config.description
        if field_config.examples:
            new_kwargs["examples"] = field_config.examples

        # Sadece gercekten degisen field'lari override et
        if new_kwargs != original_kwargs:
            field_overrides[field_name] = (
                original.annotation,
                Field(default=original.default, **new_kwargs),
            )

    if not field_overrides:
        return base_model

    return create_model(
        dynamic_name,
        __base__=base_model,
        **field_overrides,
    )


def build_image_prompt_model(config: AgentInstructionConfig) -> type[ImagePrompt]:
    """Firebase config ile override edilmis ImagePrompt modeli olusturur."""
    return _build_dynamic_model(ImagePrompt, config, "DynamicImagePrompt")


def build_video_prompt_model(config: AgentInstructionConfig) -> type[VideoPrompt]:
    """Firebase config ile override edilmis VideoPrompt modeli olusturur."""
    return _build_dynamic_model(VideoPrompt, config, "DynamicVideoPrompt")


__all__ = [
    "ImagePrompt",
    "VideoPrompt",
    "build_image_prompt_model",
    "build_video_prompt_model",
]
