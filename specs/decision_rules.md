# Kitami Gomi AI Decision Rules

## Purpose

These rules define when the prototype may provide a final disposal answer, when it must ask a clarification question, and when it must report that the result is unsupported.

## Source priority

Use official information in this order:

1. `waste_dictionary.json` for item-specific classification and instructions.
2. `general_rules.md` for bag, preparation, size, safety, and disposal rules.
3. `collection_schedule.json` for the next collection date.
4. `english_guide.md` for clear English wording.

An exact item rule takes priority over a general category rule.

## Result status

The `result_status` field must contain one of these values:

### `final`

Use `final` only when:

- The object is identified with reasonable confidence.
- A supported official dictionary match is found.
- Required condition, size, mark, contents, and battery information are known.
- The category and disposal method are supported by official sources.

### `needs_clarification`

Use `needs_clarification` when one answer from the user could determine the correct category.

Ask only one focused question at a time.

Examples:

- “Can the food residue be washed off?”
- “Does the bottle have a PET mark?”
- “Is the item longer than 1 metre?”
- “Can the battery be removed?”
- “Is the container completely empty?”

Do not provide a final category or collection date until the essential uncertainty is resolved.

### `unsupported`

Use `unsupported` when:

- The object cannot be identified reliably.
- No sufficiently relevant official dictionary record is found.
- The photograph contains several objects and the intended item is unclear.
- The item appears to be commercial or contractor waste outside the prototype scope.
- The available official sources do not support a safe answer.
- The calendar is outside its validity period.

The response must explain the uncertainty and recommend checking with Kitami City when appropriate.

## Object-identification rules

The vision model should identify:

- The specific object and its function
- Visible material
- Visible PET or `プラ` mark
- Visible contamination
- Remaining contents
- Broken or sharp parts
- Battery or electrical components
- Approximate size when reasonably visible

The model must not infer hidden characteristics as facts.

## Confidence rules

Use a confidence value from `0.0` to `1.0`.

- `0.90–1.00`: Object is clearly visible and specifically identifiable.
- `0.70–0.89`: Likely identification, with minor uncertainty.
- `0.50–0.69`: Meaningful ambiguity exists. Clarification is normally required.
- Below `0.50`: Do not provide a final disposal answer.

A high visual confidence does not automatically mean the disposal classification is confirmed.

## Dictionary-match rules

The `match_type` field must contain one of:

### `exact`

The identified object corresponds directly to a dictionary item.

### `close`

The object is a common synonym, translation, brand-independent equivalent, or minor variation of a dictionary item.

### `related`

The object is not listed exactly, but an official record with the same function and relevant characteristics may apply.

A `related` match requires careful application of the general rules and may require clarification.

### `none`

No sufficiently supported dictionary record was found.

Use `unsupported` unless another official rule clearly resolves the item.

## Condition rules

Ask for clarification when classification depends on a condition that is not reliably visible, including:

- Whether contamination can be removed
- Whether a container is empty
- Whether the product has a PET or `プラ` mark
- Whether a battery can be removed
- Whether an item exceeds a size or weight threshold
- Whether the waste came from household use
- Whether a contractor removed the item

Do not assume that an item is clean, empty, washable, small enough, or battery-free.

## Disposal rules

The final disposal result must include:

- Official category
- Bag color or alternative disposal route
- Required preparation
- Safety warning when applicable

Do not describe every plastic object as plastic container packaging. The object’s function, packaging status, mark, and condition must be considered.

## Collection-date rules

The collection date must be calculated by program code using `collection_schedule.json`.

The AI model must not invent or calculate the date independently.

Return a collection date only when:

- The category is final
- The category uses neighborhood collection
- The current date falls within the schedule validity period

For large-sized waste, city-unaccepted waste, and drop-off collection, set `collection.applicable` to `false`.

## Safety rules

Always highlight applicable safety instructions for:

- Batteries and rechargeable devices
- Spray cans and gas cylinders
- Lighters
- Sharp or broken objects
- Fluorescent tubes and bulbs
- Flammable liquids
- Medical needles
- Items Kitami City cannot process

Never recommend puncturing a spray can.

Never recommend placing a battery inside ordinary burnable or unburnable waste.

## Response rules

The user-facing response should be concise and practical.

Recommended order:

1. Identified object
2. Waste category
3. Bag or disposal method
4. Preparation steps
5. Next collection date
6. Safety warning
7. Clarification or uncertainty note

Internal source identifiers may be visible during prototype testing but should not clutter the final LINE response.

## Multiple-object rule

The initial prototype analyzes one main item per photograph.

If multiple waste items are visible and the intended object is unclear, ask:

“Which item in the photograph would you like me to check?”

Do not silently choose one object.

## Final principle

When uncertain, ask or report uncertainty.

Never invent a Kitami disposal rule.
