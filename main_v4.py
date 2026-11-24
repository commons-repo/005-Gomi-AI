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
        "v4_language": "English",
        "v4_previous_language": "English",
        "v4_area_id": None,
        "v4_previous_area_id": None,
        "v4_photo_bytes": None,
        "v4_photo_name": None,
        "v4_note": "",
        "v4_recognition": None,
        "v4_confirmed_recognition": None,
        "v4_result": None,
        "v4_phase": "idle",
        "v4_pending_question": None,
        "v4_clarification_history": [],
        "v4_camera_nonce": 0,
        "v4_upload_nonce": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def language_code() -> str:
    return get_language_code(st.session_state.v4_language)


def ui(en: str, ja: str) -> str:
    return ja if language_code() == "ja" else en


def clear_result(keep_photo: bool = True) -> None:
    st.session_state.v4_recognition = None
    st.session_state.v4_confirmed_recognition = None
    st.session_state.v4_result = None
    st.session_state.v4_phase = "idle"
    st.session_state.v4_pending_question = None
    st.session_state.v4_clarification_history = []
    if not keep_photo:
        st.session_state.v4_photo_bytes = None
        st.session_state.v4_photo_name = None
        st.session_state.v4_note = ""
        st.session_state.v4_camera_nonce += 1
        st.session_state.v4_upload_nonce += 1


def normalize_image_orientation(image_bytes: bytes, image_name: str) -> tuple[bytes, str]:
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
            name = str(Path(image_name).with_suffix(".png"))
        elif suffix == ".webp":
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGB")
            image.save(output, format="WEBP", quality=95, method=6)
            name = str(Path(image_name).with_suffix(".webp"))
        else:
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(output, format="JPEG", quality=95, optimize=True)
            name = str(Path(image_name).with_suffix(".jpg"))
    return output.getvalue(), name


def recognize_photo() -> dict[str, Any]:
    image_bytes = st.session_state.v4_photo_bytes
    if not image_bytes:
        raise ValueError(ui("Add a photo first.", "先に写真を追加してください。"))
    name = st.session_state.v4_photo_name or "photo.jpg"
    suffix = Path(name).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as file:
            file.write(image_bytes)
            temporary_path = Path(file.name)
        context = (
            f"{build_language_instruction(language_code())}\n\n"
            "Recognition stage only. Identify the photographed object and relevant "
            "separable components. Do not decide disposal yet.\n"
            f"User information: {st.session_state.v4_note or get_ui_text(language_code(), 'default_request')}"
        )
        return recognize_waste_item(temporary_path, context)
    finally:
        if temporary_path:
            temporary_path.unlink(missing_ok=True)


