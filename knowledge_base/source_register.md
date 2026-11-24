# Kitami Gomi AI - Source Register

## 1. Purpose

This register documents the official source documents currently stored in `source_documents/` and the derived knowledge-base files used by the Kitami Gomi AI prototype.

The register records:

- the local standardized filename;
- the document language and role;
- the geographical and temporal scope;
- the relationship between official PDFs and derived files;
- the present verification status; and
- the planned expansion of collection-schedule coverage.

This register describes the current project state as of **August 30, 2026**. It must be updated whenever an official source or derived knowledge file is added, replaced, or revised.

## 2. Current source-document inventory

The `source_documents/` folder currently contains **11 official PDF files**:

### Kitami Autonomous Region collection calendars

1. `01_kitami_collection_calendar_1_2026_ja.pdf`
2. `01_kitami_collection_calendar_1_2026_en.pdf`
3. `01_kitami_collection_calendar_2_2026_ja.pdf`
4. `01_kitami_collection_calendar_2_2026_en.pdf`
5. `01_kitami_collection_calendar_3_2026_ja.pdf`
6. `01_kitami_collection_calendar_3_2026_en.pdf`
7. `01_kitami_collection_calendar_4_2026_ja.pdf`
8. `01_kitami_collection_calendar_4_2026_en.pdf`

### Kitami Autonomous Region sorting references

9. `02_kitami_household_waste_guide_2026_ja.pdf`
10. `03_kitami_waste_dictionary_2026_ja.pdf`
11. `04_kitami_household_waste_guide_2026_en.pdf`

The four calendar numbers represent separate official collection-calendar groups. The exact neighborhood coverage of Calendar Groups 1 through 4 must be verified from the printed headings in each PDF before the schedule data are expanded.

## 3. Source authority and conflict handling

Official sources should be applied according to their purpose rather than treated as interchangeable.

1. **Japanese item dictionary**
   - Primary source for item-specific classification, conditions, exceptions, and preparation instructions.

2. **Japanese household waste guide**
   - Primary source for general category definitions, bag requirements, size limits, preparation rules, safety requirements, and special handling.

3. **Applicable official collection calendar**
   - Primary source for collection dates, weekdays, district coverage, and calendar-specific exceptions.

4. **English collection calendar and English household guide**
   - Supporting sources for English terminology and resident-facing explanations.

5. **Conflict or uncertainty**
   - Item-specific and general-rule evidence should both be retained when they appear inconsistent.
   - The application must not silently invent a resolution.
   - When the official evidence remains insufficient or contradictory, the response should disclose the uncertainty and direct the user to the applicable Kitami City source.

## 4. Official source documents

### Source Group 1: Kitami collection calendars, Japanese editions

#### Files

- `01_kitami_collection_calendar_1_2026_ja.pdf`
- `01_kitami_collection_calendar_2_2026_ja.pdf`
- `01_kitami_collection_calendar_3_2026_ja.pdf`
- `01_kitami_collection_calendar_4_2026_ja.pdf`

#### Description

- Japanese label: **令和8年度 北見自治区ごみカレンダー**
- English label: **FY2026 Kitami Autonomous Region Waste Collection Calendars**
- Language: Japanese
- Autonomous region: Kitami Autonomous Region
- Validity: April 1, 2026 to March 31, 2027
- Number of calendar groups: Four
- Role: Authoritative Japanese references for collection-area coverage, category dates, collection weekdays, and calendar exceptions
- Planned derived output: Expanded collection-schedule data covering Calendar Groups 1 through 4
- Current verification status: Files collected; Calendar Group 1 previously used for the prototype; exact coverage and date data for all four groups require systematic verification
- Important note: The visual calendar layout is authoritative. Automatic plain-text extraction must be checked against the actual calendar pages.

### Source Group 2: Kitami collection calendars, English editions

#### Files

- `01_kitami_collection_calendar_1_2026_en.pdf`
- `01_kitami_collection_calendar_2_2026_en.pdf`
- `01_kitami_collection_calendar_3_2026_en.pdf`
- `01_kitami_collection_calendar_4_2026_en.pdf`

