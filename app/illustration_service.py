import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAP_PATH = PROJECT_ROOT / "bag_images" / "illustration_map.json"


def normalize_text(value: Any) -> str:
    """Normalize English and Japanese guidance for signal matching."""
    return " ".join(str(value or "").casefold().split())


def load_illustration_map(
    map_path: Path = DEFAULT_MAP_PATH,
) -> dict[str, Any]:
    """Load and minimally validate the local illustration mapping."""
    if not map_path.exists():
        raise FileNotFoundError(f"Illustration mapping was not found: {map_path}")

    with map_path.open("r", encoding="utf-8") as file:
        mapping = json.load(file)

    if not isinstance(mapping.get("illustrations"), dict):
        raise ValueError("illustration_map.json has no valid illustrations object.")
    if not isinstance(mapping.get("display_policy"), dict):
        raise ValueError("illustration_map.json has no valid display policy.")
    return mapping


def collect_guidance_sources(decision: dict[str, Any]) -> dict[str, str]:
    """Keep generic method text separate from exact preparation instructions."""
    bag_or_method = normalize_text(decision.get("bag_or_method", ""))

    preparation_parts: list[str] = []
    for field_name in (
        "preparation_steps",
        "preparation_steps_ja",
        "preparation_steps_en",
        "instructions_ja",
        "instructions_en",
    ):
        value = decision.get(field_name)
        if isinstance(value, list):
            preparation_parts.extend(str(item) for item in value if item)
        elif value:
            preparation_parts.append(str(value))

    return {
        "bag_or_method": bag_or_method,
        "preparation_steps": normalize_text(" ".join(preparation_parts)),
    }


def signal_match_count(text: str, signals: list[Any]) -> int:
    """Count distinct configured signals found in one guidance source."""
    normalized_signals = {
        normalize_text(signal)
        for signal in signals
        if normalize_text(signal)
    }
    return sum(1 for signal in normalized_signals if signal in text)


def select_for_decision(
    decision: dict[str, Any],
    mapping: dict[str, Any],
) -> dict[str, Any] | None:
    """Select one compatible illustration for one disposal decision."""
    category_id = str(decision.get("category_id", "")).strip()
    guidance = collect_guidance_sources(decision)
    illustrations = mapping.get("illustrations", {})
    ranked: list[tuple[int, int, int, str, dict[str, Any]]] = []

    for illustration_id, illustration in illustrations.items():
        if not isinstance(illustration, dict):
            continue

        allowed_categories = illustration.get("category_ids", [])
        category_match = category_id in allowed_categories
        require_category_match = bool(
            illustration.get("require_category_match", False)
        )
        if require_category_match and not category_match:
            continue

        signals = illustration.get("method_signals", [])
        signal_sources = illustration.get(
            "signal_sources",
            ["preparation_steps", "bag_or_method"],
        )
        matches = sum(
            signal_match_count(guidance.get(source, ""), signals)
            for source in signal_sources
        )

        require_method_signal = bool(
            illustration.get("require_method_signal", False)
        )
        if require_method_signal and matches == 0:
            continue

        selection_priority = int(illustration.get("selection_priority", 0))
        allow_category_fallback = bool(
            illustration.get("allow_category_fallback", True)
        )

        if matches:
            ranked.append(
                (2, selection_priority, matches, illustration_id, illustration)
            )
        elif category_match and allow_category_fallback:
            ranked.append(
                (1, selection_priority, 0, illustration_id, illustration)
            )

    if not ranked:
        return None

    ranked.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]))
    match_level, priority, match_count, illustration_id, illustration = ranked[0]

    image_path = PROJECT_ROOT / illustration.get("image_path", "")
    if not image_path.is_file():
        return None

    return {
        "illustration_id": illustration_id,
        "image_path": str(image_path),
        "label_en": illustration.get("label_en", ""),
        "label_ja": illustration.get("label_ja", ""),
        "matched_by": (
            "method_signal" if match_level == 2 else "category_fallback"
        ),
        "matched_signal_count": match_count,
        "selection_priority": priority,
    }


def build_decisions(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract single or component-level verified disposal decisions."""
    components = result.get("components", [])
    if isinstance(components, list) and components:
        return [component for component in components if isinstance(component, dict)]

    disposal = result.get("disposal", {})
    return [disposal] if isinstance(disposal, dict) and disposal else []


def select_result_illustrations(
    result: dict[str, Any],
    language_code: str = "en",
    map_path: Path = DEFAULT_MAP_PATH,
) -> list[dict[str, Any]]:
    """Return deduplicated example illustrations for a verified final result."""
    if result.get("result_status") != "final":
        return []

    mapping = load_illustration_map(map_path)
    policy = mapping.get("display_policy", {})
    maximum = int(policy.get("maximum_images_per_response", 1))
    avoid_duplicates = bool(policy.get("avoid_duplicate_images", True))
    note = policy.get(
        "note_ja" if language_code == "ja" else "note_en",
        "",
    )

    selections: list[dict[str, Any]] = []
    used_paths: set[str] = set()

    for decision in build_decisions(result):
        selection = select_for_decision(decision, mapping)
        if not selection:
            continue

        image_path = selection["image_path"]
        if avoid_duplicates and image_path in used_paths:
            continue

        selection["label"] = selection[
            "label_ja" if language_code == "ja" else "label_en"
        ]
        selection["note"] = note
        selections.append(selection)
        used_paths.add(image_path)

        if len(selections) >= maximum:
            break

    return selections
