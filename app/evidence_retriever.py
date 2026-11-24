import re
from difflib import SequenceMatcher
from typing import Any

DEFAULT_RECORD_LIMIT = 20
DEFAULT_RULE_LIMIT = 8


def normalize_text(text: str) -> str:
    """Normalize Japanese or English text for comparison."""
    return (
        str(text)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("　", "")
        .replace("\n", "")
        .replace("（", "(")
        .replace("）", ")")
    )


def get_base_item_name(text: str) -> str:
    """Return the item label before a parenthetical qualifier."""
    return normalize_text(text).split("(", 1)[0]


def create_character_ngrams(text: str, size: int = 2) -> set[str]:
    """Create character n-grams without treating one character as a phrase."""
    normalized_text = normalize_text(text)
    if len(normalized_text) < size:
        return set()
    return {
        normalized_text[index:index + size]
        for index in range(len(normalized_text) - size + 1)
    }


def calculate_ngram_similarity(first_text: str, second_text: str) -> float:
    """Calculate Jaccard overlap between character n-gram sets."""
    first_ngrams = create_character_ngrams(first_text)
    second_ngrams = create_character_ngrams(second_text)
    if not first_ngrams or not second_ngrams:
        return 0.0
    intersection = first_ngrams & second_ngrams
    union = first_ngrams | second_ngrams
    return len(intersection) / len(union)


def classify_record_match(concept: str, record: dict[str, Any]) -> str:
    """Describe the strongest textual relationship to a dictionary item."""
    normalized_concept = normalize_text(concept)
    normalized_item = normalize_text(record.get("item_ja", ""))
    base_item = get_base_item_name(record.get("item_ja", ""))
    instructions = normalize_text(record.get("instructions_ja", ""))

    if not normalized_concept or not normalized_item:
        return "none"
    if normalized_concept == normalized_item:
        return "exact"
    if normalized_concept == base_item:
        return "base_exact"
    if len(normalized_concept) >= 2 and normalized_concept in normalized_item:
        return "concept_in_item"
    if len(normalized_item) >= 2 and normalized_item in normalized_concept:
        return "item_in_concept"
    if len(normalized_concept) >= 2 and normalized_concept in instructions:
        return "instruction_only"
    if len(normalized_concept) >= 2:
        ratio = SequenceMatcher(None, normalized_concept, normalized_item).ratio()
        ngram = calculate_ngram_similarity(normalized_concept, normalized_item)
        if ratio >= 0.58 or ngram >= 0.34:
            return "fuzzy"
    return "none"


def calculate_record_score(concept: str, record: dict[str, Any]) -> float:
    """Calculate conservative relevance between a concept and a record."""
    normalized_concept = normalize_text(concept)
    normalized_item = normalize_text(record.get("item_ja", ""))
    match_quality = classify_record_match(concept, record)
    if match_quality == "none":
        return 0.0

    fixed_scores = {
        "exact": 16.0,
        "base_exact": 14.0,
        "concept_in_item": 10.0,
        "item_in_concept": 8.0,
        "instruction_only": 2.0,
    }
    score = fixed_scores.get(match_quality, 0.0)
    if match_quality == "fuzzy":
        score = (
            SequenceMatcher(None, normalized_concept, normalized_item).ratio() * 5.0
            + calculate_ngram_similarity(normalized_concept, normalized_item) * 5.0
        )
    return score


