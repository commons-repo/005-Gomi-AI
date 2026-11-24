import json
from typing import Any

from openai import OpenAI

from app.config import OPENAI_API_KEY
from app.language_service import (
    build_language_instruction,
    get_category_label,
    get_disposal_method,
    get_ui_text,
)


DEFAULT_LOCALIZATION_MODEL = "gpt-4.1-mini"


def get_bilingual_area_label(
    collection: dict[str, Any],
    language_code: str,
) -> str:
    """Return the verified selected area with the chosen language first."""
    name_en = str(collection.get("service_area_name_en", "")).strip()
    name_ja = str(collection.get("service_area_name_ja", "")).strip()
    if language_code == "ja":
        return f"{name_ja} ({name_en})" if name_en else name_ja
    return f"{name_en} ({name_ja})" if name_ja else name_en


def get_contextual_disposal_method(
    category_id: str,
    item_name: str,
    language_code: str,
) -> str:
    """Avoid applying paper-only guidance to non-paper recyclables."""
    if category_id != "recyclable":
        return get_disposal_method(category_id, language_code)

    normalized = item_name.casefold()
    paper_terms = (
        "paper", "cardboard", "catalog", "magazine", "newspaper", "carton",
        "紙", "段ボール", "カタログ", "雑誌", "新聞",
    )
    if any(term in normalized for term in paper_terms):
        return (
            "種類ごとに分け、ひもで縛って出してください。"
            if language_code == "ja"
            else "Separate it by paper type and tie it securely with string."
        )
    return (
        "透明または半透明の袋を使用してください。"
        if language_code == "ja"
        else "Use a transparent or translucent bag."
    )


def get_deadline_passed_message(
    collection: dict[str, Any],
    language_code: str,
) -> str | None:
    """Return a concise notice when today's collection deadline was skipped."""
    if not collection.get("today_deadline_passed"):
        return None
    put_out_by = collection.get("put_out_by", "08:30")
    if language_code == "ja":
        return f"**期限：** 本日の{put_out_by}の排出期限は過ぎています。"
    return f"**Deadline:** Today's {put_out_by} put-out deadline has passed."


def remove_markdown_headings(text: str) -> str:
    """Convert heading syntax to ordinary same-size bold text."""
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            label = stripped.lstrip("#").strip()
            lines.append(f"**{label}**" if label else "")
        else:
            lines.append(line)
    return "\n".join(lines).strip()


def build_component_fallback_message(
    result: dict[str, Any],
    language_code: str,
) -> str:
    """Build a deterministic message for component-separated results."""
    identified_item = result.get("identified_item", {})
    components = result.get("components", [])
    parent_name = " ".join(
        str(value)
        for value in (
            identified_item.get("name_en"),
            identified_item.get("name_ja"),
        )
        if value
    )
    collections = {
        entry.get("component_id"): entry
        for entry in result.get("component_collections", [])
        if isinstance(entry, dict)
    }

    if language_code == "ja":
        item_name = (
            identified_item.get("name_ja")
            or identified_item.get("name_en")
            or "複合品目"
        )
        lines = [
            f"**判定品目：** {item_name}",
            "**分別方法：** 部品ごとに分けて排出してください。",
        ]
    else:
        item_name = (
            identified_item.get("name_en")
            or identified_item.get("name_ja")
            or "Composite item"
        )
        lines = [
            f"**Object:** {item_name}",
            "**Disposal method:** Separate the components before disposal.",
        ]

    area_source = next(iter(collections.values()), result.get("collection", {}))
    area_label = get_bilingual_area_label(area_source, language_code)
    if area_label:
        lines.append(
            f"**地域：** {area_label}"
            if language_code == "ja"
            else f"**Area:** {area_label}"
        )

    for index, component in enumerate(components, start=1):
        if not isinstance(component, dict):
            continue

        component_id = component.get("component_id")
        collection = collections.get(component_id, {})
        category_id = component.get("category_id", "")

        if language_code == "ja":
            component_name = (
                component.get("name_ja")
                or component.get("name_en")
                or f"部品{index}"
            )
            category_label = get_category_label(category_id, "ja")
            disposal_method = get_contextual_disposal_method(
                category_id, f"{parent_name} {component_name}", "ja"
            )
            lines.extend(
                [
                    f"**{index}. {component_name}**",
                    f"**分別区分：** {category_label}",
                    f"**指定袋または排出方法：** {disposal_method}",
                ]
            )
        else:
            component_name = (
                component.get("name_en")
                or component.get("name_ja")
                or f"Component {index}"
            )
            category_label = get_category_label(category_id, "en")
            disposal_method = get_contextual_disposal_method(
                category_id, f"{parent_name} {component_name}", "en"
            )
            lines.extend(
                [
                    f"**{index}. {component_name}**",
                    f"**Category:** {category_label}",
                    f"**Bag or method:** {disposal_method}",
                ]
            )

        preparation_steps = component.get("preparation_steps", [])
        if preparation_steps:
            heading = "**出し方：**" if language_code == "ja" else "**Preparation:**"
            lines.append(heading)
            lines.extend(f"- {step}" for step in preparation_steps)

        if collection.get("applicable"):
            deadline_message = get_deadline_passed_message(
                collection, language_code
            )
            if deadline_message:
                lines.append(deadline_message)
            next_date = collection.get("next_date")
            if next_date:
                if language_code == "ja":
                    lines.append(f"**次回収集日：** {next_date}")
                    lines.append(
                        f"**排出時刻：** {collection.get('put_out_by', '08:30')}まで"
                    )
                else:
                    lines.append(f"**Next collection date:** {next_date}")
                    lines.append(
                        f"**Put it out by:** {collection.get('put_out_by', '08:30')}"
                    )
        else:
            lines.append(
                get_ui_text(language_code, "no_schedule")
            )

        safety_warning = component.get("safety_warning")
        if safety_warning:
            label = "安全上の注意" if language_code == "ja" else "Safety"
            lines.append(f"**{label}:** {safety_warning}")

        reasoning_summary = component.get("reasoning_summary")
        if reasoning_summary:
            label = "判断理由" if language_code == "ja" else "Reason"
            lines.append(f"**{label}:** {reasoning_summary}")

    return "\n\n".join(lines)


