from typing import Any


SUPPORTED_LANGUAGES = {
    "English": "en",
    "日本語": "ja",
}


UI_TEXT = {
    "en": {
        "title": "Kitami Gomi AI Prototype",
        "subtitle": (
            "Local proof-of-concept using official "
            "Kitami City household-waste information"
        ),
        "prototype_scope": (
            "This prototype supports the four official collection-calendar "
            "groups of the Kitami Autonomous Region. Select your area so the "
            "correct collection schedule can be used."
        ),
        "covered_areas": "Supported areas",
        "area_selection": "Select your area",
        "area_selection_help": (
            "Choose the neighborhood where the waste will be collected."
        ),
        "area_not_selected": "Please select an area.",
        "calendar_group": "Calendar group",
        "language": "Response language",
        "waste_item": "Waste item",
        "upload": "Upload one clear photograph",
        "optional_information": "Optional information",
        "optional_placeholder": (
            "Example: It is empty, clean, and approximately "
            "20 cm long."
        ),
        "analyze": "Analyze new item",
        "clear": "Clear and start again",
        "conversation": "Conversation",
        "conversation_empty": (
            "Upload one image on the left and select "
            "**Analyze new item**."
        ),
        "default_request": "Please analyze this waste item.",
        "reply_placeholder": (
            "Reply or ask a follow-up question"
        ),
        "developer_details": "Developer details",
        "developer_caption": (
            "Internal information for prototype evaluation. "
            "This section would not be shown in the final "
            "resident-facing experience."
        ),
        "technical_json": "Complete technical JSON",
        "result_status": "Result status",
        "image_confidence": "Image confidence",
        "dictionary_record": "Dictionary record",
        "match_type": "Match type",
        "service_area": "Service area",
        "source_page": "Source page",
        "object": "Object",
        "category": "Category",
        "bag_or_method": "Bag or method",
        "preparation": "Preparation",
        "next_collection_date": "Next collection date",
        "put_out_by": "Put it out by",
        "safety": "Safety",
        "official_match": "Official source match",
        "no_schedule": (
            "This item does not use normal "
            "neighborhood collection."
        ),
        "no_valid_date": (
            "No valid collection date was found "
            "within the prototype calendar."
        ),
        "configuration_error": (
            "The project configuration is incomplete."
        ),
        "analysis_error": (
            "The analysis could not be completed."
        ),
        "analyzing": "Analyzing the photograph...",
        "checking_reply": (
            "Checking the reply against the photograph..."
        ),
        "prototype_warning": (
            "Prototype only. Unsupported or uncertain items "
            "should be confirmed with Kitami City."
        ),
    },
    "ja": {
        "title": "北見ごみ分別AIプロトタイプ",
        "subtitle": (
            "北見市の公式家庭ごみ情報を使用した"
            "ローカル実証用プロトタイプ"
        ),
        "prototype_scope": (
            "このプロトタイプは、北見自治区の公式ごみカレンダー"
            "1から4の対象地域に対応しています。正しい収集日を"
            "確認するため、お住まいの地域を選択してください。"
        ),
        "covered_areas": "対応地域",
        "area_selection": "お住まいの地域を選択",
        "area_selection_help": (
            "ごみを出す地域の町名を選択してください。"
        ),
        "area_not_selected": "地域を選択してください。",
        "calendar_group": "カレンダー区分",
        "language": "回答言語",
        "waste_item": "ごみ品目",
        "upload": "ごみ一品が明確に写った写真をアップロード",
        "optional_information": "補足情報",
        "optional_placeholder": (
            "例：中身は空で、洗浄済み、長さは約20cmです。"
        ),
        "analyze": "新しい品目を判定",
        "clear": "クリアして最初から",
        "conversation": "会話",
        "conversation_empty": (
            "左側から写真をアップロードして、"
            "**新しい品目を判定**を選択してください。"
        ),
        "default_request": "このごみ品目を判定してください。",
        "reply_placeholder": (
            "回答または追加の質問を入力してください"
        ),
        "developer_details": "開発者向け詳細",
        "developer_caption": (
            "プロトタイプ評価用の内部情報です。"
            "最終的な住民向け画面には表示しません。"
        ),
        "technical_json": "完全な技術JSON",
        "result_status": "判定状態",
        "image_confidence": "画像認識信頼度",
        "dictionary_record": "辞典レコード",
        "match_type": "一致方法",
        "service_area": "収集区域",
        "source_page": "出典ページ",
        "object": "判定品目",
        "category": "分別区分",
        "bag_or_method": "指定袋または排出方法",
        "preparation": "出し方",
        "next_collection_date": "次回収集日",
        "put_out_by": "排出時刻",
        "safety": "安全上の注意",
        "official_match": "公式資料の一致品目",
        "no_schedule": (
            "この品目は通常のごみステーション収集の"
            "対象ではありません。"
        ),
        "no_valid_date": (
            "プロトタイプのカレンダー期間内に"
            "有効な収集日が見つかりませんでした。"
        ),
        "configuration_error": (
            "プロジェクト設定が完了していません。"
        ),
        "analysis_error": "判定を完了できませんでした。",
        "analyzing": "写真を分析しています...",
        "checking_reply": (
            "写真と回答内容を確認しています..."
        ),
        "prototype_warning": (
            "このシステムはプロトタイプです。"
            "不明な品目は北見市にご確認ください。"
        ),
    },
}