#### Description

- Japanese label: **令和8年度 北見自治区ごみカレンダー（英語版）**
- English label: **FY2026 Kitami Autonomous Region Waste Collection Calendars, English Editions**
- Language: English
- Autonomous region: Kitami Autonomous Region
- Validity: April 1, 2026 to March 31, 2027
- Number of calendar groups: Four
- Role: Readable supporting references for English category names, collection patterns, and cross-verification of the Japanese calendars
- Planned derived output: Expanded collection-schedule data covering Calendar Groups 1 through 4
- Current verification status: Files collected; detailed group-by-group verification pending
- Authority limitation: If the English and Japanese calendars differ or the English wording is incomplete, the corresponding Japanese calendar should be checked as the authoritative source.

### Source 3: Japanese household waste sorting guide

- Local filename: `02_kitami_household_waste_guide_2026_ja.pdf`
- Japanese label: **北見自治区のごみの分け方・出し方【家庭用】2026年改訂版**
- English label: **Kitami Autonomous Region Household Waste Sorting and Disposal Guide, 2026 Revised Edition**
- Language: Japanese
- Coverage: Kitami Autonomous Region household waste
- Edition: 2026 revised edition
- Role: Authoritative general rules for categories, designated bags, preparation, size thresholds, special handling, and safety requirements
- Derived output: `general_rules.md`
- Verification status: Previously visually inspected and structured for the prototype

### Source 4: Japanese item dictionary

- Local filename: `03_kitami_waste_dictionary_2026_ja.pdf`
- Japanese label: **令和8年度 ごみの区分け辞典（北見自治区）**
- English label: **FY2026 Waste Separation Dictionary, Kitami Autonomous Region**
- Language: Japanese
- Coverage: Kitami Autonomous Region household items
- Length: 40 pages
- Role: Primary item-level source for waste categories, preparation conditions, exceptions, and disposal instructions
- Derived output: `waste_dictionary.json`
- Verification status: 1,128 item records extracted; JSON structure validated; representative records spot-checked

### Source 5: English household waste sorting guide

- Local filename: `04_kitami_household_waste_guide_2026_en.pdf`
- Japanese label: **北見市 ごみの分け方・出し方（北見自治区・英語版）**
- English label: **Kitami City: How to Separate Trash, Kitami Autonomous Region, English Edition**
- Language: English
- Coverage: Kitami Autonomous Region household waste
- Edition date: April 2026
- Role: Supporting source for resident-facing English terminology and explanations
- Derived output: `english_guide.md`
- Verification status: Previously visually inspected and reorganized into a readable Markdown reference
- Authority limitation: The Japanese item dictionary and Japanese household guide take priority when the English wording is incomplete or ambiguous.

## 5. Derived knowledge-base files

### `general_rules.md`

- Japanese label: **北見自治区 家庭ごみ基本分別ルール**
- English label: **Kitami Autonomous Region Household Waste General Rules**
- Primary source: `02_kitami_household_waste_guide_2026_ja.pdf`
- Function: Structured category definitions, bag rules, preparation requirements, thresholds, safety logic, and general decision guidance
- Current scope: Kitami Autonomous Region

### `waste_dictionary.json`

- Japanese label: **北見自治区 品目別ごみ分別データ**
- English label: **Kitami Autonomous Region Item-Level Waste Separation Data**
- Primary source: `03_kitami_waste_dictionary_2026_ja.pdf`
- Function: Searchable item-level records used as official evidence during retrieval and reasoning
- Current scope: Kitami Autonomous Region

### `collection_schedule.json`

- Japanese label: **北見自治区 対象地域ごみ収集日程データ**
- English label: **Kitami Autonomous Region Selected-Area Collection Schedule Data**
- Current primary sources:
  - `01_kitami_collection_calendar_1_2026_en.pdf`
  - `01_kitami_collection_calendar_1_2026_ja.pdf`
