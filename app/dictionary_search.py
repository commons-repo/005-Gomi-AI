from typing import Any


def normalize_text(text: str) -> str:
    """Normalize text for basic dictionary matching."""

    return (
        text.strip()
        .lower()
        .replace(" ", "")
        .replace("　", "")
        .replace("\n", "")
    )


def search_dictionary(
    query: str,
    waste_dictionary: dict[str, Any],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Search the official Kitami waste dictionary.

    Search order:
    1. Exact normalized match
    2. Item name contains the query
    3. Query contains the item name
    """

    normalized_query = normalize_text(query)

    if not normalized_query:
        return []

    records = waste_dictionary.get("records", [])

    exact_matches = []
    partial_matches = []
    reverse_matches = []

    for record in records:
        item_name = record.get("item_ja", "")
        normalized_item = normalize_text(item_name)

        if normalized_item == normalized_query:
            exact_matches.append(
                {
                    **record,
                    "search_match_type": "exact",
                }
            )

        elif normalized_query in normalized_item:
            partial_matches.append(
                {
                    **record,
                    "search_match_type": "partial",
                }
            )

        elif normalized_item in normalized_query:
            reverse_matches.append(
                {
                    **record,
                    "search_match_type": "reverse_partial",
                }
            )

    combined_results = (
        exact_matches
        + partial_matches
        + reverse_matches
    )

    return combined_results[:limit]