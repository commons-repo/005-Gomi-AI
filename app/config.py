import os
from pathlib import Path

from dotenv import load_dotenv


# Project folders
PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge_base"
SPECS_DIR = PROJECT_ROOT / "specs"


# Load private environment variables from .env
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE)


# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# Knowledge-base files
GENERAL_RULES_PATH = KNOWLEDGE_BASE_DIR / "general_rules.md"
WASTE_DICTIONARY_PATH = KNOWLEDGE_BASE_DIR / "waste_dictionary.json"
COLLECTION_SCHEDULE_PATH = KNOWLEDGE_BASE_DIR / "collection_schedule.json"
ENGLISH_GUIDE_PATH = KNOWLEDGE_BASE_DIR / "english_guide.md"
SOURCE_REGISTER_PATH = KNOWLEDGE_BASE_DIR / "source_register.md"


# Specification files
OUTPUT_SCHEMA_PATH = SPECS_DIR / "output_schema.json"
DECISION_RULES_PATH = SPECS_DIR / "decision_rules.md"
SYSTEM_PROMPT_PATH = SPECS_DIR / "system_prompt.md"
VISION_SCHEMA_PATH = SPECS_DIR / "vision_schema.json"
REASONING_SCHEMA_PATH = SPECS_DIR / "reasoning_schema.json"


def validate_configuration() -> None:
    """Check that the API key and required project files are available."""

    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY was not found. Check the private .env file."
        )

    required_files = [
        GENERAL_RULES_PATH,
        WASTE_DICTIONARY_PATH,
        COLLECTION_SCHEDULE_PATH,
        ENGLISH_GUIDE_PATH,
        SOURCE_REGISTER_PATH,
        OUTPUT_SCHEMA_PATH,
        DECISION_RULES_PATH,
        SYSTEM_PROMPT_PATH,
        VISION_SCHEMA_PATH,
        REASONING_SCHEMA_PATH,
    ]

    missing_files = [path for path in required_files if not path.exists()]

    if missing_files:
        missing_list = "\n".join(str(path) for path in missing_files)
        raise FileNotFoundError(
            f"Required project files are missing:\n{missing_list}"
        )

    