from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.evidence_reasoner import reason_over_evidence
from app.evidence_retriever import build_evidence_packet
from app.knowledge_loader import load_knowledge_base
from app.schedule_service import (
    get_area_record,
    get_calendar_group_id,
    get_next_collection_info,
)
from app.vision_service import analyze_image


CATEGORY_ENGLISH = {
    "burnable": "Burnable waste",
    "unburnable": "Unburnable waste",
    "recyclable": "Recyclable waste",
    "plastic_container_packaging": "Plastic containers and packaging",
    "diapers": "Diapers",
    "hazardous": "Hazardous waste",
    "large_sized": "Large-sized waste",
    "not_accepted_by_city": "Not accepted by Kitami City",
}

DISPOSAL_METHODS = {
    "burnable": "Use the designated orange Kitami City bag.",
    "unburnable": "Use the designated young-grass green Kitami City bag.",
    "recyclable": (
        "Use a transparent or translucent bag, or bundle paper "
        "separately according to type."
    ),
    "plastic_container_packaging": "Use a transparent or translucent bag.",
    "diapers": "Use a transparent or translucent bag of 45 litres or less.",
    "hazardous": (
        "Use a transparent or translucent bag and separate each "
        "hazardous-waste type."
    ),
    "large_sized": (
        "Apply to the Large-sized Waste Reception Center. Do not use "
        "the neighborhood waste station."
    ),
    "not_accepted_by_city": (
        "Use the official retailer, manufacturer, specialist, or "
        "recycling route."
    ),
}

NON_SCHEDULED_CATEGORIES = {
    "large_sized",
    "not_accepted_by_city",
}


def get_japan_datetime() -> datetime:
    """Return the current timezone-aware date and time in Japan."""
    return datetime.now(ZoneInfo("Asia/Tokyo"))


def collect_visible_characteristics(
    vision_result: dict[str, Any],
) -> list[str]:
    """Create a concise list of visible and user-confirmed characteristics."""
    observations = vision_result.get("visible_observations", {})
    characteristics: list[str] = []

    for field_name in (
        "materials",
        "recycling_marks",
        "condition",
        "battery_or_electrical_components",
    ):
        values = observations.get(field_name, [])
        if isinstance(values, list):
            characteristics.extend(str(value) for value in values if value)

    if observations.get("remaining_contents_visible"):
        characteristics.append("Remaining contents are visible")
    if observations.get("sharp_or_broken_parts"):
        characteristics.append("Sharp or broken parts are visible")
    if observations.get("pressurized_container"):
        characteristics.append("The item appears pressurized")

    estimated_size = observations.get("estimated_size")
    if estimated_size:
        characteristics.append(f"Estimated size: {estimated_size}")

    return list(dict.fromkeys(characteristics))


