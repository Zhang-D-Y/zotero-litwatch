# Zotero LitWatch

Zotero LitWatch is a literature radar system for continuous research-topic tracking. It is extended from Jianxinnn's `Zotero-review-generation / Zotero Chat`: it keeps the original local Zotero AI literature-assistant capabilities and adds a LitWatch pipeline for automated discovery of topic-relevant papers, screening and deduplication, Zotero import dry-runs, deep research reports, related-work matrices, must-read lists, paper-positioning reports, and visual literature knowledge graphs.

This is not a fully original project. It inherits the core code of the upstream Zotero Chat project and adds LitWatch scripts, configuration, workflows, and documentation. When redistributing, republishing, or further deriving this project, please preserve the upstream attribution and license notice.

---

## Project Overview

The original Zotero Chat is a local AI literature assistant built around a Zotero library. It can scan Zotero collections, read local PDF attachments, generate AI summaries, run Deep Research, categorize papers, chat with papers, perform semantic search and global search, and provide a FastAPI backend with a Next.js frontend.

LitWatch adds an automated workflow for research-topic literature tracking:

```text
Public literature search
→ Candidate metadata normalization
→ Local screening, scoring, and deduplication
→ Zotero import dry-run
→ Human confirmation
→ Zotero --commit import
→ Deep Research report
→ Related-work matrix
→ Must-read list
→ Paper-positioning report
→ Literature knowledge graph
```

LitWatch emphasizes human confirmation by default: you should always run a dry-run first, inspect the report, and only then use `--commit` to write to Zotero.

---

## Features

### Inherited Zotero Chat Features

- Scan Zotero collections and list items.
- Read local Zotero PDF attachments.
- Generate AI summaries for one or multiple papers.
- Generate Deep Research reports based on selected papers and a research question.
- Quickly group papers into topics using abstracts.
- Chat with selected papers.
- Build a local semantic-search index for the current collection.
- Run keyword-based Global Search across the entire Zotero library.
- Provide a FastAPI backend and a Next.js frontend.

### New LitWatch Features

- Search public literature sources based on YAML configuration.
- Normalize, score, screen, and deduplicate candidate papers.
- Generate a dry-run import plan before any Zotero write.
- Write to Zotero only when the user explicitly runs `--commit`.
- Generate tags, notes, and collection/subcollection organization for imported papers.
- Generate search reports, screen reports, and import reports for auditability.
- Output deep research reports, related-work matrices, must-read lists, and paper-positioning reports.
- Generate literature knowledge graphs in HTML, GraphML, JSON, and Markdown formats.
- Audit LitWatch outputs for quality and consistency.

---

## Architecture

- **FastAPI backend**: `api.py` and `main.py` provide the Zotero Chat API and CLI entry points.
- **Next.js frontend**: `web-ui/` provides the browser UI for collection scanning, paper selection, AI tools, and search.
- **Zotero client**: `zotero/` manages Zotero API access, local metadata, collections, and data models.
- **AI provider**: `ai/` calls an OpenAI-compatible chat provider according to `.env`; DeepSeek-compatible endpoints can be used through OpenAI-compatible configuration.
- **LitWatch tools**: `tools/` contains scripts for search, screening, Zotero import, knowledge-graph generation, and quality audit.
- **Topic config**: `configs/lit_watch_template.yaml` is a generic topic-search template. Users should copy it and adapt it to their own research topic.
- **Generated artifacts**: `artifacts/` stores runtime outputs such as JSONL files, CSV files, Markdown reports, and graphs. It is excluded from clean releases by default.

---

## Project Structure

```text
.
├── ai/                       # AI prompts, summarization, research, categorization, and chat logic
├── indexer/                  # Zotero collection scanning and semantic indexing
├── zotero/                   # Zotero API client, models, and collection utilities
├── utils/                    # Logging, PDF extraction, and general utilities
├── web-ui/                   # Next.js frontend
├── tools/                    # LitWatch pipeline scripts
│   ├── lit_watch_search.py
│   ├── lit_watch_screen.py
│   ├── lit_watch_import_zotero.py
│   ├── lit_watch_kg.py
│   └── lit_watch_quality_audit.py
├── configs/                  # LitWatch YAML configuration
│   └── lit_watch_template.yaml
├── artifacts/                # LitWatch-generated outputs; excluded from release by default
├── api.py                    # FastAPI app
├── main.py                   # CLI and API launcher
├── config.py                 # Environment-variable configuration
├── requirements.txt          # Python dependencies
├── .env.example              # Environment template without real keys
├── README.md                 # English documentation
├── README_CN.md              # Chinese documentation
├── ATTRIBUTION.md            # Upstream attribution and extension notes
├── SECURITY_CHECKLIST.md     # Pre-release security checklist
└── RELEASE_MANIFEST.md       # Clean-release package notes
```

---

## Requirements

