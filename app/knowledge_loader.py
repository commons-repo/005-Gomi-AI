import json
from typing import Any

from app.config import (
    COLLECTION_SCHEDULE_PATH,
    ENGLISH_GUIDE_PATH,
    GENERAL_RULES_PATH,
    OUTPUT_SCHEMA_PATH,
    REASONING_SCHEMA_PATH,
    SYSTEM_PROMPT_PATH,
    VISION_SCHEMA_PATH,
    WASTE_DICTIONARY_PATH,
)


def load_text_file(file_path) -> str:
    """Load a UTF-8 text or Markdown file."""

    return file_path.read_text(encoding="utf-8")


def load_json_file(file_path) -> dict[str, Any]:
    """Load and parse a UTF-8 JSON file."""

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_knowledge_base() -> dict[str, Any]:
    """Load the files required by the prototype."""

    return {
        "general_rules": load_text_file(GENERAL_RULES_PATH),
        "waste_dictionary": load_json_file(WASTE_DICTIONARY_PATH),
        "collection_schedule": load_json_file(COLLECTION_SCHEDULE_PATH),
        "english_guide": load_text_file(ENGLISH_GUIDE_PATH),
        "output_schema": load_json_file(OUTPUT_SCHEMA_PATH),
        "system_prompt": load_text_file(SYSTEM_PROMPT_PATH),
        "vision_schema": load_json_file(VISION_SCHEMA_PATH),
        "reasoning_schema": load_json_file(REASONING_SCHEMA_PATH),
    }