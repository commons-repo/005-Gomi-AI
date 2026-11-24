#!/usr/bin/env python3
"""Condition 2 experiment runner for Kitami Gomi AI Version 4.

Condition 2: verification-in-the-loop processing.

For one selected image, this runner:
1. generates the initial Item Interpretation;
2. allows the interpretation to be verified and corrected when necessary;
3. accepts missing decision-relevant information through Verify;
4. resolves any subsequent clarification required by the downstream process;
5. freezes the verified Item Interpretation and accumulated communication; and
6. repeatedly runs the existing retrieval, reasoning, scheduling, and
   localization tasks using these fixed inputs.

The runner writes raw outputs only, without ground-truth comparison or scoring.

Expected project layout:
    project_root/
        app/
        images/
        knowledge_base/
        specs/
        .env
        run_condition2_verified_communication.py

Full experiment for I17:
    python .\run_condition2_verified_communication.py --image "images\I17.jpg" --item-id I17 --output-dir "condition2_results" --runs 50
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
import traceback
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.config import validate_configuration
from app.knowledge_loader import load_knowledge_base
from app.language_service import build_language_instruction, get_ui_text
from app.pipeline import recognize_waste_item, reason_about_recognized_item
from app.response_localizer import localize_result_message
from app.text_recognition_service import recognize_item_from_text

CONDITION_ID = "condition_2_verified_communication"
AREA_ID = "tabata"
LANGUAGE_CODE = "en"
DEFAULT_RUNS = 50
DEFAULT_EXPERIMENT_DATETIME = "2026-09-17T12:00:00+09:00"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Condition 2 for one manually selected image."
    )
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--item-id", required=True, help="Example: I1")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument(
        "--experiment-datetime", default=DEFAULT_EXPERIMENT_DATETIME
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def parse_fixed_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    japan = ZoneInfo("Asia/Tokyo")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=japan)
    return parsed.astimezone(japan)


def validate_inputs(args: argparse.Namespace) -> datetime:
    if not args.image.is_file():
        raise FileNotFoundError(f"Image not found: {args.image}")
    if args.image.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Image must be JPG, JPEG, PNG, or WEBP.")
    if args.runs < 1:
        raise ValueError("--runs must be at least 1")
    if not args.item_id.strip():
        raise ValueError("--item-id is required")
    return parse_fixed_datetime(args.experiment_datetime)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_image_orientation(image_path: Path) -> tuple[bytes, str]:
    image_bytes = image_path.read_bytes()
    if not image_bytes:
        raise ValueError("The image file is empty.")
    suffix = image_path.suffix.lower()
    output = BytesIO()
    with Image.open(BytesIO(image_bytes)) as source:
        image = ImageOps.exif_transpose(source)
        image.load()
        if suffix == ".png":
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA")
            image.save(output, format="PNG", optimize=True)
            name = image_path.with_suffix(".png").name
        elif suffix == ".webp":
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGB")
            image.save(output, format="WEBP", quality=95, method=6)
            name = image_path.with_suffix(".webp").name
        else:
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(output, format="JPEG", quality=95, optimize=True)
            name = image_path.with_suffix(".jpg").name
    return output.getvalue(), name


def vision_context() -> str:
    return (
        f"{build_language_instruction(LANGUAGE_CODE)}\n\n"
        "Recognition stage only. Identify the photographed object and relevant "
        "separable components. Do not decide disposal yet.\n"
        f"User information: {get_ui_text(LANGUAGE_CODE, 'default_request')}"
    )


def pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def ask_yes_no(prompt: str) -> bool:
    while True:
        answer = input(f"{prompt} [y/n]: ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please enter y or n.")


def recognize_image_once(normalized_bytes: bytes, normalized_name: str) -> dict[str, Any]:
    suffix = Path(normalized_name).suffix.lower() or ".jpg"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            temporary.write(normalized_bytes)
            temporary_path = Path(temporary.name)
        return recognize_waste_item(temporary_path, vision_context())
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def interactive_verification(
    initial_recognition: dict[str, Any],
) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    knowledge = load_knowledge_base()
    recognition = initial_recognition
    communication: list[dict[str, str]] = []
    accumulated_descriptions: list[str] = []

    print("\nInitial Item Interpretation:\n")
    print(pretty(recognition))

    if ask_yes_no("Is the interpretation fully correct and complete?"):
        communication.append({
            "type": "confirmation",
            "content": "The initial interpretation was confirmed by the user.",
        })
    else:
        description = input(
            "Enter the complete correct description and all decision-relevant facts:\n> "
        ).strip()
        if not description:
            raise ValueError("A complete correction is required after selecting no.")
        communication.append({"type": "correction", "content": description})
        accumulated_descriptions.append(description)
        recognition = recognize_item_from_text(
            user_description=description,
            vision_schema=knowledge["vision_schema"],
            language_code=LANGUAGE_CODE,
            previous_recognition=recognition,
        )
        print("\nUpdated Item Interpretation:\n")
        print(pretty(recognition))

    while not ask_yes_no("Is this now the final verified interpretation?"):
        addition = input(
            "Enter the correction or missing decision-relevant facts:\n> "
        ).strip()
        if not addition:
            print("No information entered. Please try again.")
            continue
        communication.append({"type": "additional_correction", "content": addition})
        accumulated_descriptions.append(addition)
        recognition = recognize_item_from_text(
            user_description=addition,
            vision_schema=knowledge["vision_schema"],
            language_code=LANGUAGE_CODE,
            previous_recognition=recognition,
        )
        print("\nUpdated Item Interpretation:\n")
        print(pretty(recognition))

    optional = input(
        "Optional: add any remaining confirmed facts for disposal reasoning, "
        "or press Enter to continue:\n> "
    ).strip()
    if optional:
        communication.append({"type": "additional_context", "content": optional})
        accumulated_descriptions.append(optional)
        recognition = recognize_item_from_text(
            user_description=optional,
            vision_schema=knowledge["vision_schema"],
            language_code=LANGUAGE_CODE,
            previous_recognition=recognition,
        )
        print("\nFinal updated Item Interpretation:\n")
        print(pretty(recognition))
        if not ask_yes_no("Confirm this final interpretation"):
            raise RuntimeError("Verification was not confirmed. Run the script again.")

    context_parts = [
        "The Item Interpretation was verified by the user before repeated testing."
    ]
    if accumulated_descriptions:
        context_parts.append("Confirmed user information:")
        context_parts.extend(accumulated_descriptions)
    return recognition, "\n\n".join(context_parts), communication


def preflight_clarification(
    recognition: dict[str, Any],
    user_context: str,
    communication: list[dict[str, str]],
    fixed_datetime: datetime,
) -> tuple[str, list[dict[str, str]]]:
    """Resolve actual pipeline clarification before freezing the 50-run input."""
    while True:
        result = reason_about_recognized_item(
            vision_result=recognition,
            user_text=user_context,
            current_date=fixed_datetime,
            area_id=AREA_ID,
        )
        status = result.get("result_status")
        if status != "needs_clarification":
            print(f"\nPreflight downstream status: {status}")
            return user_context, communication

        clarification = result.get("clarification", {})
        question = (
            clarification.get("question_en")
            or clarification.get("question")
            or "Please provide the missing decision-relevant fact."
        )
        print(f"\nSystem clarification: {question}")
        answer = input("Your answer:\n> ").strip()
        if not answer:
            print("An answer is required to complete the verified setup.")
            continue
        communication.append({
            "type": "clarification",
            "question": question,
            "content": answer,
        })
        user_context += f"\n\nQuestion: {question}\nAnswer: {answer}"


def existing_runs(path: Path) -> set[int]:
    found: set[int] = set()
    if not path.exists():
        return found
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            number = record.get("run_number")
            if isinstance(number, int):
                found.add(number)
    return found


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as destination:
        destination.write(json.dumps(record, ensure_ascii=False) + "\n")
        destination.flush()


def save_setup(path: Path, setup: dict[str, Any]) -> None:
    path.write_text(pretty(setup), encoding="utf-8")


def load_setup(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_trial(
    item_id: str,
    run_number: int,
    image_path: Path,
    image_hash: str,
    recognition: dict[str, Any],
    user_context: str,
    fixed_datetime: datetime,
) -> dict[str, Any]:
    started = datetime.now(ZoneInfo("Asia/Tokyo"))
    timer = time.perf_counter()
    result: dict[str, Any] | None = None
    message: str | None = None
    error: dict[str, Any] | None = None
    try:
        result = reason_about_recognized_item(
            vision_result=recognition,
            user_text=user_context,
            current_date=fixed_datetime,
            area_id=AREA_ID,
        )
        message = localize_result_message(result, LANGUAGE_CODE)
    except Exception as exception:
        error = {
            "type": type(exception).__name__,
            "message": str(exception),
            "traceback": traceback.format_exc(),
        }
    completed = datetime.now(ZoneInfo("Asia/Tokyo"))
    return {
        "condition_id": CONDITION_ID,
        "item_id": item_id,
        "run_number": run_number,
        "status": "error" if error else (result or {}).get("result_status", "unknown"),
        "communication_used": True,
        "verified_interpretation_frozen": True,
        "area_id": AREA_ID,
        "language_code": LANGUAGE_CODE,
        "fixed_experiment_datetime": fixed_datetime.isoformat(),
        "image": {
            "path": str(image_path.resolve()),
            "filename": image_path.name,
            "sha256": image_hash,
        },
        "started_at": started.isoformat(),
        "completed_at": completed.isoformat(),
        "duration_seconds": round(time.perf_counter() - timer, 6),
        "verified_interpretation": recognition,
        "frozen_user_context": user_context,
        "structured_result": result,
        "resident_facing_message": message,
        "error": error,
    }


def main() -> int:
    args = parse_args()
    fixed_datetime = validate_inputs(args)
    validate_configuration()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    item_id = args.item_id.strip().upper()
    stem = item_id.lower()
    setup_path = args.output_dir / f"{stem}_condition2_setup.json"
    raw_path = args.output_dir / f"{stem}_condition2_raw.jsonl"

    if args.overwrite:
        raw_path.unlink(missing_ok=True)
        setup_path.unlink(missing_ok=True)

    image_hash = sha256_file(args.image)

    if setup_path.exists():
        setup = load_setup(setup_path)
        recorded_hash = setup.get("image", {}).get("sha256")
        if recorded_hash != image_hash:
            raise ValueError("Existing setup belongs to a different image.")
        recognition = setup["verified_interpretation"]
        user_context = setup["frozen_user_context"]
        print(f"Loaded verified setup: {setup_path}")
    else:
        normalized_bytes, normalized_name = normalize_image_orientation(args.image)
        initial = recognize_image_once(normalized_bytes, normalized_name)
        recognition, user_context, communication = interactive_verification(initial)
        user_context, communication = preflight_clarification(
            recognition, user_context, communication, fixed_datetime
        )
        setup = {
            "condition_id": CONDITION_ID,
            "item_id": item_id,
            "created_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(),
            "image": {
                "path": str(args.image.resolve()),
                "filename": args.image.name,
                "sha256": image_hash,
            },
            "area_id": AREA_ID,
            "language_code": LANGUAGE_CODE,
            "fixed_experiment_datetime": fixed_datetime.isoformat(),
            "models": {
                "vision": "gpt-4.1-mini",
                "text_recognition": "gpt-4.1-mini",
                "reasoning": "gpt-4.1-mini",
                "localization": "gpt-4.1-mini",
            },
            "initial_interpretation": initial,
            "communication_record": communication,
            "verified_interpretation": recognition,
            "frozen_user_context": user_context,
            "runs_requested": args.runs,
            "ground_truth_used": False,
            "scoring_included": False,
        }
        save_setup(setup_path, setup)
        print(f"\nVerified setup saved: {setup_path}")

    completed = existing_runs(raw_path)
    print(f"\nStarting {args.runs} repeated downstream runs for {item_id}.")
    for run_number in range(1, args.runs + 1):
        if run_number in completed:
            print(f"Run {run_number}/{args.runs}: already saved, skipping")
            continue
        print(f"Run {run_number}/{args.runs}: running ...", end="", flush=True)
        record = run_trial(
            item_id=item_id,
            run_number=run_number,
            image_path=args.image,
            image_hash=image_hash,
            recognition=recognition,
            user_context=user_context,
            fixed_datetime=fixed_datetime,
        )
        append_jsonl(raw_path, record)
        print(f" {record['status']}")

    print("\nCondition 2 data collection completed for this image.")
    print("No ground-truth comparison or scoring was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
