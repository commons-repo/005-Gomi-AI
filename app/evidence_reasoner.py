import json
from typing import Any

from openai import OpenAI

from app.config import OPENAI_API_KEY


DEFAULT_REASONING_MODEL = "gpt-4.1-mini"
ALLOWED_DECISION_STATUSES = {
    "final",
    "needs_clarification",
    "unsupported",
}
ALLOWED_DECISION_MODES = {
    "direct_match",
    "inferred_equivalent",
    "component_separation",
    "general_rule_inference",
    "unsupported",
}
ALLOWED_CATEGORY_IDS = {
    "burnable",
    "unburnable",
    "recyclable",
    "plastic_container_packaging",
    "diapers",
    "hazardous",
    "large_sized",
    "not_accepted_by_city",
}


def clean_json_response(response_text: str) -> str:
    """Remove optional Markdown fences from a model response."""

    cleaned_text = response_text.strip()

    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[len("```json"):].strip()
    elif cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[len("```"):].strip()

    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3].strip()

    return cleaned_text


def compact_candidate_record(record: dict[str, Any]) -> dict[str, Any]:
    """Keep only official record fields needed for reasoning."""

    return {
        "id": record.get("id"),
        "item_ja": record.get("item_ja"),
        "category_id": record.get("category_id"),
        "category_ja": record.get("category_ja"),
        "instructions_ja": record.get("instructions_ja"),
        "source_page": record.get("source_page"),
        "retrieval_score": record.get("retrieval_score"),
        "matched_concepts": record.get("matched_concepts", []),
    }


def compact_rule_section(section: dict[str, Any]) -> dict[str, Any]:
    """Keep only official rule fields needed for reasoning."""

    return {
        "section_id": section.get("section_id"),
        "heading": section.get("heading"),
        "content": section.get("content"),
        "retrieval_score": section.get("retrieval_score"),
    }


def build_reasoning_payload(
    vision_result: dict[str, Any],
    evidence_packet: dict[str, Any],
    reasoning_schema: dict[str, Any],
    user_context: str | None = None,
) -> dict[str, Any]:
    """Build the source-grounded payload supplied to the model."""

    candidate_records = [
        compact_candidate_record(record)
        for record in evidence_packet.get("candidate_records", [])
    ]

    rule_sections = [
        compact_rule_section(section)
        for section in evidence_packet.get("general_rule_sections", [])
    ]

    return {
        "user_context": user_context or "",
        "vision_analysis": vision_result,
        "retrieved_official_evidence": {
            "search_concepts": evidence_packet.get("search_concepts", []),
            "candidate_dictionary_records": candidate_records,
            "general_rule_sections": rule_sections,
        },
        "required_output_structure": reasoning_schema,
    }


def build_reasoning_instructions() -> str:
    """Return strict instructions for evidence-grounded reasoning."""

    return """
You are the evidence-reasoning component of the Kitami Gomi AI prototype.

You receive:
1. A visual analysis of one household waste item.
2. The user's accumulated explanation or clarification.
3. Candidate records retrieved from Kitami City's official waste dictionary.
4. Relevant sections retrieved from the official Kitami general waste rules.
5. A required JSON output structure.

Your task is to determine the most strongly supported disposal decision using
only the supplied official evidence.

You may:
- select a direct dictionary match;
- infer that the photographed object is functionally equivalent to an official
  dictionary example;
- decompose a composite object into separable disposable components;
- apply a supplied general rule when no exact item record exists;
- ask one focused clarification question when one missing fact can change the
  disposal result;
- return unsupported when the supplied evidence is insufficient or conflicting.

Decision modes:
- direct_match
- inferred_equivalent
- component_separation
- general_rule_inference
- unsupported

Decision statuses:
- final
- needs_clarification
- unsupported

Important reasoning rules:
- Treat the official dictionary records and supplied general-rule sections as
  evidence, not as a requirement for exact wording.
- Compare function, material, contents, packaging purpose, condition, hazards,
  and separable components.
- A photographed brand or everyday name may be equivalent to a more general
  official dictionary term.
- If an object contains separable parts that follow different official rules,
  use component_separation and provide one component decision per part.
- Do not classify every plastic object as plastic container packaging.
  Packaging function, eligibility, condition, and official evidence matter.
- Do not invent a Kitami rule or rely on municipal rules not included in the
  supplied evidence.
- Do not change official categories attached to dictionary records.
- Do not cite a record ID that is absent from the supplied candidate records.
- Do not cite a general-rule section that is absent from the supplied sections.
- Do not claim that a dictionary record supports the decision unless its record ID
  is cited in the decision.
- Do not describe an official rule more specifically than the supplied rule text.
- Surface contradictory evidence instead of hiding it.
- For safety-critical uncertainty involving batteries, pressurized containers,
  sharp objects, flammable contents, or medical waste, ask for clarification or
  return unsupported rather than guessing.

Output rules:
- Return valid JSON only.
- Do not use Markdown fences.
- Follow the supplied required output structure.
- Keep reasoning summaries concise and evidence-based.
- Use Japanese in official category and preparation fields.
- Questions must be provided in both English and Japanese.
- Use an empty components list for a single-category overall decision.
- For component_separation, populate components and set
  overall_decision.single_category to false.
""".strip()