- Python >= 3.9
- `uv`
- Node.js >= 18
- Zotero Desktop
- Zotero API key
- Access to the local Zotero data directory for reading local attachments
- An OpenAI-compatible AI provider
- Optional: a DeepSeek-compatible service configured through the OpenAI-compatible interface

---

## Installation

### Windows PowerShell

```powershell
git clone https://github.com/<your-username>/zotero-litwatch.git
cd zotero-litwatch

irm https://astral.sh/uv/install.ps1 | iex

uv venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt

cd web-ui
npm.cmd install
cd ..
```

If PowerShell blocks `npm` because of the execution policy, use:

```powershell
npm.cmd install
npm.cmd run dev
```

### Linux/macOS

```bash
git clone https://github.com/<your-username>/zotero-litwatch.git
cd zotero-litwatch

curl -LsSf https://astral.sh/uv/install.sh | sh

uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt

cd web-ui
npm install
cd ..
```

---

## Configuration

Copy `.env.example` to a local `.env` file and fill in your own values. Do not commit `.env`.

### Windows PowerShell

```powershell
Copy-Item .env.example .env
notepad .env
```

### Linux/macOS

```bash
cp .env.example .env
${EDITOR:-vi} .env
```

Core configuration:

```env
ZOTERO_LIBRARY_ID=your_library_id
ZOTERO_LIBRARY_TYPE=user
ZOTERO_API_KEY=your_zotero_api_key
ZOTERO_DATA_DIR=C:/Users/<user>/Zotero

AI_PROVIDER=openai
AI_API_KEY=your_api_key
AI_MODEL=gpt-4o-mini
AI_API_BASE=
```

DeepSeek-compatible example:

```env
AI_PROVIDER=openai
AI_API_KEY=your_deepseek_key
AI_MODEL=deepseek-chat
AI_API_BASE=https://api.deepseek.com
```

Zotero settings:

- Create or manage your Zotero API key at `https://www.zotero.org/settings/keys`.
- Use `ZOTERO_LIBRARY_TYPE=user` for a personal library and `group` for a group library.
- On Windows, paths using `/` are recommended, for example: `ZOTERO_DATA_DIR=C:/Users/<user>/Zotero`.

---

## Running Zotero Chat

You need two terminal windows.

### Window 1: Start the backend

Windows PowerShell:

```powershell
cd zotero-litwatch
uv run python main.py ui --port 8000
```

Linux/macOS:

```bash
cd zotero-litwatch
uv run python main.py ui --port 8000
```

### Window 2: Start the frontend

Windows PowerShell:

```powershell
cd zotero-litwatch\web-ui
npm.cmd run dev
```

Linux/macOS:

```bash
cd zotero-litwatch/web-ui
npm run dev
```

Open the browser at:

```text
http://localhost:3000
```

The backend defaults to:

```text
http://localhost:8000
```

If the frontend needs an explicit backend address, use the following in Windows PowerShell:

```powershell
$env:NEXT_PUBLIC_API_URL="http://localhost:8000"
npm.cmd run dev
```

On Linux/macOS:

```bash
export NEXT_PUBLIC_API_URL="http://localhost:8000"
npm run dev
```

---

## Zotero Chat CLI

Run from the repository root:

```powershell
uv run python main.py list
uv run python main.py scan "Collection Name"
uv run python main.py summarize "Collection Name" --limit 5
uv run python main.py research "Collection Name" -q "Question"
```

---

## Configure Your Own LitWatch Topic-Search YAML

LitWatch no longer ships with a default configuration for any specific research topic. The public version provides only a generic template:

```text
configs/lit_watch_template.yaml
```

Each user should copy the template and create a configuration for their own research direction:

```powershell
Copy-Item configs/lit_watch_template.yaml configs/my_topic_lit_watch.yaml
notepad configs/my_topic_lit_watch.yaml
```

The YAML usually contains:

```yaml
version: 1
name: Your Topic Literature Watch
description: Generic LitWatch query matrix template.

defaults:
  year_from: 2020
  max_results: 25
  source:
    - openalex
    - semantic_scholar
    - arxiv
    - crossref
  root_collection: Your-Topic-LitWatch

queries:
  - query: '"your core keyword" AND "your research task"'
    source: [openalex, semantic_scholar, arxiv, crossref]
    year_from: 2020
    max_results: 25
    tags: [replace_me, core_topic]
    target_subcollection: 01_core_papers
    inclusion_reason: Replace with why this query is central to your topic.
```

Each query should ideally cover a clear direction, such as:

- core topic: the central research problem;
- methods: major methods;
- benchmarks: datasets, benchmarks, and evaluation suites;
- evaluation metrics: metrics and validation methods;
- related work: neighboring research areas;
- limitations/open problems: limitations, challenges, and open questions;
- recent work: recent developments from the last two or three years.

### Ask AI to Generate a Topic YAML

You can send the following prompt to ChatGPT, Codex, or another coding assistant and ask it to generate a topic-specific configuration from the template:

