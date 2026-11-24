#!/usr/bin/env python3
"""Condition 1 experiment runner for Kitami Gomi AI Version 4.

Condition 1: image-only, agent-only completion.

For each numbered image, this runner:
1. normalizes EXIF orientation using the same policy as main_v4.py;
2. calls the existing Version 4 recognition pipeline;
3. automatically accepts the initial Item Interpretation;
4. calls the existing retrieval, reasoning, scheduling, and localization code;
5. bypasses user clarification and produces the strongest result supported by
   the available Item Interpretation and official evidence; and
6. writes raw outcomes only, without ground-truth comparison or scoring.

Expected project layout:
    project_root/
        app/
        images/
        knowledge_base/
        specs/
        .env
        run_condition1_agent_only.py

Image files may be named I1.jpg ... I21.jpg, 1.jpg ... 21.jpg, or with
zero-padded numbering such as 01.jpg. JPEG, PNG, and WEBP are supported.

Full experiment:
    python .\run_condition1_agent_only.py --image-dir "images" --output-dir "condition1_results" --runs 50

Two-run test using only I1:
    python .\run_condition1_agent_only.py --image-dir "images" --output-dir "condition1_results_test" --first-item 1 --last-item 1 --runs 2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps

# Ensure imports resolve when this script is placed in the project root.
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from app.config import validate_configuration
from app.language_service import build_language_instruction, get_ui_text
from app.pipeline import recognize_waste_item, reason_about_recognized_item
from app.response_localizer import localize_result_message
import app.evidence_reasoner as evidence_reasoner


CONDITION_ID = "condition_1_agent_only"
AREA_ID = "tabata"
LANGUAGE_CODE = "en"
DEFAULT_RUNS = 50
DEFAULT_FIRST_ITEM = 1
DEFAULT_LAST_ITEM = 21
DEFAULT_EXPERIMENT_DATETIME = "2026-09-17T12:00:00+09:00"
SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

# This addition changes only the interaction policy for the controlled
# no-communication condition. The existing Version 4 reasoner, schemas,
# retrieval logic, validation, categories, schedule service, and localizer
# remain in use.
NO_COMMUNICATION_POLICY = """
Controlled experiment condition: no user communication is available.
Do not return needs_clarification and do not ask the user a question.
Using only the supplied vision analysis, user context already present, and
retrieved official evidence, produce the strongest evidence-supported final
result. Do not invent any unseen fact or municipal rule.
When an unknown condition does not prevent an evidence-supported category,
provide the supported category and preserve the official conditional
preparation or exception in the preparation steps.
If the supplied evidence cannot support any responsible decision at all,
return unsupported rather than guessing.
""".strip()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Kitami Gomi AI Condition 1 on numbered images and save raw "
            "outcomes without scoring."
        )
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        required=True,
        help="Folder containing images such as I1.jpg ... I21.jpg or 1.jpg ... 21.jpg.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Folder in which experiment outputs will be written.",
    )
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--first-item", type=int, default=DEFAULT_FIRST_ITEM)
    parser.add_argument("--last-item", type=int, default=DEFAULT_LAST_ITEM)
    parser.add_argument(
        "--experiment-datetime",
        default=DEFAULT_EXPERIMENT_DATETIME,
        help=(
            "Fixed ISO datetime used for schedule calculation. Default: "
            f"{DEFAULT_EXPERIMENT_DATETIME}"
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output file instead of resuming it.",
    )
    return parser.parse_args()


def validate_arguments(args: argparse.Namespace) -> datetime:
    if not args.image_dir.is_dir():
        raise NotADirectoryError(f"Image folder not found: {args.image_dir}")
    if args.runs < 1:
        raise ValueError("--runs must be at least 1")
    if args.first_item < 1 or args.last_item < args.first_item:
        raise ValueError("Invalid item range")
    parsed = datetime.fromisoformat(args.experiment_datetime)
    japan = ZoneInfo("Asia/Tokyo")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=japan)
    else:
        parsed = parsed.astimezone(japan)
    return parsed


def find_numbered_image(image_dir: Path, item_number: int) -> Path:
    stems = (str(item_number), f"{item_number:02d}", f"I{item_number}", f"i{item_number}")
    for stem in stems:
        for extension in SUPPORTED_EXTENSIONS:
            candidate = image_dir / f"{stem}{extension}"
            if candidate.is_file():
                return candidate
            upper = image_dir / f"{stem}{extension.upper()}"
            if upper.is_file():
                return upper
    raise FileNotFoundError(
        f"No image found for I{item_number} in {image_dir}. "
        f"Expected a numbered JPG, JPEG, PNG, or WEBP file."
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_image_orientation(image_path: Path) -> tuple[bytes, str]:
    """Match the image-normalization policy implemented in main_v4.py."""
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
            normalized_name = image_path.with_suffix(".png").name
        elif suffix == ".webp":
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGB")
            image.save(output, format="WEBP", quality=95, method=6)
            normalized_name = image_path.with_suffix(".webp").name
        else:
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(output, format="JPEG", quality=95, optimize=True)
            normalized_name = image_path.with_suffix(".jpg").name
    return output.getvalue(), normalized_name


def build_v4_recognition_context() -> str:
    return (
        f"{build_language_instruction(LANGUAGE_CODE)}\n\n"
        "Recognition stage only. Identify the photographed object and relevant "
        "separable components. Do not decide disposal yet.\n"
        f"User information: {get_ui_text(LANGUAGE_CODE, 'default_request')}"
    )


@contextmanager
def no_communication_reasoning_policy() -> Iterator[None]:
    """Temporarily add the Condition 1 policy to the existing reasoner prompt."""
    original_builder = evidence_reasoner.build_reasoning_instructions

    def condition_1_builder() -> str:
        return f"{original_builder()}\n\n{NO_COMMUNICATION_POLICY}"

    evidence_reasoner.build_reasoning_instructions = condition_1_builder
    try:
        yield
    finally:
        evidence_reasoner.build_reasoning_instructions = original_builder


def existing_run_numbers(jsonl_path: Path) -> set[int]:
    completed: set[int] = set()
    if not jsonl_path.exists():
        return completed
    with jsonl_path.open("r", encoding="utf-8") as source:
        for line in source:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            run_number = record.get("run_number")
            if isinstance(run_number, int):
                completed.add(run_number)
    return completed


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as destination:
        destination.write(json.dumps(record, ensure_ascii=False) + "\n")
        destination.flush()


def run_one_trial(
    item_id: str,
    run_number: int,
    original_image: Path,
    normalized_bytes: bytes,
    normalized_name: str,
    image_hash: str,
    fixed_datetime: datetime,
) -> dict[str, Any]:
    started_at = datetime.now(ZoneInfo("Asia/Tokyo"))
    monotonic_start = time.perf_counter()
    recognition: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    resident_message: str | None = None
    error: dict[str, Any] | None = None

    suffix = Path(normalized_name).suffix.lower() or ".jpg"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            temporary.write(normalized_bytes)
            temporary_path = Path(temporary.name)

        recognition = recognize_waste_item(
            image_path=temporary_path,
            user_text=build_v4_recognition_context(),
        )

        # Automatic acceptance, with no correction and no user-supplied facts.
        with no_communication_reasoning_policy():
            result = reason_about_recognized_item(
                vision_result=recognition,
                user_text="Recognition accepted automatically under Condition 1; no user communication was provided.",
                current_date=fixed_datetime,
                area_id=AREA_ID,
            )

        resident_message = localize_result_message(result, LANGUAGE_CODE)
    except Exception as exception:
        error = {
            "type": type(exception).__name__,
            "message": str(exception),
            "traceback": traceback.format_exc(),
        }
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    completed_at = datetime.now(ZoneInfo("Asia/Tokyo"))
    duration_seconds = round(time.perf_counter() - monotonic_start, 6)
    status = "error" if error else str((result or {}).get("result_status", "unknown"))

    return {
        "condition_id": CONDITION_ID,
        "item_id": item_id,
        "run_number": run_number,
        "status": status,
        "communication_used": False,
        "automatic_interpretation_acceptance": True,
        "area_id": AREA_ID,
        "language_code": LANGUAGE_CODE,
        "fixed_experiment_datetime": fixed_datetime.isoformat(),
        "image": {
            "original_path": str(original_image.resolve()),
            "original_filename": original_image.name,
            "normalized_filename": normalized_name,
            "sha256": image_hash,
        },
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": duration_seconds,
        "initial_interpretation": recognition,
        "structured_result": result,
        "resident_facing_message": resident_message,
        "error": error,
    }


def write_metadata(
    path: Path,
    args: argparse.Namespace,
    fixed_datetime: datetime,
    images: dict[str, Path],
) -> None:
    metadata = {
        "condition_id": CONDITION_ID,
        "description": (
            "Image-only, agent-only completion using existing Kitami Gomi AI "
            "Version 4 components. No user correction or clarification answer."
        ),
        "created_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(),
        "area_id": AREA_ID,
        "language_code": LANGUAGE_CODE,
        "runs_per_item": args.runs,
        "first_item": args.first_item,
        "last_item": args.last_item,
        "fixed_experiment_datetime": fixed_datetime.isoformat(),
        "models": {
            "vision": "gpt-4.1-mini",
            "reasoning": "gpt-4.1-mini",
            "localization": "gpt-4.1-mini",
        },
        "communication_policy": NO_COMMUNICATION_POLICY,
        "python_version": sys.version,
        "platform": platform.platform(),
        "images": {
            item_id: {
                "path": str(image.resolve()),
                "filename": image.name,
                "sha256": sha256_file(image),
            }
            for item_id, image in images.items()
        },
        "scoring_included": False,
        "ground_truth_used": False,
    }
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_arguments()
    fixed_datetime = validate_arguments(args)
    validate_configuration()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    images: dict[str, Path] = {}
    for number in range(args.first_item, args.last_item + 1):
        images[f"I{number}"] = find_numbered_image(args.image_dir, number)

    metadata_path = args.output_dir / "condition1_metadata.json"
    write_metadata(metadata_path, args, fixed_datetime, images)

    recognition_context = build_v4_recognition_context()
    print(f"Condition: {CONDITION_ID}")
    print(f"Items: I{args.first_item} to I{args.last_item}")
    print(f"Runs per item: {args.runs}")
    print(f"Area: {AREA_ID}")
    print(f"Fixed experiment datetime: {fixed_datetime.isoformat()}")
    print(f"Recognition context: {recognition_context!r}")
    print(f"Outputs: {args.output_dir.resolve()}")

    for item_id, image_path in images.items():
        output_path = args.output_dir / f"{item_id.lower()}_condition1_raw.jsonl"
        if args.overwrite and output_path.exists():
            output_path.unlink()
        completed_runs = existing_run_numbers(output_path)

        normalized_bytes, normalized_name = normalize_image_orientation(image_path)
        image_hash = sha256_file(image_path)
        print(f"\n{item_id}: {image_path.name}")

        for run_number in range(1, args.runs + 1):
            if run_number in completed_runs:
                print(f"  Run {run_number}/{args.runs}: already saved, skipping")
                continue

            print(f"  Run {run_number}/{args.runs}: running ...", end="", flush=True)
            record = run_one_trial(
                item_id=item_id,
                run_number=run_number,
                original_image=image_path,
                normalized_bytes=normalized_bytes,
                normalized_name=normalized_name,
                image_hash=image_hash,
                fixed_datetime=fixed_datetime,
            )
            append_jsonl(output_path, record)
            print(f" {record['status']}")

    print("\nCondition 1 data collection completed.")
    print("No ground-truth comparison or scoring was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
