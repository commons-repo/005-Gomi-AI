import json
from typing import Any

from openai import OpenAI

from app.config import OPENAI_API_KEY


DEFAULT_REPLY_MODEL = "gpt-4.1-mini"

ALLOWED_INTENTS = {
    "confirm",
    "correct",
    "reconsider",
    "unclear",
}


def clean_json_response(response_text: str) -> str:
    """Remove optional Markdown code fences."""

    cleaned_text = response_text.strip()

    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[
            len("```json"):
        ].strip()

    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[
            len("```"):
        ].strip()

    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3].strip()

    return cleaned_text


def summarize_proposed_recognition(
    vision_result: dict[str, Any],
) -> dict[str, Any]:
    """Extract the recognition facts needed to interpret a reply."""

    primary_object = vision_result.get(
        "primary_object",
        {},
    )

    components = vision_result.get(
        "components",
        [],
    )

    component_summaries = []

    if isinstance(components, list):
        for component in components:
            if not isinstance(component, dict):
                continue

            component_summaries.append(
                {
                    "name_en": component.get("name_en"),
                    "name_ja": component.get("name_ja"),
                    "function": component.get("function"),
                    "materials": component.get(
                        "materials",
                        [],
                    ),
                }
            )

    return {
        "name_en": primary_object.get("name_en"),
        "name_ja": primary_object.get("name_ja"),
        "function": primary_object.get("function"),
        "is_composite": primary_object.get(
            "is_composite",
            False,
        ),
        "components": component_summaries,
    }


def interpret_recognition_reply(
    proposed_recognition: dict[str, Any],
    user_reply: str,
    language_code: str = "en",
    model: str = DEFAULT_REPLY_MODEL,
) -> dict[str, Any]:
    """
    Interpret a natural reply to a recognition question.

    Possible intents:
    - confirm
    - correct
    - reconsider
    - unclear
    """

    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY was not found. "
            "Check the private .env file."
        )

    client = OpenAI(
        api_key=OPENAI_API_KEY
    )

    recognition_summary = (
        summarize_proposed_recognition(
            proposed_recognition
        )
    )

    instructions = """
You interpret a user's reply to an object-recognition
confirmation question.

The application has shown the user a proposed recognition
of a photographed household item and asked whether the
recognition is correct.

Classify the user's reply into exactly one intent:

1. confirm
   The user accepts the proposed recognition.

2. correct
   The user corrects, modifies, or adds an important detail
   to the proposed recognition.

3. reconsider
   The user asks the system to inspect the photograph again
   without providing a clear replacement description.

4. unclear
   The reply does not clearly confirm, correct, or request
   reconsideration.

Examples:

"Yes. Now okay."
→ confirm

"Close enough, yes."
→ confirm

"Correct, but there are three sheets."
→ correct

"No. These are loose papers."
→ correct

"It contains glue, not toothpaste."
→ correct

"Please look at the photograph again."
→ reconsider

"I do not understand the question."
→ unclear

Return valid JSON only:

{
  "intent": "confirm",
  "correction_text": null,
  "reason": ""
}

Rules:

- Do not perform waste classification.
- Do not provide disposal instructions.
- Preserve the user's correction faithfully.
- If the reply confirms but also changes an important fact,
  use "correct".
- If the intent is "correct", correction_text must contain
  the useful corrected description.
- If the intent is not "correct", correction_text must be null.
- Return no Markdown and no explanatory text outside the JSON.
""".strip()

    payload = {
        "language_code": language_code,
        "proposed_recognition": recognition_summary,
        "user_reply": user_reply,
    }

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

    response_text = clean_json_response(
        response.output_text
    )

    try:
        interpretation = json.loads(
            response_text
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            "The recognition-reply interpreter "
            "did not return valid JSON."
        ) from error

    intent = interpretation.get(
        "intent"
    )

    if intent not in ALLOWED_INTENTS:
        raise ValueError(
            f"Invalid recognition reply intent: {intent}"
        )

    correction_text = interpretation.get(
        "correction_text"
    )

    if intent == "correct":
        if not correction_text:
            correction_text = user_reply.strip()

    else:
        correction_text = None

    return {
        "intent": intent,
        "correction_text": correction_text,
        "reason": interpretation.get(
            "reason",
            "",
        ),
    }