def build_single_fallback_message(
    result: dict[str, Any],
    language_code: str,
) -> str:
    """Build a deterministic message for one-category results."""
    identified_item = result.get("identified_item", {})
    disposal = result.get("disposal", {})
    collection = result.get("collection", {})
    reasoning = result.get("reasoning", {})
    category_id = disposal.get("category_id", "")
    item_context = " ".join(
        str(value)
        for value in (
            identified_item.get("name_en"),
            identified_item.get("name_ja"),
        )
        if value
    )
    area_label = get_bilingual_area_label(collection, language_code)

    if language_code == "ja":
        item_name = (
            identified_item.get("name_ja")
            or identified_item.get("name_en")
            or "不明な品目"
        )
        lines = [
            f"**判定品目：** {item_name}",
            f"**分別区分：** {get_category_label(category_id, 'ja')}",
            f"**指定袋または排出方法：** {get_contextual_disposal_method(category_id, item_context, 'ja')}",
        ]
    else:
        item_name = (
            identified_item.get("name_en")
            or identified_item.get("name_ja")
            or "Unidentified item"
        )
        lines = [
            f"**Object:** {item_name}",
            f"**Category:** {get_category_label(category_id, 'en')}",
            f"**Bag or method:** {get_contextual_disposal_method(category_id, item_context, 'en')}",
        ]

    if area_label:
        lines.append(
            f"**地域：** {area_label}"
            if language_code == "ja"
            else f"**Area:** {area_label}"
        )

    preparation_steps = disposal.get("preparation_steps", [])
    if preparation_steps:
        heading = "**出し方：**" if language_code == "ja" else "**Preparation:**"
        lines.append(heading)
        lines.extend(f"- {step}" for step in preparation_steps)

    if collection.get("applicable"):
        deadline_message = get_deadline_passed_message(collection, language_code)
        if deadline_message:
            lines.append(deadline_message)
        next_date = collection.get("next_date")
        if next_date:
            if language_code == "ja":
                lines.append(f"**次回収集日：** {next_date}")
                lines.append(
                    f"**排出時刻：** {collection.get('put_out_by', '08:30')}まで"
                )
            else:
                lines.append(f"**Next collection date:** {next_date}")
                lines.append(
                    f"**Put it out by:** {collection.get('put_out_by', '08:30')}"
                )
        else:
            lines.append(get_ui_text(language_code, "no_valid_date"))
    else:
        lines.append(get_ui_text(language_code, "no_schedule"))

    safety_warning = disposal.get("safety_warning")
    if safety_warning:
        label = "安全上の注意" if language_code == "ja" else "Safety"
        lines.append(f"**{label}:** {safety_warning}")

    reasoning_summary = reasoning.get("reasoning_summary")
    if reasoning_summary:
        label = "判断理由" if language_code == "ja" else "Reason"
        lines.append(f"**{label}:** {reasoning_summary}")

    return "\n\n".join(lines)


def build_fallback_final_message(
    result: dict[str, Any],
    language_code: str,
) -> str:
    """Build a final message without a localization API call."""
    if result.get("decision_mode") == "component_separation" or result.get(
        "components"
    ):
        return build_component_fallback_message(result, language_code)

    return build_single_fallback_message(result, language_code)


