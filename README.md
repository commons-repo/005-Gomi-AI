# Gomi AI: Localized Waste-Disposal Assistance

This repository contains the source code, knowledge resources, experimental materials, and evaluation records for a localized waste-disposal assistant developed for Kitami City, Japan. The assistant connects interpreted item information with municipal disposal rules, preparation requirements, and area-specific collection schedules. Four progressively developed versions of the assistant are included.

## Running the Assistant

### 1. Obtain the Repository

Clone the repository:

```powershell
git clone https://github.com/commons-repo/005-Gomi-AI.git
cd 005-Gomi-AI
```

Alternatively, download the repository as a ZIP file and extract it.

### 2. Create and Activate a Virtual Environment

Python 3.10 or later is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install the Dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure the OpenAI API Key

Open `.env.example` and enter a valid OpenAI API key:

```text
OPENAI_API_KEY=your_api_key_here
```

Rename `.env.example` to `.env`.

The `.env` file contains private credentials and must not be committed or shared publicly.

### 5. Start the Assistant

```powershell
python -m streamlit run main.py
```

The home screen provides access to all four versions of the assistant. Version 4 is the version used for the reported evaluation.

## Experimental Procedures and Results

The repository includes two experiment runners corresponding to the two evaluated conditions.

### Condition 1: Agent-Only Process

`run_condition1_agent_only.py` processes each image through the agent-only process. The initial Item Interpretation is accepted without correction, and requests for additional item information are bypassed.

Run the complete experiment with:

```powershell
python .\run_condition1_agent_only.py --image-dir "images" --output-dir "condition1_results" --runs 50
```

The runner produces:

- `condition1_metadata.json`
- One raw `.jsonl` file for each evaluated image

### Condition 2: Verification-in-the-Loop Process

`run_condition2_verified_communication.py` first allows the Item Interpretation to be checked and corrected. Missing decision-relevant information and answers to subsequent clarification requests can be entered through Verify. The resulting Item Interpretation and accumulated communication are then fixed for the repeated downstream trials.

For example, run 50 trials for `I1.jpg` with:

```powershell
python .\run_condition2_verified_communication.py --image "images\I1.jpg" --item-id I1 --output-dir "condition2_results" --runs 50
```

The runner produces:

- One setup `.json` file containing the verified inputs for the selected image
- One raw `.jsonl` file containing the repeated trial outputs

The `condition1_results/` and `condition2_results/` directories already contain the outputs used in the reported evaluation. Rerunning an experiment with the same output directory may replace or modify the existing records. To preserve the published records, first copy them elsewhere or specify a different output directory, for example:

```powershell
--output-dir "condition1_results_new"
```

or:

```powershell
--output-dir "condition2_results_new"
```

## Evaluation Materials

The `evaluation/` directory contains:

- `ground truth for evaluation.txt`
- `condition1_scores.csv`
- `condition2_scores.csv`

Ground-truth references were established for the 21 images using the official municipal source documents. Each reference specifies the expected item and disposal-relevant components, applicable disposal category or alternative route, component separation, required preparation and safety instructions, and collection information when relevant.

The raw outputs stored in `condition1_results/` and `condition2_results/` were manually compared with the corresponding ground-truth references. Item Interpretation and resident-facing Guidance were evaluated independently using binary scores:

- `1`: Agreement with the essential ground-truth information
- `0`: Disagreement with the essential ground-truth information

No partial credit was assigned. Optional preparation details, harmless supplementary instructions, and valid alternative disposal routes were accepted when they did not materially change or contradict the required disposal action.

Each scoring file contains 1,050 evaluated trials, corresponding to 21 images and 50 runs per image. The scores were used to calculate the item-level and overall correct-response rates reported in the paper.

## Repository Contents

- `app/`: Modular interpretation, retrieval, reasoning, scheduling, localization, verification, and validation services
- `bag_images/`: Disposal-method illustrations used by the assistant
- `images/`: The 21 images used in the evaluation
- `knowledge_base/`: Machine-accessible municipal waste-disposal knowledge
- `source_documents/`: Official source documents used to prepare the Knowledge Base
- `specs/`: Task instructions, decision rules, and structured-output specifications
- `condition1_results/`: Raw outputs from the agent-only experiment
- `condition2_results/`: Verified setups and raw outputs from the verification-in-the-loop experiment
- `evaluation/`: Ground-truth references and final binary scores
- `main.py`: Streamlit application entry point
- `main_v1.py`–`main_v4.py`: Four progressively developed versions of the assistant
- `run_condition1_agent_only.py`: Condition 1 experiment runner
- `run_condition2_verified_communication.py`: Condition 2 experiment runner
- `requirements.txt`: Python dependencies
- `.env.example`: Environment-variable template

## Scope

The municipal knowledge and collection schedules in this repository correspond to the evaluated Kitami City setting. Applying the software to another municipality requires replacing the Knowledge Base and collection schedules with verified information from the relevant local authority.
