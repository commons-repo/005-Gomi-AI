import hashlib
import json
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image, ImageOps

from app.config import validate_configuration
from app.language_service import (
    build_language_instruction,
    get_area_display_text,
    get_area_option_label,
    get_area_options,
    get_language_code,
    get_ui_text,
)
from app.knowledge_loader import load_knowledge_base
from app.pipeline import (
    recognize_waste_item,
    reason_about_recognized_item,
)
from app.recognition_reply_service import interpret_recognition_reply
from app.response_localizer import localize_result_message
from app.text_recognition_service import recognize_item_from_text


st.set_page_config(
    page_title="Kitami Gomi AI Prototype",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def initialize_session_state() -> None:
    """Initialize persistent interface and conversation values."""
    defaults = {
        "messages": [],
        "uploaded_image_bytes": None,
        "uploaded_image_name": None,
        "latest_result": None,
        "original_note": "",
        "language_label": "English",
        "previous_language_label": "English",
        "selected_area_id": None,
        "previous_area_id": None,
        "interaction_mode": "Photo and Text",
        "uploader_nonce": 0,
        "camera_nonce": 0,
        "last_saved_camera_hash": None,
        "last_saved_camera_path": None,
        "conversation_phase": "recognition",
        "pending_vision_result": None,
        "confirmed_vision_result": None,
        "pending_clarification_question": None,
        "clarification_history": [],
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_conversation(keep_image: bool = True) -> None:
    """Clear conversation state, optionally retaining the image."""
    st.session_state.messages = []
    st.session_state.latest_result = None
    st.session_state.original_note = ""
    st.session_state.conversation_phase = "recognition"
    st.session_state.pending_vision_result = None
    st.session_state.confirmed_vision_result = None
    st.session_state.pending_clarification_question = None
    st.session_state.clarification_history = []

    if not keep_image:
        st.session_state.uploaded_image_bytes = None
        st.session_state.uploaded_image_name = None
        st.session_state.uploader_nonce += 1
        st.session_state.camera_nonce += 1
        st.session_state.last_saved_camera_hash = None
        st.session_state.last_saved_camera_path = None


def reset_prototype() -> None:
    """Clear the image and conversation completely."""
    clear_conversation(keep_image=False)


def normalize_image_orientation(
    image_bytes: bytes,
    image_name: str,
) -> tuple[bytes, str]:
    """Apply EXIF orientation and return normalized image bytes.

    The returned bytes are used consistently for the interface preview,
    locally saved camera image, and AI recognition input.
    """
    if not image_bytes:
        raise ValueError("The image file is empty.")

    image_suffix = Path(image_name).suffix.lower()
    output_buffer = BytesIO()

    with Image.open(BytesIO(image_bytes)) as source_image:
        normalized_image = ImageOps.exif_transpose(source_image)
        normalized_image.load()

        if image_suffix == ".png":
            if normalized_image.mode not in {"RGB", "RGBA"}:
                normalized_image = normalized_image.convert("RGBA")
            normalized_image.save(
                output_buffer,
                format="PNG",
                optimize=True,
            )
            normalized_name = str(Path(image_name).with_suffix(".png"))

        elif image_suffix == ".webp":
            if normalized_image.mode not in {"RGB", "RGBA"}:
                normalized_image = normalized_image.convert("RGB")
            normalized_image.save(
                output_buffer,
                format="WEBP",
                quality=95,
                method=6,
            )
            normalized_name = str(Path(image_name).with_suffix(".webp"))

        else:
            if normalized_image.mode != "RGB":
                normalized_image = normalized_image.convert("RGB")
            normalized_image.save(
                output_buffer,
                format="JPEG",
                quality=95,
                optimize=True,
            )
            normalized_name = str(Path(image_name).with_suffix(".jpg"))

    return output_buffer.getvalue(), normalized_name


def save_image_temporarily() -> Path:
    """Save the session image and return its temporary path."""
    image_bytes = st.session_state.uploaded_image_bytes
    if not image_bytes:
        raise ValueError("No image is available for analysis.")

    image_name = st.session_state.uploaded_image_name or "uploaded_image.jpg"
    image_suffix = Path(image_name).suffix.lower()
    if image_suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        image_suffix = ".jpg"

    with tempfile.NamedTemporaryFile(delete=False, suffix=image_suffix) as file:
        file.write(image_bytes)
        return Path(file.name)


def save_camera_image_for_testing(image_bytes: bytes) -> Path:
    """Save one camera photograph locally without duplicate rerun copies."""
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    previous_hash = st.session_state.get("last_saved_camera_hash")
    previous_path = st.session_state.get("last_saved_camera_path")

    if image_hash == previous_hash and previous_path:
        existing_path = Path(previous_path)
        if existing_path.exists():
            return existing_path

    directory = Path(__file__).resolve().parent / "test_images"
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    image_path = directory / f"test_image_{timestamp}.jpg"
    image_path.write_bytes(image_bytes)

    st.session_state.last_saved_camera_hash = image_hash
    st.session_state.last_saved_camera_path = str(image_path)
    return image_path


def add_chat_message(role: str, content: str) -> None:
    """Add one message to the persistent conversation."""
    st.session_state.messages.append({"role": role, "content": content})


def run_recognition(user_context: str | None) -> dict:
    """Run image recognition only."""
    temporary_path = None
    try:
        temporary_path = save_image_temporarily()
        return recognize_waste_item(
            image_path=temporary_path,
            user_text=user_context,
        )
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def run_text_recognition(
    user_description: str,
    language_code: str,
    previous_recognition: dict | None = None,
) -> dict:
    """Recognize an item from a text description."""
    knowledge = load_knowledge_base()
    return recognize_item_from_text(
        user_description=user_description,
        vision_schema=knowledge["vision_schema"],
        language_code=language_code,
        previous_recognition=previous_recognition,
    )


def build_recognition_message(vision_result: dict, language_code: str) -> str:
    """Create a concise recognition confirmation question."""
    primary = vision_result.get("primary_object", {})
    components = vision_result.get("components", [])

    if language_code == "ja":
        item_name = primary.get("name_ja") or primary.get("name_en") or "不明な品目"
        introduction = (
            f"写真の品目を **{item_name}** と認識しました。"
            if st.session_state.interaction_mode == "Photo and Text"
            else f"品目を **{item_name}** と理解しました。"
        )
        lines = [introduction]
        names = [
            component.get("name_ja") or component.get("name_en")
            for component in components
            if isinstance(component, dict)
            and (component.get("name_ja") or component.get("name_en"))
        ]
        if names:
            lines.append("構成部分: " + "、".join(names))
        lines.append("この認識で合っていますか？違う場合は、正しい品目を文章で教えてください。")
        return "\n\n".join(lines)

    item_name = primary.get("name_en") or primary.get("name_ja") or "an unidentified item"
    introduction = (
        f"I recognize the photographed item as **{item_name}**."
        if st.session_state.interaction_mode == "Photo and Text"
        else f"I understand the item as **{item_name}**."
    )
    lines = [introduction]
    names = [
        component.get("name_en") or component.get("name_ja")
        for component in components
        if isinstance(component, dict)
        and (component.get("name_en") or component.get("name_ja"))
    ]
    if names:
        lines.append("Components: " + ", ".join(names))
    lines.append(
        "Is this recognition correct? If not, please describe the item correctly in your reply."
    )
    return "\n\n".join(lines)


def initial_recognition_context(optional_note: str, language_code: str) -> str:
    """Build the first recognition-only instruction."""
    note = optional_note or get_ui_text(language_code, "default_request")
    return (
        f"{build_language_instruction(language_code)}\n\n"
        "Recognition stage only. Identify the photographed object and relevant "
        "components. Do not perform waste classification or disposal reasoning.\n"
        f"User information: {note}"
    )


def correction_recognition_context(reply: str, language_code: str) -> str:
    """Build a recognition correction instruction from the user's text."""
    previous = st.session_state.pending_vision_result or {}
    previous_name = previous.get("primary_object", {}).get("name_en", "")
    return (
        f"{build_language_instruction(language_code)}\n\n"
        "Recognition correction stage only. The user says the prior recognition "
        "was incorrect or incomplete. Update the object description and components "
        "using the photograph and the user's correction. Do not classify disposal.\n"
        f"Previous recognition: {previous_name}\n"
        f"User correction: {reply}\n"
        f"Original note: {st.session_state.original_note}"
    )


def record_clarification_answer(user_reply: str) -> None:
    """Store the pending clarification question with the user's answer."""
    question = st.session_state.pending_clarification_question
    if not question:
        return

    st.session_state.clarification_history.append(
        {"question": question, "answer": user_reply.strip()}
    )
    st.session_state.pending_clarification_question = None


def build_reasoning_context(user_context: str | None) -> str:
    """Combine the request with all previously answered clarifications."""
    parts = [user_context.strip()] if user_context and user_context.strip() else []
    history = st.session_state.clarification_history

    if history:
        parts.append(
            "Treat the following clarification answers as current facts. "
            "Do not ask an already answered question again unless the answer "
            "is genuinely ambiguous or contradictory."
        )
        for index, exchange in enumerate(history, start=1):
            parts.append(
                f"Clarification {index} question: {exchange['question']}\n"
                f"Clarification {index} answer: {exchange['answer']}"
            )

    return "\n\n".join(parts)


def normalize_question_text(question: str | None) -> str:
    """Normalize a question for duplicate comparison."""
    if not question:
        return ""
    return " ".join(question.casefold().split()).rstrip("?.。？")


def run_confirmed_reasoning(user_context: str | None, language_code: str) -> None:
    """Run grounded reasoning while preserving clarification history."""
    vision_result = st.session_state.confirmed_vision_result
    if not vision_result:
        raise ValueError("No confirmed recognition is available.")

    result = reason_about_recognized_item(
        vision_result=vision_result,
        user_text=build_reasoning_context(user_context),
        area_id=st.session_state.selected_area_id,
    )

    previous_question = None
    if st.session_state.clarification_history:
        previous_question = st.session_state.clarification_history[-1]["question"]

    clarification = result.get("clarification", {})
    new_question = (
        clarification.get("question")
        or clarification.get("question_en")
        or clarification.get("question_ja")
    )

    if result.get("result_status") == "needs_clarification" and new_question:
        if (
            normalize_question_text(new_question)
            == normalize_question_text(previous_question)
        ):
            new_question = (
                "I could not fully apply the previous answer. Please add any "
                "specific detail that may affect disposal."
                if language_code == "en"
                else "前回の回答だけでは判断に反映できませんでした。分別に関係する具体的な情報があれば追加してください。"
            )
            clarification["question"] = new_question
            result["clarification"] = clarification
            result.setdefault("user_message", {})["text"] = new_question

        st.session_state.pending_clarification_question = new_question
    else:
        st.session_state.pending_clarification_question = None

    st.session_state.latest_result = result
    add_chat_message(
        "assistant",
        localize_result_message(result=result, language_code=language_code),
    )


def display_developer_details(result: dict | None, language_code: str) -> None:
    """Display internal prototype evaluation information."""
    st.subheader(get_ui_text(language_code, "developer_details"))
    st.caption(get_ui_text(language_code, "developer_caption"))

    if not result:
        message = (
            "Developer details will appear after disposal reasoning."
            if language_code == "en"
            else "分別判断後に開発者向け詳細が表示されます。"
        )
        st.info(message)
        return

    if "error" in result:
        st.error(result["error"])
        return

    identified = result.get("identified_item", {})
    official = result.get("official_match", {})
    collection = result.get("collection", {})
    reasoning = result.get("reasoning", {})

    left, right = st.columns(2)
    with left:
        st.write(
            f"**{get_ui_text(language_code, 'image_confidence')}:** "
            f"{identified.get('confidence', 0):.0%}"
        )
        st.write(
            f"**Decision mode:** {result.get('decision_mode') or '-'}"
        )
        st.write(
            f"**Decision confidence:** "
            f"{reasoning.get('decision_confidence', 0):.0%}"
        )
    with right:
        st.write(
            f"**{get_ui_text(language_code, 'result_status')}:** "
            f"{result.get('result_status') or '-'}"
        )
        st.write(
            f"**{get_ui_text(language_code, 'dictionary_record')}:** "
            f"{official.get('dictionary_record_id') or '-'}"
        )
        area_name = (
            collection.get("service_area_name_ja")
            if language_code == "ja"
            else collection.get("service_area_name_en")
        )
        st.write(
            f"**{get_ui_text(language_code, 'service_area')}:** "
            f"{area_name or collection.get('service_area_id') or '-'}"
        )
        st.write(
            f"**{get_ui_text(language_code, 'calendar_group')}:** "
            f"{collection.get('calendar_group_id') or '-'}"
        )

    with st.expander(get_ui_text(language_code, "technical_json"), expanded=False):
        st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")


initialize_session_state()

if st.button("← Home", key="back_to_home"):
    st.switch_page("home.py")

try:
    validate_configuration()
except Exception as configuration_error:
    st.error(get_ui_text("en", "configuration_error"))
    st.exception(configuration_error)
    st.stop()

knowledge = load_knowledge_base()
collection_schedule = knowledge["collection_schedule"]

language_label = st.selectbox(
    "Response language / 回答言語",
    options=["English", "日本語"],
    key="language_label",
)

if st.session_state.language_label != st.session_state.previous_language_label:
    clear_conversation(keep_image=True)
    st.session_state.previous_language_label = st.session_state.language_label

language_code = get_language_code(language_label)

st.title(f"♻️ {get_ui_text(language_code, 'title')}")
st.caption(get_ui_text(language_code, "subtitle"))
st.write(get_ui_text(language_code, "prototype_scope"))

area_options = get_area_options(collection_schedule)
area_records = {
    area["area_id"]: area
    for area in area_options
}
area_ids = [area["area_id"] for area in area_options]

selected_area_id = st.selectbox(
    get_ui_text(language_code, "area_selection"),
    options=area_ids,
    index=None,
    placeholder=get_ui_text(language_code, "area_not_selected"),
    format_func=lambda area_id: get_area_option_label(
        area_records[area_id],
        language_code,
    ),
    help=get_ui_text(language_code, "area_selection_help"),
    key="selected_area_id",
)

if selected_area_id != st.session_state.previous_area_id:
    clear_conversation(keep_image=True)
    st.session_state.previous_area_id = selected_area_id

with st.expander(get_ui_text(language_code, "covered_areas"), expanded=False):
    st.write(
        get_area_display_text(
            collection_schedule,
            language_code,
        )
    )

left_column, right_column = st.columns([1, 2.25], gap="medium")

with left_column:
    st.markdown(f"### {get_ui_text(language_code, 'waste_item')}")

    interaction_mode = st.radio(
        (
            "How would you like to describe the item?"
            if language_code == "en"
            else "品目の伝え方を選択してください"
        ),
        options=["Photo and Text", "Text Only"],
        horizontal=True,
        key="interaction_mode",
    )

    text_description = ""
    optional_note = ""

    if interaction_mode == "Text Only":
        text_description = st.text_area(
            (
                "Describe the waste item"
                if language_code == "en"
                else "ごみの品目を文章で説明してください"
            ),
            placeholder=(
                "Example: I have a paper coffee cup that still contains coffee."
                if language_code == "en"
                else "例：コーヒーがまだ残っている紙コップです。"
            ),
            height=120,
        )

    else:
        source_options = (
            ["Upload photo", "Take photo"]
            if language_code == "en"
            else ["写真をアップロード", "カメラで撮影"]
        )
        selected_source = st.radio(
            "Image source" if language_code == "en" else "画像の入力方法",
            options=source_options,
            horizontal=True,
        )

        upload_selected = selected_source in {
            "Upload photo",
            "写真をアップロード",
        }
        new_image_bytes = None
        new_image_name = None

        if upload_selected:
            uploaded_file = st.file_uploader(
                get_ui_text(language_code, "upload"),
                type=["jpg", "jpeg", "png", "webp"],
                key=f"image_uploader_{st.session_state.uploader_nonce}",
            )
            if uploaded_file is not None:
                new_image_bytes, new_image_name = normalize_image_orientation(
                    image_bytes=uploaded_file.getvalue(),
                    image_name=uploaded_file.name,
                )
        else:
            st.caption(
                "Connect the USB camera and select it in the browser's camera settings."
                if language_code == "en"
                else "USBカメラを接続し、ブラウザのカメラ設定から選択してください。"
            )
            camera_photo = st.camera_input(
                "Take a photograph" if language_code == "en" else "写真を撮影",
                key=f"camera_input_{st.session_state.camera_nonce}",
            )
            save_for_testing = st.checkbox(
                "Save captured image in test_images"
                if language_code == "en"
                else "撮影画像を test_images に保存",
                value=True,
            )
            if camera_photo is not None:
                new_image_bytes, new_image_name = normalize_image_orientation(
                    image_bytes=camera_photo.getvalue(),
                    image_name="camera_capture.jpg",
                )
                if save_for_testing:
                    saved_path = save_camera_image_for_testing(new_image_bytes)
                    new_image_name = saved_path.name
                    st.success(
                        f"Saved as {saved_path.name}"
                        if language_code == "en"
                        else f"{saved_path.name} として保存しました"
                    )

        if new_image_bytes is not None:
            image_changed = (
                new_image_bytes != st.session_state.uploaded_image_bytes
            )
            if image_changed:
                st.session_state.uploaded_image_bytes = new_image_bytes
                st.session_state.uploaded_image_name = new_image_name
                clear_conversation(keep_image=True)

        if st.session_state.uploaded_image_bytes:
            thumbnail_column, name_column = st.columns(
                [1, 1.2],
                vertical_alignment="center",
            )
            with thumbnail_column:
                st.image(st.session_state.uploaded_image_bytes, width=150)
            with name_column:
                st.caption(
                    st.session_state.uploaded_image_name or "Current image"
                )
            with st.expander(
                "Enlarge image" if language_code == "en" else "画像を拡大",
                expanded=False,
            ):
                st.image(
                    st.session_state.uploaded_image_bytes,
                    use_container_width=True,
                )

        optional_note = st.text_area(
            get_ui_text(language_code, "optional_information"),
            placeholder=get_ui_text(language_code, "optional_placeholder"),
            height=80,
        )

    item_input_available = (
        (
            interaction_mode == "Photo and Text"
            and st.session_state.uploaded_image_bytes is not None
        )
        or (
            interaction_mode == "Text Only"
            and bool(text_description.strip())
        )
    )
    analysis_input_available = (
        selected_area_id is not None
        and item_input_available
    )

    analyze_button = st.button(
        get_ui_text(language_code, "analyze"),
        type="primary",
        use_container_width=True,
        disabled=not analysis_input_available,
    )
    clear_button = st.button(
        get_ui_text(language_code, "clear"),
        use_container_width=True,
    )

    if clear_button:
        reset_prototype()
        st.rerun()

    if analyze_button:
        note = (
            text_description.strip()
            if interaction_mode == "Text Only"
            else optional_note.strip()
        )
        st.session_state.original_note = note
        st.session_state.pending_clarification_question = None
        st.session_state.clarification_history = []
        st.session_state.messages = []
        add_chat_message(
            "user",
            note or get_ui_text(language_code, "default_request"),
        )

        try:
            with st.spinner(get_ui_text(language_code, "analyzing")):
                if interaction_mode == "Text Only":
                    recognition_result = run_text_recognition(
                        user_description=note,
                        language_code=language_code,
                    )
                else:
                    recognition_result = run_recognition(
                        initial_recognition_context(note, language_code)
                    )

            st.session_state.pending_vision_result = recognition_result
            st.session_state.confirmed_vision_result = None
            st.session_state.conversation_phase = "recognition"
            add_chat_message(
                "assistant",
                build_recognition_message(recognition_result, language_code),
            )
        except Exception as error:
            add_chat_message(
                "assistant",
                get_ui_text(language_code, "analysis_error"),
            )
            st.session_state.latest_result = {"error": str(error)}

        st.rerun()


with right_column:
    st.markdown(f"### {get_ui_text(language_code, 'conversation')}")
    conversation_container = st.container(height=430, border=True)

    with conversation_container:
        if not st.session_state.messages:
            st.info(get_ui_text(language_code, "conversation_empty"))
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    chat_input_disabled = (
        not st.session_state.messages
        or (
            interaction_mode == "Photo and Text"
            and st.session_state.uploaded_image_bytes is None
        )
    )
    chat_reply = st.chat_input(
        get_ui_text(language_code, "reply_placeholder"),
        disabled=chat_input_disabled,
    )

    if chat_reply:
        add_chat_message("user", chat_reply)

        try:
            if st.session_state.conversation_phase == "recognition":
                proposed_recognition = (
                    st.session_state.pending_vision_result or {}
                )

                with st.spinner(
                    get_ui_text(language_code, "checking_reply")
                ):
                    reply_interpretation = interpret_recognition_reply(
                        proposed_recognition=proposed_recognition,
                        user_reply=chat_reply,
                        language_code=language_code,
                    )

                reply_intent = reply_interpretation["intent"]

                if reply_intent == "confirm":
                    st.session_state.confirmed_vision_result = (
                        proposed_recognition
                    )
                    st.session_state.conversation_phase = "reasoning"
                    st.session_state.pending_clarification_question = None
                    st.session_state.clarification_history = []
                    add_chat_message(
                        "assistant",
                        (
                            "Recognition confirmed. I will now check the applicable Kitami City information."
                            if language_code == "en"
                            else "認識を確認しました。北見市の該当する公式情報を確認します。"
                        ),
                    )
                    with st.spinner(
                        get_ui_text(language_code, "checking_reply")
                    ):
                        run_confirmed_reasoning(
                            user_context=(
                                "Recognition confirmed by the user. "
                                f"Original description: {st.session_state.original_note}"
                            ),
                            language_code=language_code,
                        )

                elif reply_intent == "correct":
                    correction_text = (
                        reply_interpretation.get("correction_text")
                        or chat_reply
                    )
                    with st.spinner(
                        get_ui_text(language_code, "checking_reply")
                    ):
                        if interaction_mode == "Text Only":
                            corrected_result = run_text_recognition(
                                user_description=correction_text,
                                language_code=language_code,
                                previous_recognition=proposed_recognition,
                            )
                        else:
                            corrected_result = run_recognition(
                                correction_recognition_context(
                                    correction_text,
                                    language_code,
                                )
                            )

                    st.session_state.pending_vision_result = corrected_result
                    add_chat_message(
                        "assistant",
                        build_recognition_message(
                            corrected_result,
                            language_code,
                        ),
                    )

                elif reply_intent == "reconsider":
                    if interaction_mode == "Text Only":
                        add_chat_message(
                            "assistant",
                            (
                                "Please describe the item again and include any material, contents, size, or condition you know."
                                if language_code == "en"
                                else "品目について、材質・中身・大きさ・状態など分かることをもう一度説明してください。"
                            ),
                        )
                    else:
                        reconsider_context = (
                            f"{build_language_instruction(language_code)}\n\n"
                            "Recognition stage only. Inspect the photograph again carefully. "
                            "The user requested reconsideration. Do not perform waste classification."
                        )
                        with st.spinner(
                            get_ui_text(language_code, "checking_reply")
                        ):
                            reconsidered_result = run_recognition(
                                reconsider_context
                            )
                        st.session_state.pending_vision_result = (
                            reconsidered_result
                        )
                        add_chat_message(
                            "assistant",
                            build_recognition_message(
                                reconsidered_result,
                                language_code,
                            ),
                        )

                else:
                    add_chat_message(
                        "assistant",
                        (
                            "I could not determine whether you confirmed or corrected the recognition. Please confirm it or describe the item more clearly."
                            if language_code == "en"
                            else "認識の確認か訂正かを判断できませんでした。認識が正しいか、品目をもう少し詳しく説明してください。"
                        ),
                    )

            else:
                record_clarification_answer(chat_reply)
                with st.spinner(
                    get_ui_text(language_code, "checking_reply")
                ):
                    run_confirmed_reasoning(
                        user_context=(
                            "The recognition is already confirmed. "
                            f"Original description: {st.session_state.original_note}. "
                            f"User follow-up: {chat_reply}"
                        ),
                        language_code=language_code,
                    )

        except Exception as error:
            add_chat_message(
                "assistant",
                get_ui_text(language_code, "analysis_error"),
            )
            st.session_state.latest_result = {"error": str(error)}

        st.rerun()

st.divider()
display_developer_details(st.session_state.latest_result, language_code)
st.divider()

if language_code == "ja":
    st.markdown("### ご利用上の注意")
    st.warning(
        "本アプリは、個人による研究・実証を目的とした非公式のプロトタイプです。"
        "AIによる画像認識および回答には、誤りが含まれる可能性があります。"
        "本アプリが表示する内容は、北見市による公式なごみ分別判定ではありません。"
    )
    st.markdown(
        """
本プロトタイプは、**北見市在住の Angkush Kumar Ghosh** が、個人の研究・実証プロジェクトとして独立して開発したものです。

現時点において、本プロトタイプは、**北見市、北見市役所、またはその他の公的機関と提携したものではありません。また、それらの機関による承認、許可、運営、または共同開発によるものでもありません。**

利用者は、本アプリが表示する情報を北見市の公式資料と照合し、ご自身の判断と責任において利用してください。

**以下の北見市公式情報をご確認ください。**

- [北見自治区のごみ分別・カレンダー・区分け辞典](https://www.city.kitami.lg.jp/administration/life/detail.php?content=9346)
- [ごみ分別チラシ・区分け辞典・英語版てびき](https://www.city.kitami.lg.jp/administration/life/detail.php?content=5755)
- [北見市 ごみの分別](https://www.city.kitami.lg.jp/administration/life/category/?category=453)

**関連資料の閲覧用ギャラリー：**

- [北見ごみ分別AI 関連資料ギャラリー](https://ghosh-ak.github.io/gomi-agent-source-documents/)  
  北見市ウェブサイトから取得した関連資料を、閲覧しやすいようにまとめた独自の資料リポジトリです。情報は元の公式資料と照合してください。
"""
    )
else:
    st.markdown("### Important notice")
    st.warning(
        "This application is an unofficial personal research and demonstration "
        "prototype. AI-based image recognition and responses may contain mistakes. "
        "Results are not official waste-sorting determinations by Kitami City."
    )
    st.markdown(
        """
This prototype is independently developed by **Angkush Kumar Ghosh, a resident of Kitami City**, as a personal research and demonstration project.

At present, this prototype is **not affiliated with, endorsed by, authorized by, operated by, or developed in cooperation with Kitami City, Kitami City Office, or any other public organization**.

Users should verify the displayed information against official Kitami City resources and use the prototype based on their own judgment and responsibility.

**Please verify the information using the official Kitami City sources below:**

- [Kitami Autonomous Region waste sorting, calendar and dictionary](https://www.city.kitami.lg.jp/administration/life/detail.php?content=9346)
- [Waste guides, sorting dictionary and English guide](https://www.city.kitami.lg.jp/administration/life/detail.php?content=5755)
- [Kitami City waste-sorting portal](https://www.city.kitami.lg.jp/administration/life/category/?category=453)

"""
    )