def collect_weighted_search_concepts(
    vision_result: dict[str, Any],
) -> list[tuple[str, float, str]]:
    """Collect concepts with object-level evidence weighted above attributes."""
    weighted: list[tuple[str, float, str]] = []

    def add(value: Any, weight: float, source: str) -> None:
        text = str(value).strip() if value else ""
        if text:
            weighted.append((text, weight, source))

    primary_object = vision_result.get("primary_object", {})
    add(primary_object.get("name_ja"), 1.45, "primary_object")
    add(primary_object.get("function"), 1.10, "primary_function")

    components = vision_result.get("components", [])
    if isinstance(components, list):
        for component in components:
            if not isinstance(component, dict):
                continue
            add(component.get("name_ja"), 1.35, "component_object")
            add(component.get("function"), 1.05, "component_function")
            for field_name in ("materials", "recycling_marks"):
                values = component.get(field_name, [])
                if isinstance(values, list):
                    for value in values:
                        add(value, 0.72, field_name)
            for field_name in ("visible_condition", "hazard_characteristics"):
                values = component.get(field_name, [])
                if isinstance(values, list):
                    for value in values:
                        add(value, 0.58, field_name)

    observations = vision_result.get("visible_observations", {})
    if isinstance(observations, dict):
        for field_name, weight in (
            ("materials", 0.72),
            ("recycling_marks", 0.90),
            ("condition", 0.55),
        ):
            values = observations.get(field_name, [])
            if isinstance(values, list):
                for value in values:
                    add(value, weight, f"observation_{field_name}")

    evidence = vision_result.get("evidence_search_concepts", {})
    if isinstance(evidence, dict):
        for field_name, weight in (
            ("overall_item_terms_ja", 1.35),
            ("component_terms_ja", 1.15),
            ("function_terms_ja", 1.00),
            ("material_terms_ja", 0.72),
            ("condition_terms_ja", 0.55),
        ):
            values = evidence.get(field_name, [])
            if isinstance(values, list):
                for value in values:
                    add(value, weight, field_name)

    deduplicated: dict[str, tuple[str, float, str]] = {}
    for text, weight, source in weighted:
        key = normalize_text(text)
        current = deduplicated.get(key)
        if current is None or weight > current[1]:
            deduplicated[key] = (text, weight, source)
    return list(deduplicated.values())


def collect_search_concepts(vision_result: dict[str, Any]) -> list[str]:
    """Return the public, unweighted concept list used in developer traces."""
    return [entry[0] for entry in collect_weighted_search_concepts(vision_result)]


