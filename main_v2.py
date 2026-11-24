import json
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

import streamlit as st
from PIL import Image, ImageOps

from app.config import validate_configuration
from app.illustration_service import select_result_illustrations
from app.knowledge_loader import load_knowledge_base
from app.language_service import (
    build_language_instruction,
    get_area_option_label,
    get_area_options,
    get_language_code,
    get_ui_text,
)
from app.pipeline import recognize_waste_item, reason_about_recognized_item
from app.recognition_reply_service import interpret_recognition_reply
from app.response_localizer import localize_result_message
from app.text_recognition_service import recognize_item_from_text


st.set_page_config(
    page_title="Kitami Gomi AI Prototype",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def initialize_state() -> None:
    defaults = {
        "v2_messages": [],
        "v2_language": "English",
        "v2_previous_language": "English",
        "v2_area_id": None,
        "v2_previous_area_id": None,
        "v2_phase": "idle",
        "v2_pending_recognition": None,
        "v2_confirmed_recognition": None,
        "v2_latest_result": None,
        "v2_original_text": "",
        "v2_pending_question": None,
        "v2_clarification_history": [],
        "v2_camera_nonce": 0,
        "v2_pending_camera_submission": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_conversation() -> None:
    st.session_state.v2_messages = []
    st.session_state.v2_phase = "idle"
    st.session_state.v2_pending_recognition = None
    st.session_state.v2_confirmed_recognition = None
    st.session_state.v2_latest_result = None
    st.session_state.v2_original_text = ""
    st.session_state.v2_pending_question = None
    st.session_state.v2_clarification_history = []
    st.session_state.v2_camera_nonce += 1
    st.session_state.v2_pending_camera_submission = None


def normalize_image_orientation(image_bytes: bytes, image_name: str) -> tuple[bytes, str]:
    """Apply EXIF orientation once for chat preview and AI input."""
    if not image_bytes:
        raise ValueError("The image file is empty.")

    suffix = Path(image_name).suffix.lower()
    output = BytesIO()
    with Image.open(BytesIO(image_bytes)) as source:
        image = ImageOps.exif_transpose(source)
        image.load()
        if suffix == ".png":
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA")
            image.save(output, format="PNG", optimize=True)
            normalized_name = str(Path(image_name).with_suffix(".png"))
        elif suffix == ".webp":
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGB")
            image.save(output, format="WEBP", quality=95, method=6)
            normalized_name = str(Path(image_name).with_suffix(".webp"))
        else:
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(output, format="JPEG", quality=95, optimize=True)
            normalized_name = str(Path(image_name).with_suffix(".jpg"))
    return output.getvalue(), normalized_name


def add_message(
    role: str,
    text: str = "",
    images: list[dict[str, Any]] | None = None,
    illustrations: list[dict[str, Any]] | None = None,
) -> None:
    st.session_state.v2_messages.append(
        {
            "role": role,
            "text": text,
            "images": images or [],
            "illustrations": illustrations or [],
        }
    )


def render_message(message: dict[str, Any]) -> None:
    with st.chat_message(message.get("role", "assistant")):
        for image in message.get("images", []):
            st.image(image["bytes"], width=230)
        if message.get("text"):
            st.markdown(message["text"])
        for illustration in message.get("illustrations", []):
            st.image(
                illustration["image_path"],
                width=185,
                caption=illustration.get("label", ""),
            )
            if illustration.get("note"):
                st.caption(illustration["note"])


def language_code() -> str:
    return get_language_code(st.session_state.v2_language)


def ui(en: str, ja: str) -> str:
    return ja if language_code() == "ja" else en


@st.dialog("Important notice / ご利用上の注意")
def show_important_notice() -> None:
    """Show the complete Version 1 notice without cluttering the chat page."""
    if language_code() == "ja":
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
        st.warning(
            "This application is an unofficial personal research and demonstration "
            "prototype. AI-based image recognition and responses may contain "
            "mistakes. Results are not official waste-sorting determinations by "
            "Kitami City."
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


@st.dialog("Developer details / 開発者向け詳細")
def show_developer_details() -> None:
    """Show technical output only when explicitly requested from Settings."""
    result = st.session_state.v2_latest_result
    if result:
        st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")
    else:
        st.info(
            ui(
                "Developer details will appear after reasoning.",
                "分別判断後に詳細が表示されます。",
            )
        )


def build_recognition_message(recognition: dict[str, Any], from_image: bool) -> str:
    primary = recognition.get("primary_object", {})
    components = recognition.get("components", [])
    code = language_code()

    if code == "ja":
        name = primary.get("name_ja") or primary.get("name_en") or "不明な品目"
        first = f"写真の品目を **{name}** と認識しました。" if from_image else f"品目を **{name}** と理解しました。"
        names = [
            component.get("name_ja") or component.get("name_en")
            for component in components
            if isinstance(component, dict)
            and (component.get("name_ja") or component.get("name_en"))
        ]
        lines = [first]
        if names:
            lines.append("構成部分: " + "、".join(names))
        lines.append("この認識で合っていますか？")
        return "\n\n".join(lines)

    name = primary.get("name_en") or primary.get("name_ja") or "an unidentified item"
    first = f"I recognize the photographed item as **{name}**." if from_image else f"I understand the item as **{name}**."
    names = [
        component.get("name_en") or component.get("name_ja")
        for component in components
        if isinstance(component, dict)
        and (component.get("name_en") or component.get("name_ja"))
    ]
    lines = [first]
    if names:
        lines.append("Components: " + ", ".join(names))
    lines.append("Is this recognition correct?")
    return "\n\n".join(lines)


def recognize_from_image(image_bytes: bytes, image_name: str, note: str) -> dict[str, Any]:
    suffix = Path(image_name).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as file:
            file.write(image_bytes)
            temp_path = Path(file.name)
        context = (
            f"{build_language_instruction(language_code())}\n\n"
            "Recognition stage only. Identify the photographed object and relevant "
            "components. Do not perform waste classification or disposal reasoning.\n"
            f"User information: {note or get_ui_text(language_code(), 'default_request')}"
        )
        return recognize_waste_item(image_path=temp_path, user_text=context)
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


def recognize_from_text(text: str, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    knowledge = load_knowledge_base()
    return recognize_item_from_text(
        user_description=text,
        vision_schema=knowledge["vision_schema"],
        language_code=language_code(),
        previous_recognition=previous,
    )


def build_reasoning_context(extra_text: str = "") -> str:
    parts = []
    if st.session_state.v2_original_text:
        parts.append(f"Original user information: {st.session_state.v2_original_text}")
    if extra_text.strip():
        parts.append(extra_text.strip())
    if st.session_state.v2_clarification_history:
        parts.append(
            "Treat the following clarification answers as current facts. Do not ask "
            "an already answered question again unless it is ambiguous or contradictory."
        )
        for index, exchange in enumerate(st.session_state.v2_clarification_history, start=1):
            parts.append(
                f"Clarification {index} question: {exchange['question']}\n"
                f"Clarification {index} answer: {exchange['answer']}"
            )
    return "\n\n".join(parts)


def run_reasoning(extra_text: str = "") -> None:
    recognition = st.session_state.v2_confirmed_recognition
    if not recognition:
        raise ValueError("No confirmed recognition is available.")
    if not st.session_state.v2_area_id:
        raise ValueError(ui("Select a service area in Settings.", "設定で収集地域を選択してください。"))

    result = reason_about_recognized_item(
        vision_result=recognition,
        user_text=build_reasoning_context(extra_text),
        area_id=st.session_state.v2_area_id,
    )
    st.session_state.v2_latest_result = result

    if result.get("result_status") == "needs_clarification":
        clarification = result.get("clarification", {})
        question = (
            clarification.get("question_ja") if language_code() == "ja" else clarification.get("question_en")
        ) or clarification.get("question")
        st.session_state.v2_pending_question = question
        st.session_state.v2_phase = "clarification"
    else:
        st.session_state.v2_pending_question = None
        st.session_state.v2_phase = "final"

    text = localize_result_message(result=result, language_code=language_code())
    illustrations = select_result_illustrations(result, language_code=language_code())
    add_message("assistant", text=text, illustrations=illustrations)


def begin_submission(text: str, images: list[dict[str, Any]]) -> None:
    if not st.session_state.v2_area_id:
        add_message(
            "assistant",
            ui("Please select your service area in Settings first.", "先に設定で収集地域を選択してください。"),
        )
        return

    if st.session_state.v2_phase in {"recognition_correction", "recognition_other"}:
        if not text.strip():
            add_message("assistant", ui("Please describe the item correctly.", "正しい品目を文章で教えてください。"))
            return
        corrected = recognize_from_text(text.strip(), st.session_state.v2_pending_recognition)
        st.session_state.v2_pending_recognition = corrected
        st.session_state.v2_phase = "recognition"
        add_message("assistant", build_recognition_message(corrected, from_image=False))
        return

    if st.session_state.v2_phase == "clarification":
        if not text.strip():
            return
        question = st.session_state.v2_pending_question or ""
        st.session_state.v2_clarification_history.append({"question": question, "answer": text.strip()})
        st.session_state.v2_pending_question = None
        run_reasoning(f"User clarification: {text.strip()}")
        return

    reset_conversation()
    st.session_state.v2_original_text = text.strip()
    add_message("user", text=text.strip(), images=images)

    if images:
        image = images[0]
        recognition = recognize_from_image(image["bytes"], image["name"], text.strip())
        from_image = True
    elif text.strip():
        recognition = recognize_from_text(text.strip())
        from_image = False
    else:
        return

    st.session_state.v2_pending_recognition = recognition
    st.session_state.v2_phase = "recognition"
    add_message("assistant", build_recognition_message(recognition, from_image=from_image))


def handle_recognition_action(action: str) -> None:
    if action == "confirm":
        st.session_state.v2_confirmed_recognition = st.session_state.v2_pending_recognition
        st.session_state.v2_phase = "reasoning"
        add_message("user", "〇")
        add_message("assistant", ui("Recognition confirmed. Checking Kitami City information.", "認識を確認しました。北見市の情報を確認します。"))
        run_reasoning("Recognition confirmed by the user.")
    elif action == "reject":
        add_message("user", "×")
        st.session_state.v2_phase = "recognition_correction"
        add_message("assistant", ui("Please describe the item correctly.", "正しい品目を文章で教えてください。"))
    else:
        add_message("user", ui("Other", "その他"))
        st.session_state.v2_phase = "recognition_other"
        add_message("assistant", ui("Please add any detail that would help identify the item.", "品目の特定に役立つ情報を入力してください。"))


def handle_clarification_action(answer: str) -> None:
    question = st.session_state.v2_pending_question or ""
    display = {"yes": "〇", "no": "×", "other": ui("Other", "その他")}[answer]
    add_message("user", display)
    if answer == "other":
        st.session_state.v2_phase = "clarification"
        add_message("assistant", ui("Please provide the relevant detail in text.", "関連する情報を文章で入力してください。"))
        return

    answer_text = "Yes." if answer == "yes" else "No."
    if language_code() == "ja":
        answer_text = "はい。" if answer == "yes" else "いいえ。"
    st.session_state.v2_clarification_history.append({"question": question, "answer": answer_text})
    st.session_state.v2_pending_question = None
    run_reasoning(f"User clarification: {answer_text}")


initialize_state()

try:
    validate_configuration()
except Exception as error:
    st.error("Configuration error")
    st.exception(error)
    st.stop()

knowledge = load_knowledge_base()
area_options = get_area_options(knowledge["collection_schedule"])
area_records = {area["area_id"]: area for area in area_options}
area_ids = [area["area_id"] for area in area_options]

st.markdown(
    """
    <style>
    [data-testid="stMainBlockContainer"] {
        width: 100%;
        max-width: 860px;
        margin-left: auto;
        margin-right: auto;
        padding-top: 2rem;
        padding-bottom: 0.5rem;
    }
    .v2-title {text-align:center; font-size:1.65rem; font-weight:750; margin:0.15rem 0 0.2rem 0;}
    .v2-subtitle {text-align:center; color:#6b7280; font-size:0.9rem; margin-bottom:0.6rem;}
    [data-testid="stChatMessage"] {border-radius:0.9rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

top_left, top_center, settings_column = st.columns(
    [1.15, 4.6, 0.75],
    vertical_alignment="center",
)
with top_left:
    if st.button("← Home", key="v2_home"):
        st.switch_page("home.py")
with top_center:
    st.markdown(
        '<div class="v2-title">♻️ Kitami Gomi AI Prototype</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="v2-subtitle">Version 2.0</div>',
        unsafe_allow_html=True,
    )
with settings_column:
    with st.popover("⚙️", help="Settings", use_container_width=True):
        st.selectbox(
            "Language / 言語",
            ["English", "日本語"],
            key="v2_language",
        )
        st.selectbox(
            ui("Service area", "収集地域"),
            options=area_ids,
            index=None,
            placeholder=ui("Select area", "地域を選択"),
            format_func=lambda area_id: get_area_option_label(
                area_records[area_id],
                language_code(),
            ),
            key="v2_area_id",
        )
        if st.button(
            ui("Important notice", "ご利用上の注意"),
            use_container_width=True,
            key="v2_open_notice",
        ):
            show_important_notice()
        if st.button(
            ui("Developer details", "開発者向け詳細"),
            use_container_width=True,
            key="v2_open_developer_details",
        ):
            show_developer_details()
        if st.button(
            ui("Clear conversation", "会話を消去"),
            use_container_width=True,
        ):
            reset_conversation()
            st.rerun()

if st.session_state.v2_language != st.session_state.v2_previous_language:
    reset_conversation()
    st.session_state.v2_previous_language = st.session_state.v2_language
if st.session_state.v2_area_id != st.session_state.v2_previous_area_id:
    reset_conversation()
    st.session_state.v2_previous_area_id = st.session_state.v2_area_id

pending_camera = st.session_state.v2_pending_camera_submission
if pending_camera:
    st.session_state.v2_pending_camera_submission = None
    try:
        with st.spinner(ui("Checking photo...", "写真を確認中...")):
            begin_submission(
                pending_camera.get("text", ""),
                pending_camera.get("images", []),
            )
    except Exception as error:
        add_message(
            "assistant",
            ui(
                "The analysis could not be completed.",
                "分析を完了できませんでした。",
            ),
        )
        st.session_state.v2_latest_result = {"error": str(error)}
    st.session_state.v2_camera_nonce += 1
    st.rerun()

st.divider()
chat_area = st.container(height=380, border=False)
with chat_area:
    if not st.session_state.v2_messages:
        with st.chat_message("assistant"):
            st.markdown(ui("Send a message or attach a photo of a waste item.", "メッセージを送るか、ごみの写真を添付してください。"))
    else:
        for stored_message in st.session_state.v2_messages:
            render_message(stored_message)

if st.session_state.v2_phase == "recognition":
    yes_column, no_column, other_column = st.columns(3)
    with yes_column:
        if st.button("〇", use_container_width=True, key="v2_recognition_yes"):
            handle_recognition_action("confirm")
            st.rerun()
    with no_column:
        if st.button("×", use_container_width=True, key="v2_recognition_no"):
            handle_recognition_action("reject")
            st.rerun()
    with other_column:
        if st.button(ui("その他", "その他"), use_container_width=True, key="v2_recognition_other"):
            handle_recognition_action("other")
            st.rerun()
elif st.session_state.v2_phase == "clarification" and st.session_state.v2_pending_question:
    yes_column, no_column, other_column = st.columns(3)
    with yes_column:
        if st.button("〇", use_container_width=True, key="v2_clarification_yes"):
            handle_clarification_action("yes")
            st.rerun()
    with no_column:
        if st.button("×", use_container_width=True, key="v2_clarification_no"):
            handle_clarification_action("no")
            st.rerun()
    with other_column:
        if st.button("その他", use_container_width=True, key="v2_clarification_other"):
            handle_clarification_action("other")
            st.rerun()

input_controls = st.container()
with input_controls:
    camera_column, message_column = st.columns(
        [1.15, 5.85],
        gap="small",
        vertical_alignment="bottom",
    )
    with camera_column:
        with st.popover(
            "📷 " + ui("Camera", "カメラ"),
            help=ui("Take a photo", "写真を撮影"),
        ):
            camera_photo = st.camera_input(
                ui("Take a photo", "写真を撮影"),
                key=f"v2_camera_{st.session_state.v2_camera_nonce}",
            )
            camera_note = st.text_input(
                ui("Optional message", "任意のメッセージ"),
                key="v2_camera_note",
            )
            if st.button(
                ui("Use photo", "写真を使用"),
                disabled=camera_photo is None,
                use_container_width=True,
                key="v2_use_camera_photo",
            ):
                normalized_bytes, normalized_name = normalize_image_orientation(
                    camera_photo.getvalue(),
                    "camera_capture.jpg",
                )
                st.session_state.v2_pending_camera_submission = {
                    "text": camera_note,
                    "images": [
                        {"name": normalized_name, "bytes": normalized_bytes}
                    ],
                }
                st.rerun()
    with message_column:
        submission = st.chat_input(
            ui("Message Kitami Gomi AI", "北見ごみ分別AIにメッセージ"),
            key="v2_chat_input",
            accept_file=True,
            file_type=["jpg", "jpeg", "png", "webp"],
        )

if submission:
    text = getattr(submission, "text", "") or ""
    files = getattr(submission, "files", []) or []
    images = []
    try:
        for uploaded_file in files:
            image_bytes, image_name = normalize_image_orientation(uploaded_file.getvalue(), uploaded_file.name)
            images.append({"name": image_name, "bytes": image_bytes})
        if text.strip() or images:
            if st.session_state.v2_phase not in {"recognition_correction", "recognition_other", "clarification"}:
                add_message("user", text=text.strip(), images=images)
                # begin_submission resets and re-adds for a new item, so remove this temporary entry.
                st.session_state.v2_messages.pop()
            with st.spinner(ui("Checking...", "確認中...")):
                begin_submission(text, images)
    except Exception as error:
        add_message("assistant", ui("The analysis could not be completed.", "分析を完了できませんでした。"))
        st.session_state.v2_latest_result = {"error": str(error)}
    st.rerun()