def build_localization_payload(
    result: dict[str, Any],
    language_code: str,
) -> dict[str, Any]:
    """Create verified presentation data supplied to the response localizer."""
    identified = result.get("identified_item", {})
    parent_name = " ".join(
        str(value)
        for value in (identified.get("name_en"), identified.get("name_ja"))
        if value
    )
    disposal = dict(result.get("disposal", {}))
    category_id = disposal.get("category_id", "")
    if category_id:
        disposal["bag_or_method"] = get_contextual_disposal_method(
            category_id, parent_name, language_code
        )

    components = []
    for source_component in result.get("components", []):
        if not isinstance(source_component, dict):
            continue
        component = dict(source_component)
        component_name = " ".join(
            str(value)
            for value in (component.get("name_en"), component.get("name_ja"))
            if value
        )
        component_category = component.get("category_id", "")
        if component_category:
            component["bag_or_method"] = get_contextual_disposal_method(
                component_category,
                f"{parent_name} {component_name}",
                language_code,
            )
        components.append(component)

    collection = dict(result.get("collection", {}))

    if not collection.get("today_deadline_passed"):
        collection.pop("today_deadline_passed", None)

    component_collections = result.get("component_collections", [])

    area_source = collection
    if not area_source and component_collections:
        area_source = component_collections[0]

    return {
        "decision_mode": result.get("decision_mode"),
        "identified_item": identified,
        "official_match": result.get("official_match", {}),
        "disposal": disposal,
        "components": components,
        "reasoning": result.get("reasoning", {}),
        "collection": collection,
        "component_collections": component_collections,
        "selected_area_label": get_bilingual_area_label(
            area_source, language_code
        ),
    }


def localize_final_response(
    result: dict[str, Any],
    language_code: str,
    model: str = DEFAULT_LOCALIZATION_MODEL,
) -> str:
    """Produce a single-language resident-facing final answer."""
    if language_code not in {"en", "ja"}:
        language_code = "en"

    if not OPENAI_API_KEY:
        return build_fallback_final_message(result, language_code)

    client = OpenAI(api_key=OPENAI_API_KEY)
    payload = build_localization_payload(result, language_code)
    language_instruction = build_language_instruction(language_code)

    instructions = f"""
You prepare a resident-facing household-waste response for the Kitami Gomi AI
prototype.

{language_instruction}

The supplied decision has already been produced by a source-grounded reasoning
pipeline using Kitami City's official documents.

You must not:
- change any category;
- combine components that the decision says must be separated;
- change any collection date or time;
- when today_deadline_passed is true, state clearly that today's put-out
  deadline has passed before showing the next collection date;
- when today_deadline_passed is absent or false, do not mention today's
  deadline status;
- remove a preparation or safety instruction;
- add unsupported municipal rules;
- change direct or inferred evidence into a stronger claim;
- include developer JSON, record IDs, or source-page numbers;
- mix English and Japanese in resident-facing prose.

If decision_mode is component_separation:
- state that the item must be separated;
- create one clearly numbered section for every supplied component;
- give each component's category, bag or method, preparation, collection date,
  safety warning, and concise reason when available.

Otherwise, present one category result.

Translate official Japanese preparation and safety instructions faithfully when
English is selected. Use natural Japanese when Japanese is selected.

Use selected_area_label exactly whenever the area is shown.
Use ordinary body-sized Markdown only. Never use #, ##, ###, or heading syntax.
Use bold labels and simple numbered lines. Keep all text at one visual size.
Do not add greetings, thanks, slogans, or generic closing reminders.
Use the supplied bag_or_method exactly. Do not add an alternative method.
In English, use English only except for the bilingual selected_area_label.
In Japanese, use Japanese only except for the bilingual selected_area_label.
Keep the response concise and structurally consistent.
Return concise Markdown only.
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
                        "text": (
                            "Create the resident-facing response from this "
                            "verified result:\n\n"
                            + json.dumps(payload, ensure_ascii=False, indent=2)
                        ),
                    }
                ],
            }
        ],
    )

    localized_text = remove_markdown_headings(response.output_text.strip())
    if not localized_text:
        return build_fallback_final_message(result, language_code)

    return localized_text


def localize_clarification_question(
    result: dict[str, Any],
    language_code: str,
) -> str:
    """Return the already grounded clarification in the selected language."""
    clarification = result.get("clarification", {})

    if language_code == "ja":
        return (
            clarification.get("question_ja")
            or clarification.get("question")
            or "正しい分別方法を確認するため、もう一つ情報を教えてください。"
        )

    return (
        clarification.get("question_en")
        or clarification.get("question")
        or "Please provide one more decision-relevant detail about the item."
    )


def localize_unsupported_message(
    result: dict[str, Any],
    language_code: str,
) -> str:
    """Return a concise unsupported message in the selected language."""
    reason = result.get("clarification", {}).get("reason")

    if language_code == "ja":
        base_message = (
            "取得した北見市の公式情報だけでは、十分に根拠のある分別方法を"
            "判断できませんでした。必要に応じて北見市の公式情報をご確認ください。"
        )
        return f"{base_message}\n\n**理由：** {reason}" if reason else base_message

    base_message = (
        "I could not make a sufficiently supported disposal decision from the "
        "available Kitami City evidence. Please consult the official Kitami "
        "City information if needed."
    )
    return f"{base_message}\n\n**Reason:** {reason}" if reason else base_message


def localize_result_message(
    result: dict[str, Any],
    language_code: str,
) -> str:
    """Localize a grounded pipeline result according to its status."""
    result_status = result.get("result_status")

    if result_status == "final":
        return localize_final_response(result, language_code)

    if result_status == "needs_clarification":
        return localize_clarification_question(result, language_code)

    return localize_unsupported_message(result, language_code)