def retrieve_candidate_records(
    concepts: list[str],
    waste_dictionary: dict[str, Any],
    limit: int = DEFAULT_RECORD_LIMIT,
    concept_metadata: list[tuple[str, float, str]] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve records while prioritizing object identity over attributes."""
    weighted_lookup = {
        normalize_text(text): (weight, source)
        for text, weight, source in (concept_metadata or [])
    }
    scored_records: list[dict[str, Any]] = []

    for record in waste_dictionary.get("records", []):
        if not isinstance(record, dict) or not record.get("id"):
            continue
        best_score = 0.0
        best_quality = "none"
        best_source = ""
        matched_concepts: list[str] = []

        for concept in concepts:
            weight, source = weighted_lookup.get(
                normalize_text(concept), (1.0, "unweighted")
            )
            raw_score = calculate_record_score(concept, record)
            weighted_score = raw_score * weight
            quality = classify_record_match(concept, record)
            if weighted_score >= 1.5:
                matched_concepts.append(concept)
            if weighted_score > best_score:
                best_score = weighted_score
                best_quality = quality
                best_source = source

        if best_score < 2.0:
            continue
        candidate = dict(record)
        candidate["retrieval_score"] = round(best_score, 4)
        candidate["match_quality"] = best_quality
        candidate["best_concept_source"] = best_source
        candidate["matched_concepts"] = list(dict.fromkeys(matched_concepts))
        scored_records.append(candidate)

    quality_rank = {
        "exact": 0,
        "base_exact": 1,
        "concept_in_item": 2,
        "item_in_concept": 3,
        "fuzzy": 4,
        "instruction_only": 5,
        "none": 6,
    }
    scored_records.sort(
        key=lambda record: (
            quality_rank.get(record.get("match_quality", "none"), 9),
            -record.get("retrieval_score", 0.0),
            len(record.get("item_ja", "")),
        )
    )
    return scored_records[:limit]


def normalize_section_id(heading: str) -> str:
    """Create a stable identifier from a Markdown heading."""
    section_id = heading.strip().lower().replace("`", "")
    section_id = re.sub(r"[^a-z0-9_]+", "_", section_id)
    return section_id.strip("_") or "general_rule"


def split_general_rules_into_sections(general_rules: str) -> list[dict[str, str]]:
    """Split general_rules.md into searchable heading sections."""
    pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(general_rules))
    sections: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(general_rules)
        heading = match.group(2).strip()
        content = general_rules[start:end].strip()
        if content:
            sections.append({
                "section_id": normalize_section_id(heading),
                "heading": heading,
                "content": content,
            })
    return sections


def collect_rule_topics(vision_result: dict[str, Any]) -> list[str]:
    """Collect general-rule topics and observable terms."""
    topics: list[str] = []
    evidence = vision_result.get("evidence_search_concepts", {})
    if isinstance(evidence, dict):
        values = evidence.get("general_rule_topics", [])
        if isinstance(values, list):
            topics.extend(str(value) for value in values if value)
    observations = vision_result.get("visible_observations", {})
    if isinstance(observations, dict):
        for field_name in ("materials", "recycling_marks"):
            values = observations.get(field_name, [])
            if isinstance(values, list):
                topics.extend(str(value) for value in values if value)
        if observations.get("remaining_contents_visible"):
            topics.extend(["remaining contents", "empty container"])
        if observations.get("battery_or_electrical_components"):
            topics.extend(["battery", "hazardous", "electrical appliance"])
        if observations.get("sharp_or_broken_parts"):
            topics.extend(["sharp", "broken", "dangerous"])
        if observations.get("pressurized_container"):
            topics.extend(["spray can", "gas cylinder", "pressurized"])
    return list(dict.fromkeys(topic.strip() for topic in topics if topic.strip()))


def calculate_rule_score(search_terms: list[str], section: dict[str, str]) -> float:
    """Score rule sections conservatively, ignoring one-character containment."""
    heading = section.get("heading", "")
    searchable = normalize_text(f"{heading}\n{section.get('content', '')}")
    score = 0.0
    for term in search_terms:
        normalized = normalize_text(term)
        if len(normalized) < 2:
            continue
        if normalized in searchable:
            score += 4.0
        score += calculate_ngram_similarity(normalized, heading) * 2.0
    return score


def retrieve_general_rule_sections(
    vision_result: dict[str, Any],
    general_rules: str,
    limit: int = DEFAULT_RULE_LIMIT,
) -> list[dict[str, Any]]:
    """Retrieve relevant rules and retain core waste-category sections."""
    sections = split_general_rules_into_sections(general_rules)
    search_terms = collect_search_concepts(vision_result) + collect_rule_topics(vision_result)
    scored: list[dict[str, Any]] = []
    category_section_ids = {
        "burnable", "unburnable", "recyclable",
        "plastic_container_packaging", "diapers", "hazardous",
        "large_sized", "not_accepted_by_city",
    }
    for section in sections:
        score = calculate_rule_score(search_terms, section)
        # Category sections are low-cost guardrails against a noisy dictionary set.
        if section.get("section_id") in category_section_ids:
            score += 0.25
        if score <= 0:
            continue
        copy = dict(section)
        copy["retrieval_score"] = round(score, 4)
        scored.append(copy)
    scored.sort(key=lambda section: (-section.get("retrieval_score", 0.0), section.get("heading", "")))
    return scored[:limit]


def build_evidence_packet(
    vision_result: dict[str, Any],
    waste_dictionary: dict[str, Any],
    general_rules: str,
    record_limit: int = DEFAULT_RECORD_LIMIT,
    rule_limit: int = DEFAULT_RULE_LIMIT,
) -> dict[str, Any]:
    """Build official candidate evidence for the reasoning model."""
    metadata = collect_weighted_search_concepts(vision_result)
    concepts = [entry[0] for entry in metadata]
    candidate_records = retrieve_candidate_records(
        concepts=concepts,
        waste_dictionary=waste_dictionary,
        limit=record_limit,
        concept_metadata=metadata,
    )
    rule_sections = retrieve_general_rule_sections(
        vision_result=vision_result,
        general_rules=general_rules,
        limit=rule_limit,
    )
    return {
        "search_concepts": concepts,
        "candidate_records": candidate_records,
        "general_rule_sections": rule_sections,
        "retrieval_summary": {
            "candidate_record_count": len(candidate_records),
            "general_rule_section_count": len(rule_sections),
        },
    }