def normalize_decision_mode(result: dict[str, Any]) -> str:
    """Normalize only the technical reasoning-mode label from cited evidence.

    This does not choose or modify the waste category. It prevents a missing or
    inconsistent developer metadata label from discarding a complete result.
    """
    decision_status = result.get("decision_status")
    supplied_mode = result.get("decision_mode")
    components = result.get("components", [])
    component_decisions = (
        [
            component
            for component in components
            if isinstance(component, dict) and component.get("category_id")
        ]
        if isinstance(components, list)
        else []
    )

    if decision_status == "unsupported":
        return "unsupported"
    if component_decisions:
        return "component_separation"

    decisions: list[dict[str, Any]] = []
    overall_decision = result.get("overall_decision", {})
    if isinstance(overall_decision, dict):
        decisions.append(overall_decision)
    if isinstance(components, list):
        decisions.extend(
            component for component in components if isinstance(component, dict)
        )

    cited_record_ids: set[str] = set()
    cited_rule_ids: set[str] = set()
    for decision in decisions:
        cited_record_ids.update(decision.get("supporting_record_ids", []) or [])
        cited_rule_ids.update(decision.get("supporting_rule_sections", []) or [])

    if cited_record_ids:
        if supplied_mode in {"direct_match", "inferred_equivalent"}:
            return supplied_mode
        return "inferred_equivalent"
    if cited_rule_ids:
        return "general_rule_inference"
    if supplied_mode in ALLOWED_DECISION_MODES:
        return supplied_mode
    if decision_status == "final":
        return "general_rule_inference"
    return "unsupported"


def validate_reasoning_result(
    result: dict[str, Any],
    evidence_packet: dict[str, Any],
) -> dict[str, Any]:
    """Validate critical fields and evidence references."""

    decision_status = result.get("decision_status")
    decision_mode = normalize_decision_mode(result)
    result["decision_mode"] = decision_mode

    if decision_status not in ALLOWED_DECISION_STATUSES:
        raise ValueError(f"Invalid decision_status: {decision_status}")

    if decision_mode not in ALLOWED_DECISION_MODES:
        raise ValueError(f"Invalid decision_mode: {decision_mode}")

    available_record_ids = {
        record.get("id")
        for record in evidence_packet.get("candidate_records", [])
        if record.get("id")
    }
    available_rule_ids = {
        section.get("section_id")
        for section in evidence_packet.get("general_rule_sections", [])
        if section.get("section_id")
    }

    decisions: list[dict[str, Any]] = []
    overall_decision = result.get("overall_decision", {})
    if isinstance(overall_decision, dict):
        decisions.append(overall_decision)

    components = result.get("components", [])
    if isinstance(components, list):
        decisions.extend(
            component for component in components if isinstance(component, dict)
        )

    for decision in decisions:
        category_id = decision.get("category_id")
        if category_id and category_id not in ALLOWED_CATEGORY_IDS:
            raise ValueError(f"Invalid category_id: {category_id}")

        cited_record_ids = set(decision.get("supporting_record_ids", []))
        unknown_record_ids = cited_record_ids - available_record_ids
        if unknown_record_ids:
            raise ValueError(
                "Reasoning result cited unavailable dictionary records: "
                + ", ".join(sorted(unknown_record_ids))
            )

        cited_rule_ids = set(decision.get("supporting_rule_sections", []))
        unknown_rule_ids = cited_rule_ids - available_rule_ids
        if unknown_rule_ids:
            raise ValueError(
                "Reasoning result cited unavailable rule sections: "
                + ", ".join(sorted(unknown_rule_ids))
            )

        confidence = decision.get("decision_confidence", 0.0)
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError) as error:
            raise ValueError("decision_confidence must be numeric") from error

        if not 0.0 <= confidence_value <= 1.0:
            raise ValueError("decision_confidence must be between 0.0 and 1.0")

    if decision_mode == "component_separation" and not components:
        raise ValueError(
            "component_separation requires at least one component decision"
        )

    clarification = result.get("clarification", {})
    if decision_status == "needs_clarification":
        if not clarification.get("required"):
            raise ValueError(
                "needs_clarification requires clarification.required = true"
            )
        if not clarification.get("question_en"):
            raise ValueError("English clarification question is missing")
        if not clarification.get("question_ja"):
            raise ValueError("Japanese clarification question is missing")

    return result


def reason_over_evidence(
    vision_result: dict[str, Any],
    evidence_packet: dict[str, Any],
    reasoning_schema: dict[str, Any],
    user_context: str | None = None,
    model: str = DEFAULT_REASONING_MODEL,
) -> dict[str, Any]:
    """Use OpenAI to reason over retrieved official Kitami evidence."""

    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY was not found. Check the private .env file."
        )

    candidate_records = evidence_packet.get("candidate_records", [])
    general_rule_sections = evidence_packet.get("general_rule_sections", [])

    if not candidate_records and not general_rule_sections:
        return {
            **reasoning_schema,
            "decision_status": "unsupported",
            "decision_mode": "unsupported",
            "overall_item": {
                "name_en": vision_result.get("primary_object", {}).get(
                    "name_en", ""
                ),
                "name_ja": vision_result.get("primary_object", {}).get(
                    "name_ja", ""
                ),
                "description": "No relevant official evidence was retrieved.",
            },
            "components": [],
            "clarification": {
                "required": False,
                "question_en": None,
                "question_ja": None,
                "reason": "No relevant official evidence was retrieved.",
                "missing_fact": None,
            },
        }

    client = OpenAI(api_key=OPENAI_API_KEY)
    payload = build_reasoning_payload(
        vision_result=vision_result,
        evidence_packet=evidence_packet,
        reasoning_schema=reasoning_schema,
        user_context=user_context,
    )

    response = client.responses.create(
        model=model,
        instructions=build_reasoning_instructions(),
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
            "The evidence reasoner did not return valid JSON."
        ) from error

    return validate_reasoning_result(
        result=result,
        evidence_packet=evidence_packet,
    )