CATEGORY_LABELS = {
    "en": {
        "burnable": "Burnable waste",
        "unburnable": "Unburnable waste",
        "recyclable": "Recyclable waste",
        "plastic_container_packaging": (
            "Plastic containers and packaging"
        ),
        "diapers": "Diapers",
        "hazardous": "Hazardous waste",
        "large_sized": "Large-sized waste",
        "not_accepted_by_city": (
            "Not accepted by Kitami City"
        ),
    },
    "ja": {
        "burnable": "燃やすごみ",
        "unburnable": "燃やさないごみ",
        "recyclable": "資源ごみ",
        "plastic_container_packaging": (
            "プラスチック製容器包装"
        ),
        "diapers": "紙おむつ類",
        "hazardous": "有害ごみ",
        "large_sized": "粗大ごみ",
        "not_accepted_by_city": (
            "市が処理できないごみ"
        ),
    },
}


DISPOSAL_METHOD_LABELS = {
    "en": {
        "burnable": (
            "Use the designated orange Kitami City bag."
        ),
        "unburnable": (
            "Use the designated young-grass green "
            "Kitami City bag."
        ),
        "recyclable": (
            "Use a transparent or translucent bag. "
            "Bundle paper separately by type."
        ),
        "plastic_container_packaging": (
            "Use a transparent or translucent bag."
        ),
        "diapers": (
            "Use a transparent or translucent bag "
            "of 45 litres or less."
        ),
        "hazardous": (
            "Use a transparent or translucent bag and "
            "separate each hazardous-waste type."
        ),
        "large_sized": (
            "Apply to the Large-sized Waste Reception Center. "
            "Do not use the neighborhood waste station."
        ),
        "not_accepted_by_city": (
            "Use the official retailer, manufacturer, "
            "specialist, or recycling route."
        ),
    },
    "ja": {
        "burnable": (
            "北見市指定の橙色のごみ袋を使用してください。"
        ),
        "unburnable": (
            "北見市指定の若草色のごみ袋を使用してください。"
        ),
        "recyclable": (
            "透明または半透明の袋を使用してください。"
            "紙類は種類ごとに分けてひもで縛ってください。"
        ),
        "plastic_container_packaging": (
            "透明または半透明の袋を使用してください。"
        ),
        "diapers": (
            "45リットル以下の透明または半透明の"
            "袋を使用してください。"
        ),
        "hazardous": (
            "透明または半透明の袋を使用し、"
            "有害ごみの種類ごとに分けてください。"
        ),
        "large_sized": (
            "粗大ごみ受付センターへ事前に申し込んでください。"
            "ごみステーションには出さないでください。"
        ),
        "not_accepted_by_city": (
            "販売店、メーカー、専門業者、または"
            "指定されたリサイクルルートを利用してください。"
        ),
    },
}