- Function: Current prototype schedule data, including service-area coverage, recurrence rules, exact collection dates, and put-out time
- Current limitation: The file represents only the previously configured Calendar Group 1 service area. It does not yet represent Calendar Groups 2, 3, and 4 or the other autonomous regions of Kitami City.
- Planned action: Replace or supplement this single-area structure with verified multi-calendar schedule files and a schedule index.

### `english_guide.md`

- Japanese label: **北見自治区 ごみ分別英語案内データ**
- English label: **Kitami Autonomous Region Waste Sorting English Guidance**
- Primary source: `04_kitami_household_waste_guide_2026_en.pdf`
- Function: Clear English explanations and terminology for resident-facing responses
- Current scope: Kitami Autonomous Region

### `source_register.md`

- Japanese label: **Kitami Gomi AI 情報源管理台帳**
- English label: **Kitami Gomi AI Source Register**
- Function: Source identity, authority, provenance, local file mapping, verification status, and derived-file relationships

## 6. Current project structure

```text
gomi-bot/
├── source_documents/
│   ├── 01_kitami_collection_calendar_1_2026_en.pdf
│   ├── 01_kitami_collection_calendar_1_2026_ja.pdf
│   ├── 01_kitami_collection_calendar_2_2026_en.pdf
│   ├── 01_kitami_collection_calendar_2_2026_ja.pdf
│   ├── 01_kitami_collection_calendar_3_2026_en.pdf
│   ├── 01_kitami_collection_calendar_3_2026_ja.pdf
│   ├── 01_kitami_collection_calendar_4_2026_en.pdf
│   ├── 01_kitami_collection_calendar_4_2026_ja.pdf
│   ├── 02_kitami_household_waste_guide_2026_ja.pdf
│   ├── 03_kitami_waste_dictionary_2026_ja.pdf
│   └── 04_kitami_household_waste_guide_2026_en.pdf
└── knowledge_base/
    ├── general_rules.md
    ├── waste_dictionary.json
    ├── collection_schedule.json
    ├── english_guide.md
    └── source_register.md
```

## 7. Schedule-expansion status

### Completed

- Calendar Group 1 Japanese and English PDFs are stored locally.
- Calendar Group 1 was used to create the existing prototype schedule.
- The existing schedule provides deterministic collection-date calculation for the currently configured service area.

### Collected but not yet integrated

- Calendar Group 2 Japanese and English PDFs
- Calendar Group 3 Japanese and English PDFs
- Calendar Group 4 Japanese and English PDFs

### Still to be prepared for complete Kitami City coverage

The present source folder covers Kitami Autonomous Region materials. Complete citywide coverage will also require the applicable official calendar and sorting sources for:

- Tanno Autonomous Region;
- Tokoro Autonomous Region; and
- Rubeshibe Autonomous Region.

Those files should be entered into this register only after their local filenames, edition periods, geographical coverage, and roles have been verified.

## 8. File-management rules

- Keep the content of every official PDF unchanged.
- Local filenames may be standardized, but the mapping and document identity must be recorded in this register.
- Do not silently overwrite an older official edition with a newer one.
- When a new fiscal-year edition is published, store it as a new file and update the validity period and verification status.
- Do not infer a calendar group's neighborhood coverage from the filename alone. Verify coverage from the document itself.
- Derived JSON and Markdown files must state which official sources and calendar groups they represent.
- Schedule data must be visually checked against the official calendar before it is connected to the application.
- Keep Version 1.0 working with its currently verified schedule until expanded schedules have been separately prepared and tested.

## 9. Provenance requirement for application answers

Every final answer should be traceable, where applicable, to:

- one or more records in `waste_dictionary.json`;
- the relevant rule sections in `general_rules.md`;
- the selected and verified collection-calendar schedule;
- `english_guide.md` for resident-facing English phrasing; and
- the recognition and clarification information confirmed by the user.

If required official evidence is unavailable, conflicting, outside the configured geographical scope, or outside the schedule validity period, the application should disclose that limitation rather than inventing a category, instruction, or date.
