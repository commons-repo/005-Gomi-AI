import json
from typing import Any

from openai import OpenAI

from app.config import OPENAI_API_KEY


DEFAULT_TEXT_RECOGNITION_MODEL = "gpt-4.1-mini"


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


def recognize_item_from_text(
    user_description: str,
    vision_schema: dict[str, Any],
    language_code: str = "en",
    previous_recognition: dict[str, Any] | None = None,
    model: str = DEFAULT_TEXT_RECOGNITION_MODEL,
) -> dict[str, Any]:
    """Convert a natural-language item description into recognition JSON."""
    if not user_description.strip():
        raise ValueError("A text description is required.")

    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY was not found. Check the private .env file."
        )

    client = OpenAI(api_key=OPENAI_API_KEY)

    payload = {
        "language_code": language_code,
        "user_description": user_description.strip(),
        "previous_recognition": previous_recognition,
        "required_output_structure": vision_schema,
    }

    instructions = """
You are the text-understanding component of the Kitami Gomi AI prototype.

The user describes a household item using ordinary conversational language.
Convert the description into the supplied recognition JSON structure.

This is recognition only. Do not decide:
- the waste category;
- the disposal bag or method;
- the collection date;
- any Kitami City rule.

Identify:
- the overall object;
- its function;
- whether it is composite;
- important separable components;
- stated materials;
- stated condition;
- whether contents remain;
- stated recycling marks;
- stated hazards;
- useful Japanese evidence-search concepts.

Rules:
- Treat facts explicitly stated by the user as confirmed facts.
- Do not invent materials, marks, conditions, sizes, or components.
- If a fact is unknown, record it as uncertain instead of guessing.
- If previous_recognition is supplied, update it using the user's latest
  correction or added detail. The latest explicit user statement takes priority.
- Keep components empty for a genuinely single-part object.
- Use practical Japanese terms and functional alternatives in
  evidence_search_concepts so official records can be retrieved later.
- Do not ask a disposal question at this stage.
- Set clarification.required only when the item itself cannot be understood
  well enough to present a recognition summary to the user.
- Return valid JSON only.
- Do not use Markdown fences or explanatory text outside the JSON.
- Follow the supplied output structure exactly.
""".strip()

    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(
                            payload,
                            ensure_ascii=False,
                            indent=2,
                        ),
                    }
                ],
            }
        ],
    )

    response_text = clean_json_response(response.output_text)

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise ValueError(
            "The text recognition service did not return valid JSON."
        ) from error

    if not isinstance(result, dict):
        raise ValueError("The text recognition result must be a JSON object.")

    primary_object = result.get("primary_object")
    if not isinstance(primary_object, dict):
        raise ValueError("The text recognition result has no primary_object.")

    if not primary_object.get("name_en") and not primary_object.get("name_ja"):
        raise ValueError("The recognized item name is missing.")

    return result