def get_record_map(
    evidence_packet: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Index retrieved candidate records by official record ID."""
    return {
        record["id"]: record
        for record in evidence_packet.get("candidate_records", [])
        if record.get("id")
    }


def get_rule_ids(evidence_packet: dict[str, Any]) -> list[str]:
    """Return retrieved general-rule section IDs."""
    return [
        section["section_id"]
        for section in evidence_packet.get("general_rule_sections", [])
        if section.get("section_id")
    ]


def normalize_preparation_steps(value: Any) -> list[str]:
    """Normalize reasoning-model preparation instructions to a string list."""
    if isinstance(value, list):
        return [str(step).strip() for step in value if str(step).strip()]
    if isinstance(value, str) and value.strip():
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def create_collection_result(
    category_id: str,
    collection_schedule: dict[str, Any],
    current_date: date | datetime,
    area_id: str | None = None,
) -> dict[str, Any]:
    """Create deadline-aware collection information for one category."""
    applicable = category_id not in NON_SCHEDULED_CATEGORIES
    collection_info = {
        "next_date": None,
        "put_out_by": collection_schedule["put_out_by"],
        "today_deadline_passed": False,
        "skipped_date": None,
    }

    if applicable:
        collection_info = get_next_collection_info(
            category_id=category_id,
            collection_schedule=collection_schedule,
            current_date=current_date,
            area_id=area_id,
        )

    area_record = get_area_record(area_id, collection_schedule) if area_id else None
    calendar_group_id = (
        get_calendar_group_id(area_id, collection_schedule) if area_id else None
    )

    return {
        "applicable": applicable,
        "next_date": collection_info["next_date"],
        "put_out_by": collection_info["put_out_by"],
        "today_deadline_passed": collection_info["today_deadline_passed"],
        "skipped_date": collection_info["skipped_date"],
        "service_area_id": area_id,
        "service_area_name_en": (area_record or {}).get("name_en", ""),
        "service_area_name_ja": (area_record or {}).get("name_ja", ""),
        "calendar_group_id": calendar_group_id,
    }

def build_clarification_result(
    final_result: dict[str, Any],
    reasoning_result: dict[str, Any],
    language_hint: str | None = None,
) -> dict[str, Any]:
    """Build a bilingual clarification result from grounded reasoning."""
    clarification = reasoning_result.get("clarification", {})
    question_en = clarification.get("question_en")
    question_ja = clarification.get("question_ja")
    question = question_ja if language_hint == "ja" else question_en
    question = question or question_en or question_ja or (
        "Could you provide one more decision-relevant detail about the item?"
    )

    final_result["result_status"] = "needs_clarification"
    final_result["decision_mode"] = reasoning_result.get(
        "decision_mode", "unsupported"
    )
    final_result["clarification"] = {
        "required": True,
        "question": question,
        "question_en": question_en,
        "question_ja": question_ja,
        "reason": clarification.get("reason"),
        "missing_fact": clarification.get("missing_fact"),
    }
    final_result["user_message"] = {
        "language": language_hint or "en",
        "text": question,
    }
    return final_result


def build_unsupported_result(
    final_result: dict[str, Any],
    reasoning_result: dict[str, Any],
) -> dict[str, Any]:
    """Build a grounded unsupported result."""
    clarification = reasoning_result.get("clarification", {})
    reason = clarification.get("reason") or (
        "The retrieved official evidence was insufficient for a safe decision."
    )

    final_result["result_status"] = "unsupported"
    final_result["decision_mode"] = "unsupported"
    final_result["clarification"] = {
        "required": False,
        "question": None,
        "question_en": None,
        "question_ja": None,
        "reason": reason,
        "missing_fact": clarification.get("missing_fact"),
    }
    final_result["user_message"] = {
        "language": "en",
        "text": (
            "I could not make a sufficiently supported disposal decision "
            "from the available Kitami City evidence."
        ),
    }
    return final_result


def build_component_output(
    component: dict[str, Any],
    collection_schedule: dict[str, Any],
    current_date: date | datetime,
    area_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert one reasoned component into output and collection records."""
    category_id = component.get("category_id", "")
    component_id = component.get("component_id", "")

    output_component = {
        "component_id": component_id,
        "name_en": component.get("name_en", ""),
        "name_ja": component.get("name_ja", ""),
        "material_or_function": component.get("material_or_function", ""),
        "category_id": category_id,
        "category_ja": component.get("category_ja", ""),
        "category_en": CATEGORY_ENGLISH.get(category_id, category_id),
        "bag_or_method": DISPOSAL_METHODS.get(
            category_id, "Check the official Kitami disposal instructions."
        ),
        "preparation_steps": normalize_preparation_steps(
            component.get("preparation_steps_ja", [])
        ),
        "safety_warning": component.get("safety_warning_ja"),
        "supporting_record_ids": component.get("supporting_record_ids", []),
        "supporting_rule_sections": component.get(
            "supporting_rule_sections", []
        ),
        "reasoning_summary": component.get("reasoning_summary", ""),
        "decision_confidence": float(
            component.get("decision_confidence", 0.0)
        ),
    }

    collection = create_collection_result(
        category_id=category_id,
        collection_schedule=collection_schedule,
        current_date=current_date,
        area_id=area_id,
    )
    component_collection = {
        "component_id": component_id,
        "name_en": component.get("name_en", ""),
        "name_ja": component.get("name_ja", ""),
        "category_id": category_id,
        **collection,
    }
    return output_component, component_collection


def populate_source_trace(
    final_result: dict[str, Any],
    evidence_packet: dict[str, Any],
    reasoning_result: dict[str, Any],
) -> None:
    """Record retrieved and cited evidence for developer review."""
    candidate_ids = [
        record["id"]
        for record in evidence_packet.get("candidate_records", [])
        if record.get("id")
    ]
    rule_ids = get_rule_ids(evidence_packet)

    cited_record_ids: set[str] = set()
    cited_rule_ids: set[str] = set()

    overall_decision = reasoning_result.get("overall_decision", {})
    cited_record_ids.update(overall_decision.get("supporting_record_ids", []))
    cited_rule_ids.update(overall_decision.get("supporting_rule_sections", []))

    for component in reasoning_result.get("components", []):
        if isinstance(component, dict):
            cited_record_ids.update(component.get("supporting_record_ids", []))
            cited_rule_ids.update(component.get("supporting_rule_sections", []))

    final_result["source_trace"] = {
        "dictionary_used": bool(cited_record_ids),
        "general_rules_used": bool(cited_rule_ids),
        "schedule_used": bool(
            final_result.get("collection", {}).get("applicable")
            or final_result.get("component_collections")
        ),
        "candidate_record_ids": candidate_ids,
        "general_rule_section_ids": rule_ids,
    }


def recognize_waste_item(
    image_path: Path,
    user_text: str | None = None,
) -> dict[str, Any]:
    """Analyze the photograph without making a disposal decision."""
    knowledge = load_knowledge_base()

    return analyze_image(
        image_path=image_path,
        system_prompt=knowledge["system_prompt"],
        vision_schema=knowledge["vision_schema"],
        user_text=user_text,
    )


def reason_about_recognized_item(
    vision_result: dict[str, Any],
    user_text: str | None = None,
    current_date: date | datetime | None = None,
    area_id: str | None = None,
) -> dict[str, Any]:
    """Run official-evidence reasoning after recognition is confirmed."""
    knowledge = load_knowledge_base()
    final_result = deepcopy(knowledge["output_schema"])

    primary_object = vision_result.get("primary_object", {})
    try:
        visual_confidence = float(primary_object.get("confidence", 0.0))
    except (TypeError, ValueError):
        visual_confidence = 0.0

    final_result["identified_item"] = {
        "name_en": primary_object.get("name_en") or "Unidentified item",
        "name_ja": primary_object.get("name_ja") or "",
        "confidence": visual_confidence,
        "visible_characteristics": collect_visible_characteristics(
            vision_result
        ),
        "is_composite": bool(primary_object.get("is_composite", False)),
    }

    evidence_packet = build_evidence_packet(
        vision_result=vision_result,
        waste_dictionary=knowledge["waste_dictionary"],
        general_rules=knowledge["general_rules"],
    )

    reasoning_result = reason_over_evidence(
        vision_result=vision_result,
        evidence_packet=evidence_packet,
        reasoning_schema=knowledge["reasoning_schema"],
        user_context=user_text,
    )

    final_result["developer_details"] = {
        "vision_result": vision_result,
        "evidence_packet": evidence_packet,
        "reasoning_result": reasoning_result,
    }

    final_result["decision_mode"] = reasoning_result.get(
        "decision_mode", "unsupported"
    )

    evidence_review = reasoning_result.get("evidence_review", {})
    overall_decision = reasoning_result.get("overall_decision", {})
    final_result["reasoning"] = {
        "decision_confidence": float(
            overall_decision.get("decision_confidence", 0.0)
        ),
        "reasoning_summary": overall_decision.get("reasoning_summary", ""),
        "supporting_record_ids": overall_decision.get(
            "supporting_record_ids", []
        ),
        "supporting_rule_sections": overall_decision.get(
            "supporting_rule_sections", []
        ),
        "contradictory_evidence_found": bool(
            evidence_review.get("contradictory_evidence_found", False)
        ),
        "contradictory_evidence_summary": evidence_review.get(
            "contradictory_evidence_summary"
        ),
    }

    decision_status = reasoning_result.get("decision_status")

    if decision_status == "needs_clarification":
        populate_source_trace(final_result, evidence_packet, reasoning_result)
        return build_clarification_result(final_result, reasoning_result)

    if decision_status != "final":
        populate_source_trace(final_result, evidence_packet, reasoning_result)
        return build_unsupported_result(final_result, reasoning_result)

    if current_date is None:
        current_date = get_japan_datetime()

    record_map = get_record_map(evidence_packet)
    decision_mode = reasoning_result.get("decision_mode")

    if decision_mode == "component_separation":
        output_components: list[dict[str, Any]] = []
        component_collections: list[dict[str, Any]] = []

        for component in reasoning_result.get("components", []):
            if not isinstance(component, dict):
                continue
            output_component, component_collection = build_component_output(
                component=component,
                collection_schedule=knowledge["collection_schedule"],
                current_date=current_date,
                area_id=area_id,
            )
            output_components.append(output_component)
            component_collections.append(component_collection)

        final_result["components"] = output_components
        final_result["component_collections"] = component_collections
        area_record = (
            get_area_record(area_id, knowledge["collection_schedule"])
            if area_id
            else None
        )
        calendar_group_id = (
            get_calendar_group_id(area_id, knowledge["collection_schedule"])
            if area_id
            else None
        )
        final_result["collection"] = {
            "applicable": False,
            "next_date": None,
            "put_out_by": knowledge["collection_schedule"]["put_out_by"],
            "service_area_id": area_id,
            "service_area_name_en": (area_record or {}).get("name_en", ""),
            "service_area_name_ja": (area_record or {}).get("name_ja", ""),
            "calendar_group_id": calendar_group_id,
        }
        final_result["disposal"] = {
            "category_id": "multiple",
            "category_ja": "複数区分",
            "category_en": "Separate by component",
            "bag_or_method": "Separate the listed components before disposal.",
            "preparation_steps": [],
            "safety_warning": None,
        }
        final_result["official_match"] = {
            "matched_item_ja": "",
            "match_type": "related",
            "dictionary_record_id": "",
            "source_page": None,
        }

        final_result["reasoning"]["decision_confidence"] = min(
            (
                component.get("decision_confidence", 0.0)
                for component in output_components
            ),
            default=0.0,
        )
        final_result["reasoning"]["reasoning_summary"] = (
            overall_decision.get("reasoning_summary")
            or "The photographed item contains separable components."
        )

    else:
        category_id = overall_decision.get("category_id", "")
        supporting_record_ids = overall_decision.get(
            "supporting_record_ids", []
        )
        primary_record = None
        for record_id in supporting_record_ids:
            if record_id in record_map:
                primary_record = record_map[record_id]
                break

        match_type = {
            "direct_match": "exact",
            "inferred_equivalent": "related",
            "general_rule_inference": "none",
        }.get(decision_mode, "none")

        final_result["official_match"] = {
            "matched_item_ja": (
                primary_record.get("item_ja", "") if primary_record else ""
            ),
            "match_type": match_type,
            "dictionary_record_id": (
                primary_record.get("id", "") if primary_record else ""
            ),
            "source_page": (
                primary_record.get("source_page") if primary_record else None
            ),
        }
        final_result["disposal"] = {
            "category_id": category_id,
            "category_ja": overall_decision.get("category_ja", ""),
            "category_en": CATEGORY_ENGLISH.get(category_id, category_id),
            "bag_or_method": DISPOSAL_METHODS.get(
                category_id, "Check the official Kitami disposal instructions."
            ),
            "preparation_steps": normalize_preparation_steps(
                overall_decision.get("preparation_steps_ja", [])
            ),
            "safety_warning": overall_decision.get("safety_warning_ja"),
        }
        final_result["collection"] = create_collection_result(
            category_id=category_id,
            collection_schedule=knowledge["collection_schedule"],
            current_date=current_date,
            area_id=area_id,
        )

    final_result["result_status"] = "final"
    final_result["clarification"] = {
        "required": False,
        "question": None,
        "question_en": None,
        "question_ja": None,
        "reason": None,
        "missing_fact": None,
    }
    final_result["user_message"] = {
        "language": "en",
        "text": final_result["reasoning"].get("reasoning_summary", ""),
    }

    populate_source_trace(final_result, evidence_packet, reasoning_result)
    return final_result


def analyze_waste_item(
    image_path: Path,
    user_text: str | None = None,
    current_date: date | datetime | None = None,
    area_id: str | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for direct recognition and reasoning."""
    vision_result = recognize_waste_item(
        image_path=image_path,
        user_text=user_text,
    )
    return reason_about_recognized_item(
        vision_result=vision_result,
        user_text=user_text,
        current_date=current_date,
        area_id=area_id,
    )
