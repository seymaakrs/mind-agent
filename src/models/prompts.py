"""
Structured prompt models for image and video generation.

These models define the JSON structure that agents use internally
for prompt engineering before calling generation tools.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImagePrompt(BaseModel):
    """Structured prompt for image generation."""

    scene: str = Field(
        description="Main scene description in 2-3 detailed sentences. "
        "Describe what is happening, the setting, and key elements."
    )
    subject: str = Field(
        description="Primary subject or focal point of the image. "
        "Be specific about appearance, position, and state."
    )
    style: str = Field(
        description="Artistic style (e.g., 'minimalist flat design', 'photorealistic', "
        "'watercolor illustration', '3D render', 'corporate professional')."
    )
    colors: list[str] = Field(
        description="Dominant colors to use. Include brand colors if available. "
        "Use specific names or hex codes (e.g., '#FF5733', 'deep navy blue')."
    )
    mood: str = Field(
        description="Emotional atmosphere (e.g., 'energetic and dynamic', "
        "'calm and professional', 'luxurious and elegant', 'friendly and approachable')."
    )
    composition: str = Field(
        description="Visual arrangement (e.g., 'centered with symmetric balance', "
        "'rule of thirds with subject on left', 'diagonal dynamic composition')."
    )
    lighting: str = Field(
        description="Lighting setup (e.g., 'soft natural daylight from upper left', "
        "'dramatic rim lighting', 'flat even studio lighting', 'golden hour warm glow')."
    )
    background: str = Field(
        description="Background details (e.g., 'gradient from navy to light blue', "
        "'blurred office environment', 'solid white with subtle shadow', 'abstract geometric shapes')."
    )
    text_elements: str | None = Field(
        default=None,
        description="Any text to include in the image (brand name, slogan, call-to-action). "
        "Specify font style preference if relevant."
    )
    additional_details: str | None = Field(
        default=None,
        description="Extra details, effects, or specific requirements "
        "(e.g., 'include subtle lens flare', 'add grain texture', 'ensure logo is prominent')."
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


__all__ = ["ImagePrompt", "VideoPrompt"]