```text
Please generate a new LitWatch YAML configuration based on configs/lit_watch_template.yaml for my research topic.

My research topic:
<Paste your research-topic description here>

Requirements:
1. Preserve the version/name/description/defaults/queries structure.
2. Generate 8-12 queries.
3. Cover core topic, methods, benchmarks, evaluation metrics, related work, limitations/open problems, and recent work.
4. Each query must include query/source/year_from/max_results/tags/target_subcollection/inclusion_reason.
5. Do not include any API key.
6. Use a short, safe, non-private root_collection name.
7. Output the file as configs/my_topic_lit_watch.yaml.
8. Do not run the search directly; let me manually inspect the YAML first.
```

After manually inspecting the YAML, run the LitWatch commands.

---

## LitWatch Workflow

### Step 1: Search public sources

Search public literature metadata according to the configuration and write raw candidates. Replace `configs/my_topic_lit_watch.yaml` with your own topic configuration.

```powershell
uv run python tools/lit_watch_search.py --config configs/my_topic_lit_watch.yaml --out artifacts/lit_watch/candidates_raw.jsonl
```

For a quick template-only test, you can also use:

```powershell
uv run python tools/lit_watch_search.py --config configs/lit_watch_template.yaml --out artifacts/lit_watch/candidates_raw.jsonl
```

### Step 2: Screen and deduplicate

Normalize records, deduplicate candidates, score relevance, and generate a screening report.

```powershell
uv run python tools/lit_watch_screen.py --input artifacts/lit_watch/candidates_raw.jsonl --out-dir artifacts/lit_watch
```

### Step 3: Dry-run Zotero import

Preview which candidate papers would be imported into Zotero. Always run a dry-run before any Zotero write.

```powershell
uv run python tools/lit_watch_import_zotero.py --input artifacts/lit_watch/candidates_screened.jsonl --min-score 4 --dry-run
```

### Step 4: Commit import after human confirmation

Only after manually checking the dry-run results and explicitly confirming should you use `--commit` to write into Zotero.

```powershell
uv run python tools/lit_watch_import_zotero.py --input artifacts/lit_watch/candidates_screened.jsonl --min-score 4 --commit
```

### Step 5: Generate a deep research report

After import, you can use the Zotero Chat CLI to generate a research report for the target collection:

```powershell
uv run python main.py list
uv run python main.py scan "Collection Name"
uv run python main.py summarize "Collection Name" --limit 30
uv run python main.py research "Collection Name" -q "Your research question"
```

### Step 6: Generate a knowledge graph

```powershell
uv run python tools/lit_watch_kg.py --input artifacts/lit_watch/candidates_screened.jsonl --out-dir artifacts/lit_watch
```

Open the graph:

```powershell
start .\artifacts\lit_watch\literature_graph.html
```

### Step 7: Audit and related-work matrix

```powershell
uv run python tools/lit_watch_quality_audit.py --input-dir artifacts/lit_watch
```

---

## Outputs

LitWatch typically generates the following files under `artifacts/lit_watch/`:

- `candidates_raw.jsonl`
- `candidates_screened.jsonl`
- `candidates_screened.csv`
- `search_report.md`
- `screen_report.md`
- `import_report.md`
- `deep_research_report.md`
- `deep_research_report_raw.txt`
- `related_work_matrix.csv`
- `related_work_matrix.md`
- `must_read_20.md`
- `paper_positioning_from_lit_v1.md`
- `literature_graph.html`
- `literature_graph.graphml`
- `literature_graph.json`
- `literature_map.md`

---

## Knowledge Graph Notes

The knowledge graph generated by LitWatch is primarily intended for exploring relationships among literature topics, tasks, methods, and evidence gates. It is not a strict citation graph.

The default graph may include:

- paper nodes
- method nodes
- task nodes
- evidence_gate nodes
- benchmark nodes
- gap nodes

Edge types may include:

- `uses`
- `addresses`
- `evaluates_on`
- `validates_with`
- `related_to`
- `leaves_open`
- `addresses_gap`

By default, paper-paper edges use conservative `related_to` links. They should not be interpreted as true citation relationships unless citation metadata is explicitly present upstream and explicitly handled by the script.

---

## Attribution

This project is based on Jianxinnn/Zotero-review-generation, referred to in the original documentation as Zotero Chat. The original project provides Zotero collection scanning, PDF reading, AI summarization, Deep Research, Categorize, Chat, Semantic Search, Global Search, a FastAPI backend, and a Next.js frontend.

This extension adds LitWatch scripts, a generic topic-configuration template, report-generation conventions, a safe import workflow, knowledge-graph generation, and release/security documentation.

---

## Disclaimer

This project is intended to assist researchers with literature discovery, screening, import, and research analysis. Automated search and AI-generated reports cannot replace human reading, citation verification, or scholarly judgment.

Users should independently verify:

- whether search results are complete;
- whether Zotero imports are accurate;
- whether AI-generated content is reliable;
- whether literature citations are real, accurate, and traceable;
- whether the usage complies with the terms of the relevant APIs, publishers, and databases.

---

## License

See the MIT License file for details.