def recognize_text(text: str, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    knowledge = load_knowledge_base()
    return recognize_item_from_text(
        user_description=text,
        vision_schema=knowledge["vision_schema"],
        language_code=language_code(),
        previous_recognition=previous,
    )


def recognition_name(recognition: dict[str, Any] | None) -> str:
    primary = (recognition or {}).get("primary_object", {})
    if language_code() == "ja":
        return primary.get("name_ja") or primary.get("name_en") or "不明な品目"
    return primary.get("name_en") or primary.get("name_ja") or "Unidentified item"


def reasoning_context(extra: str = "") -> str:
    parts = []
    if st.session_state.v4_note.strip():
        parts.append(f"Original user information: {st.session_state.v4_note.strip()}")
    if extra.strip():
        parts.append(extra.strip())
    if st.session_state.v4_clarification_history:
        parts.append("Treat these clarification answers as current facts:")
        for exchange in st.session_state.v4_clarification_history:
            parts.append(f"Question: {exchange['question']}\nAnswer: {exchange['answer']}")
    return "\n\n".join(parts)


def run_reasoning(extra: str = "") -> None:
    recognition = st.session_state.v4_confirmed_recognition
    if not recognition:
        raise ValueError("No confirmed recognition is available.")
    if not st.session_state.v4_area_id:
        raise ValueError(
            ui(
                "Select a service area in Settings.",
                "設定で収集地域を選択してください。",
            )
        )
    result = reason_about_recognized_item(
        vision_result=recognition,
        user_text=reasoning_context(extra),
        area_id=st.session_state.v4_area_id,
    )
    st.session_state.v4_result = result
    if result.get("result_status") == "needs_clarification":
        clarification = result.get("clarification", {})
        question = (
            clarification.get("question_ja") if language_code() == "ja"
            else clarification.get("question_en")
        ) or clarification.get("question")
        st.session_state.v4_pending_question = question
        st.session_state.v4_phase = "clarification"
    else:
        st.session_state.v4_pending_question = None
        st.session_state.v4_phase = "final"


def result_item_name(result: dict[str, Any]) -> str:
    """Return the localized final item name for the compact result view."""
    identified = result.get("identified_item", {})
    if language_code() == "ja":
        return identified.get("name_ja") or identified.get("name_en") or "判定品目"
    return identified.get("name_en") or identified.get("name_ja") or "Identified item"

def result_decisions(result: dict[str, Any]) -> list[dict[str, Any]]:
    components = result.get("components", [])
    if isinstance(components, list) and components:
        return [item for item in components if isinstance(item, dict)]
    disposal = result.get("disposal", {})
    return [disposal] if isinstance(disposal, dict) and disposal else []


@st.dialog("Important notice / ご利用上の注意")
def show_important_notice() -> None:
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

**関連資料の閲覧用ギャラリー**
- [北見ごみ分別AI 関連資料ギャラリー](https://ghosh-ak.github.io/gomi-agent-source-documents/)  
  北見市ウェブサイトから取得した関連資料を、閲覧しやすいようにまとめた独自の資料リポジトリです。情報は元の公式資料と照合してください。
            """
        )
    else:
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


@st.dialog("Developer details / 開発者向け詳細")
def show_developer_details() -> None:
    details = {
        "recognition": st.session_state.v4_recognition,
        "result": st.session_state.v4_result,
    }
    if any(details.values()):
        st.code(json.dumps(details, ensure_ascii=False, indent=2), language="json")
    else:
        st.info(ui("Details will appear after analysis.", "分析後に詳細が表示されます。"))


initialize_state()

try:
    validate_configuration()
except Exception as error:
    st.error(ui("Configuration error", "設定エラー"))
    st.exception(error)
    st.stop()

knowledge = load_knowledge_base()
area_options = get_area_options(knowledge["collection_schedule"])
area_records = {area["area_id"]: area for area in area_options}
area_ids = [area["area_id"] for area in area_options]

if st.session_state.v4_language != st.session_state.v4_previous_language:
    clear_result(keep_photo=True)
    st.session_state.v4_previous_language = st.session_state.v4_language

if st.session_state.v4_area_id != st.session_state.v4_previous_area_id:
    clear_result(keep_photo=True)
    st.session_state.v4_previous_area_id = st.session_state.v4_area_id

st.markdown(
    """
    <style>
    [data-testid="stMainBlockContainer"] {
        width: 100%; max-width: 1500px; margin-left: auto; margin-right: auto;
        padding-top: 3.75rem; padding-bottom: 0.5rem;
    }

    .v3-title {
        text-align: center;
        font-size: 1.65rem;
        font-weight: 750;
        margin: 0.1rem 0 0.15rem 0;
    }

    .v3-subtitle {
        text-align: center;
        color: #6b7280;
        font-size: 0.9rem;
        margin-bottom: 0.25rem;
    }

    .panel-heading {
        text-align: center;
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 0.6rem;
    }

    .recognition-name {
        text-align: center;
        font-size: 1rem;
        font-weight: 400;
        padding: 0.4rem 0;
    }

    .category-name {
        text-align: center;
        font-size: 1rem;
        font-weight: 400;
        margin: 0.3rem 0;
    }
    
    </style>
    """,
    unsafe_allow_html=True,
)

left, center, right = st.columns([1.1, 5.8, 1.1], vertical_alignment="center")
with left:
    if st.button("← Home", key="v4_home"):
        st.switch_page("home.py")
with center:
    st.markdown('<div class="v3-title">♻️ Kitami Gomi AI Prototype</div>', unsafe_allow_html=True)
    st.markdown('<div class="v3-subtitle">Version 4.0</div>', unsafe_allow_html=True)
with right:
    with st.popover("⚙️", help="Settings", use_container_width=True):
        st.selectbox("Language / 言語", ["English", "日本語"], key="v4_language")
        st.selectbox(
            ui("Service area", "収集地域"),
            options=area_ids,
            index=None,
            placeholder=ui("Select area", "地域を選択"),
            format_func=lambda area_id: get_area_option_label(
                area_records[area_id], language_code()
            ),
            key="v4_area_id",
        )
        if st.button(ui("Important notice", "ご利用上の注意"), use_container_width=True):
            show_important_notice()
        if st.button(ui("Developer details", "開発者向け詳細"), use_container_width=True):
            show_developer_details()
        if st.button(ui("Start over", "最初からやり直す"), use_container_width=True):
            clear_result(keep_photo=False)
            st.rerun()

st.divider()
photo_column, recognition_column, disposal_column = st.columns(3, gap="medium")

with photo_column:
    with st.container(height=455, border=True):
        st.markdown(f'<div class="panel-heading">{ui("1. Photo", "1. 写真")}</div>', unsafe_allow_html=True)
        if st.session_state.v4_photo_bytes:
            st.image(
                st.session_state.v4_photo_bytes,
                width=60,
            )

        else:
            st.info(ui("Add or take a photo.", "写真を追加または撮影してください。"))

        upload_tab, camera_tab = st.tabs([ui("Attach", "添付"), ui("Camera", "カメラ")])
        with upload_tab:
            uploaded = st.file_uploader(
                ui("Choose photo", "写真を選択"),
                type=["jpg", "jpeg", "png", "webp"],
                key=f"v4_upload_{st.session_state.v4_upload_nonce}",
                label_visibility="collapsed",
            )
            if uploaded is not None:
                image_bytes, image_name = normalize_image_orientation(uploaded.getvalue(), uploaded.name)
                if image_bytes != st.session_state.v4_photo_bytes:
                    st.session_state.v4_photo_bytes = image_bytes
                    st.session_state.v4_photo_name = image_name
                    clear_result(keep_photo=True)
                    st.rerun()
        with camera_tab:
            captured = st.camera_input(
                ui("Take photo", "写真を撮影"),
                key=f"v4_camera_{st.session_state.v4_camera_nonce}",
                label_visibility="collapsed",
            )
            if captured is not None:
                image_bytes, image_name = normalize_image_orientation(captured.getvalue(), "camera_capture.jpg")
                if image_bytes != st.session_state.v4_photo_bytes:
                    st.session_state.v4_photo_bytes = image_bytes
                    st.session_state.v4_photo_name = image_name
                    clear_result(keep_photo=True)
                    st.rerun()

        st.text_input(
            ui("Optional item information", "任意の品目情報"),
            key="v4_note",
            placeholder=ui("Example: still contains liquid", "例：中に液体が残っています"),
        )
        if st.button(
            ui("Recognize", "認識する"),
            type="primary",
            use_container_width=True,
            disabled=(
                not bool(st.session_state.v4_photo_bytes)
                or not bool(st.session_state.v4_area_id)
            ),
        ):
            try:
                with st.spinner(ui("Recognizing...", "認識中...")):
                    st.session_state.v4_recognition = recognize_photo()
                st.session_state.v4_confirmed_recognition = None
                st.session_state.v4_result = None
                st.session_state.v4_phase = "recognition"
            except Exception as error:
                st.error(ui("Recognition failed.", "認識できませんでした。"))
                st.session_state.v4_result = {"error": str(error)}
            st.rerun()

with recognition_column:
    with st.container(height=455, border=True):
        st.markdown(f'<div class="panel-heading">{ui("2. Recognition", "2. 認識結果")}</div>', unsafe_allow_html=True)
        recognition = st.session_state.v4_recognition
        if recognition:
            st.markdown(f'<div class="recognition-name">{recognition_name(recognition)}</div>', unsafe_allow_html=True)
            components = recognition.get("components", [])
            if components:
                component_names = [
                    (item.get("name_ja") if language_code() == "ja" else item.get("name_en"))
                    or item.get("name_en") or item.get("name_ja")
                    for item in components if isinstance(item, dict)
                ]
                if component_names:
                    st.caption(ui("Parts: ", "構成部分：") + " / ".join(component_names))

            yes, no = st.columns(2)
            with yes:
                if st.button(
                    "〇",
                    help=ui("Correct", "正しい"),
                    use_container_width=True,
                    key="v4_recognition_correct",
                ):
                    st.session_state.v4_confirmed_recognition = recognition
                    try:
                        with st.spinner(ui("Checking...", "確認中...")):
                            run_reasoning("Recognition confirmed by the user.")
                    except Exception as error:
                        st.session_state.v4_result = {"error": str(error)}
                    st.rerun()
            with no:
                if st.button(
                    "×",
                    help=ui("Change", "修正"),
                    use_container_width=True,
                    key="v4_recognition_change",
                ):
                    st.session_state.v4_phase = "correction"
                    st.rerun()
        else:
            st.info(ui("Recognition will appear here.", "認識結果がここに表示されます。"))

        correction = st.text_input(
            ui("Describe or correct the item", "品目を説明または修正"),
            key="v4_correction",
            placeholder=ui("You can also identify an item using text only.", "文字だけでも品目を確認できます。"),
        )
        if st.button(
            ui("Use text", "文字で確認"),
            use_container_width=True,
            disabled=not bool(correction.strip()),
        ):
            try:
                with st.spinner(ui("Recognizing...", "認識中...")):
                    st.session_state.v4_recognition = recognize_text(correction.strip(), recognition)
                st.session_state.v4_note = correction.strip()
                st.session_state.v4_confirmed_recognition = None
                st.session_state.v4_result = None
                st.session_state.v4_phase = "recognition"
            except Exception as error:
                st.session_state.v4_result = {"error": str(error)}
            st.rerun()

        clarification_history = st.session_state.v4_clarification_history

        if clarification_history:
            st.markdown(
                f"**{ui('Clarification record', '確認記録')}**"
            )

            for exchange in clarification_history:
                question_text = exchange.get("question", "")
                answer_text = exchange.get("answer", "")

                if question_text:
                    st.markdown(
                        f"**{ui('Question', '質問')}:** {question_text}"
                    )

                if answer_text:
                    st.markdown(
                        f"**{ui('Answer', '回答')}:** {answer_text}"
                    )

        if st.session_state.v4_phase == "clarification":
            question = st.session_state.v4_pending_question
            if question:
                st.warning(question)
                answer = st.text_input(ui("Your answer", "回答"), key="v4_clarification_answer")
                yes, no, send = st.columns(3)
                choices = [
                    (yes, "〇", "Yes", "はい", "v4_yes"),
                    (no, "×", "No", "いいえ", "v4_no"),
                ]
                for column, symbol, en, ja, key in choices:
                    with column:
                        if st.button(
                            symbol,
                            help=ui(en, ja),
                            use_container_width=True,
                            key=key,
                        ):
                            value = ui(en, ja)
                            st.session_state.v4_clarification_history.append({"question": question, "answer": value})
                            try:
                                run_reasoning(f"User clarification: {value}")
                            except Exception as error:
                                st.session_state.v4_result = {"error": str(error)}
                            st.rerun()
                with send:
                    if st.button(ui("Send", "送信"), use_container_width=True, disabled=not answer.strip()):
                        st.session_state.v4_clarification_history.append({"question": question, "answer": answer.strip()})
                        try:
                            run_reasoning(f"User clarification: {answer.strip()}")
                        except Exception as error:
                            st.session_state.v4_result = {"error": str(error)}
                        st.rerun()

with disposal_column:
    with st.container(height=455, border=True):
        st.markdown(
            f'<div class="panel-heading">{ui("3. Disposal", "3. 分別方法")}</div>',
            unsafe_allow_html=True,
        )
        result = st.session_state.v4_result

        if not result:
            if not st.session_state.v4_area_id:
                st.info(
                    ui(
                        "Select your service area in Settings, then analyze an item.",
                        "設定で収集地域を選択してから品目を判定してください。",
                    )
                )
            else:
                st.info(
                    ui(
                        "The disposal result will appear here.",
                        "分別結果がここに表示されます。",
                    )
                )
        elif result.get("error"):
            st.error(
                ui(
                    "The result could not be produced.",
                    "結果を作成できませんでした。",
                )
            )
        elif result.get("result_status") == "needs_clarification":
            st.info(
                ui(
                    "Answer the question in Panel 2.",
                    "パネル2の質問に回答してください。",
                )
            )
        elif result.get("result_status") != "final":
            st.warning(
                ui(
                    "No sufficiently supported result was found.",
                    "十分な根拠のある結果を確認できませんでした。",
                )
            )
        else:
            st.markdown(
                f'<div class="category-name"><strong>{result_item_name(result)}</strong></div>',
                unsafe_allow_html=True,
            )

            illustrations = select_result_illustrations(result, language_code())
            if illustrations:
                image_columns = st.columns(len(illustrations))
                for column, illustration in zip(image_columns, illustrations):
                    with column:
                        st.image(
                            illustration["image_path"],
                            width=205,
                            caption=illustration.get("label", ""),
                        )
            else:
                st.caption(
                    ui(
                        "No applicable disposal illustration is available.",
                        "該当する排出方法のイラストはありません。",
                    )
                )

            with st.expander(
                ui("View disposal information", "分別情報を表示"),
                expanded=False,
            ):
                st.markdown(
                    localize_result_message(
                        result=result,
                        language_code=language_code(),
                    )
                )
                for illustration in illustrations:
                    if illustration.get("note"):
                        st.caption(illustration["note"])
                        break