def get_language_code(language_label: str) -> str:
    """Return the internal language code."""

    return SUPPORTED_LANGUAGES.get(
        language_label,
        "en",
    )


def get_ui_text(
    language_code: str,
    text_key: str,
) -> str:
    """Return one interface label in the selected language."""

    language_text = UI_TEXT.get(
        language_code,
        UI_TEXT["en"],
    )

    return language_text.get(
        text_key,
        UI_TEXT["en"].get(text_key, text_key),
    )


def get_category_label(
    category_id: str,
    language_code: str,
) -> str:
    """Return one category name in the selected language."""

    labels = CATEGORY_LABELS.get(
        language_code,
        CATEGORY_LABELS["en"],
    )

    return labels.get(
        category_id,
        category_id,
    )


def get_disposal_method(
    category_id: str,
    language_code: str,
) -> str:
    """Return a disposal method in the selected language."""

    methods = DISPOSAL_METHOD_LABELS.get(
        language_code,
        DISPOSAL_METHOD_LABELS["en"],
    )

    return methods.get(
        category_id,
        category_id,
    )


def get_area_options(
    collection_schedule: dict[str, Any],
) -> list[dict[str, str]]:
    """Return bilingual area options sorted by Japanese area name."""
    area_index = collection_schedule.get("area_index", {})
    options: list[dict[str, str]] = []

    if not isinstance(area_index, dict):
        return options

    for area_id, area_record in area_index.items():
        if not isinstance(area_record, dict):
            continue

        options.append(
            {
                "area_id": str(area_id),
                "name_en": str(area_record.get("name_en", "")),
                "name_ja": str(area_record.get("name_ja", "")),
                "calendar_group_id": str(
                    area_record.get("calendar_group_id", "")
                ),
            }
        )

    return sorted(
        options,
        key=lambda option: (
            option["name_ja"],
            option["name_en"],
        ),
    )


def get_area_option_label(
    area_record: dict[str, str],
    language_code: str,
) -> str:
    """Return one area label with the selected language shown first."""
    name_en = area_record.get("name_en", "")
    name_ja = area_record.get("name_ja", "")

    if language_code == "ja":
        return f"{name_ja} ({name_en})" if name_en else name_ja

    return f"{name_en} ({name_ja})" if name_ja else name_en


def get_area_display_text(
    collection_schedule: dict[str, Any],
    language_code: str = "en",
) -> str:
    """Return a bilingual summary of all schedule-supported areas."""
    return "、".join(
        get_area_option_label(area, language_code)
        for area in get_area_options(collection_schedule)
    )


def get_response_language_name(
    language_code: str,
) -> str:
    """Return a prompt-friendly language name."""

    if language_code == "ja":
        return "Japanese"

    return "English"


def build_language_instruction(
    language_code: str,
) -> str:
    """Create a language restriction for an AI request."""

    language_name = get_response_language_name(
        language_code
    )

    return (
        f"Respond only in {language_name}. "
        "Do not mix Japanese and English in the "
        "resident-facing response. Official Japanese "
        "source terms may remain only in internal fields."
    )


def localize_basic_result(
    result: dict[str, Any],
    language_code: str,
) -> dict[str, Any]:
    """
    Apply deterministic category and method labels.

    Detailed official instructions remain unchanged until
    the pipeline performs faithful language conversion.
    """

    disposal = result.get("disposal", {})
    category_id = disposal.get("category_id")

    if not category_id:
        return result

    disposal["category_en"] = get_category_label(
        category_id,
        language_code,
    )

    disposal["bag_or_method"] = get_disposal_method(
        category_id,
        language_code,
    )

    result["disposal"] = disposal

    result.setdefault(
        "user_message",
        {},
    )["language"] = language_code

    return result