import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.config import OPENAI_API_KEY


SUPPORTED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

DEFAULT_VISION_MODEL = "gpt-4.1-mini"


def encode_image_as_data_url(image_path: Path) -> str:
    """Convert a supported local image into a Base64 data URL."""

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image file not found: {image_path}"
        )

    mime_type, _ = mimetypes.guess_type(image_path.name)

    if mime_type not in SUPPORTED_IMAGE_TYPES:
        raise ValueError(
            "Unsupported image format. Use JPG, JPEG, PNG, or WEBP."
        )

    image_bytes = image_path.read_bytes()
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    return f"data:{mime_type};base64,{encoded_image}"


def build_vision_instructions(
    system_prompt: str,
    vision_schema: dict[str, Any],
) -> str:
    """Combine the system prompt with the vision-output structure."""

    schema_text = json.dumps(
        vision_schema,
        ensure_ascii=False,
        indent=2,
    )

    return (
        f"{system_prompt}\n\n"
        "For this image-analysis stage, return observations only. "
        "Do not assign a Kitami waste category, bag, or "
        "collection date.\n\n"
        "Return valid JSON matching this structure:\n"
        f"{schema_text}"
    )


def clean_json_response(response_text: str) -> str:
    """Remove optional Markdown code fences from a model response."""

    cleaned_text = response_text.strip()

    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[len("```json"):].strip()
    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[len("```"):].strip()

    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3].strip()

    return cleaned_text


def analyze_image(
    image_path: Path,
    system_prompt: str,
    vision_schema: dict[str, Any],
    user_text: str | None = None,
    model: str = DEFAULT_VISION_MODEL,
) -> dict[str, Any]:
    """
    Analyze one waste-item image using the OpenAI API.

    This function returns visual observations only.
    It does not assign a Kitami waste category.
    """

    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY was not found. "
            "Check the private .env file."
        )

    client = OpenAI(api_key=OPENAI_API_KEY)

    image_data_url = encode_image_as_data_url(image_path)

    instructions = build_vision_instructions(
        system_prompt=system_prompt,
        vision_schema=vision_schema,
    )

    if user_text and user_text.strip():
        user_request = user_text.strip()
    else:
        user_request = (
            "Analyze the main waste item in this photograph."
        )

    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": user_request,
                    },
                    {
                        "type": "input_image",
                        "image_url": image_data_url,
                        "detail": "high",
                    },
                ],
            }
        ],
    )

    response_text = clean_json_response(
        response.output_text
    )

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise ValueError(
            "The vision model did not return valid JSON."
        ) from error

    return result