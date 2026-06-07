# Zotero LitWatch

Zotero LitWatch 是一个面向研究课题持续追踪的文献雷达系统。它基于 Jianxinnn 的 `Zotero-review-generation / Zotero Chat` 扩展而来，保留原本的本地 Zotero AI 文献助手能力，并新增 LitWatch pipeline，用于课题相关文献的自动检索、筛选去重、Zotero 入库预演、深度调研报告、related work 矩阵、必读清单、论文定位报告和可视化知识图谱。

本项目不是完全原创项目。它继承 upstream Zotero Chat 的核心代码，并在此基础上增加 LitWatch 脚本、配置、工作流和文档。重新发布、二次分发或继续派生时，应保留 upstream attribution 和 license notice。

---

## 项目简介

原 Zotero Chat 是围绕 Zotero 文库构建的本地 AI 文献助手，可扫描 Zotero collection、读取本地 PDF 附件、生成 AI 总结、Deep Research、Categorize、Chat、Semantic Search 和 Global Search，并提供 FastAPI 后端与 Next.js 前端。

LitWatch 在此基础上增加了一套面向“课题文献追踪”的自动化流程：

```text
公开文献检索
→ 候选文献规范化
→ 本地筛选、评分、去重
→ Zotero 导入 dry-run
→ 人工确认
→ Zotero --commit 入库
→ Deep Research 报告
→ related work 矩阵
→ must-read 清单
→ paper positioning 报告
→ 文献知识图谱
```

LitWatch 默认强调人工确认：必须先 dry-run，检查报告后才使用 `--commit` 写入 Zotero。

---

## 功能概览

### 继承的 Zotero Chat 功能

- 扫描 Zotero collection 并列出条目。
- 读取本地 Zotero PDF 附件。
- 对单篇或多篇文献生成 AI 总结。
- 针对选中文献和研究问题生成 Deep Research 报告。
- 基于摘要进行快速主题分类。
- 与选中文献进行问答式 Chat。
- 为当前 collection 建立本地语义搜索索引。
- 在整个 Zotero 文库中进行关键词 Global Search。
- 提供 FastAPI 后端和 Next.js 前端。

### 新增的 LitWatch 功能

- 根据 YAML 配置检索公开文献来源。
- 对候选文献进行规范化、评分、筛选和去重。
- 在任何 Zotero 写入前生成 dry-run 导入计划。
- 仅当用户显式运行 `--commit` 时才写入 Zotero。
- 为导入文献生成 tags、notes 和 collection/subcollection 组织结构。
- 生成 search report、screen report 和 import report，便于审计。
- 输出 deep research report、related work matrix、must-read list 和 paper positioning report。
- 生成 HTML、GraphML、JSON 和 Markdown 格式的文献知识图谱。
- 对 LitWatch 输出进行质量审计。

---

## 系统架构

- **FastAPI backend**：`api.py` 和 `main.py` 提供 Zotero Chat API 与 CLI 入口。
- **Next.js frontend**：`web-ui/` 提供浏览器界面，用于 collection 扫描、文献选择、AI 工具和搜索。
- **Zotero client**：`zotero/` 负责 Zotero API、本地元数据、collection 管理和数据模型。
- **AI provider**：`ai/` 按 `.env` 配置调用 OpenAI-compatible chat provider；DeepSeek-compatible endpoint 可通过 OpenAI-compatible 配置接入。
- **LitWatch tools**：`tools/` 包含检索、筛选、Zotero 导入、知识图谱和质量审计脚本。
- **Topic config**：`configs/lit_watch_template.yaml` 是通用课题检索模板，用户应复制后改成自己的课题配置。
- **Generated artifacts**：`artifacts/` 存放 JSONL、CSV、Markdown 报告和图谱等运行输出，默认不作为发布包内容。

---

## 项目结构

```text
.
├── ai/                       # AI prompt、总结、研究、分类和对话逻辑
├── indexer/                  # Zotero collection 扫描和语义索引
├── zotero/                   # Zotero API client、模型和 collection 工具
├── utils/                    # 日志、PDF 提取和通用工具
├── web-ui/                   # Next.js 前端
├── tools/                    # LitWatch pipeline 脚本
│   ├── lit_watch_search.py
│   ├── lit_watch_screen.py
│   ├── lit_watch_import_zotero.py
│   ├── lit_watch_kg.py
│   └── lit_watch_quality_audit.py
├── configs/                  # LitWatch YAML 配置
│   └── lit_watch_template.yaml
├── artifacts/                # LitWatch 生成文件，默认不作为发布输入
├── api.py                    # FastAPI 应用
├── main.py                   # CLI 和 API 启动器
├── config.py                 # 环境变量配置
├── requirements.txt          # Python 依赖
├── .env.example              # 环境变量模板，不包含真实 key
├── README.md                 # 英文文档
├── README_CN.md              # 中文文档
├── ATTRIBUTION.md            # 上游来源和扩展说明
├── SECURITY_CHECKLIST.md     # 发布前安全检查清单
└── RELEASE_MANIFEST.md       # clean release 包说明
```

---

## 环境要求

- Python >= 3.9
- `uv`
- Node.js >= 18
- Zotero Desktop
- Zotero API key
- 可访问本地 Zotero data directory，用于读取本地附件
- OpenAI-compatible AI provider
- 可选：通过 OpenAI-compatible 配置接入 DeepSeek-compatible 服务

---

## 安装

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

如果 `npm` 在 PowerShell 中被执行策略拦截，可以使用：

```powershell
npm.cmd install
npm.cmd run dev
```

### Linux/macOS

```bash
git clone https://github.com/Zhang-D-Y/zotero-litwatch.git
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

## 配置

从 `.env.example` 复制本地配置文件并填写。不要提交 `.env`。

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

核心配置项：

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

DeepSeek-compatible example：

```env
AI_PROVIDER=openai
AI_API_KEY=your_deepseek_key
AI_MODEL=deepseek-chat
AI_API_BASE=https://api.deepseek.com
```

Zotero settings：

- 在 `https://www.zotero.org/settings/keys` 创建或管理 Zotero API key。
- 个人文库使用 `ZOTERO_LIBRARY_TYPE=user`，群组文库使用 `group`。
- Windows 路径建议使用 `/`，例如：`ZOTERO_DATA_DIR=C:/Users/<user>/Zotero`。

---

## 启动 Zotero Chat

需要两个终端窗口。

### 窗口 1：启动 backend

Windows PowerShell：

```powershell
cd zotero-litwatch
uv run python main.py ui --port 8000
```

Linux/macOS：

```bash
cd zotero-litwatch
uv run python main.py ui --port 8000
```

### 窗口 2：启动 frontend

Windows PowerShell：

```powershell
cd zotero-litwatch\web-ui
npm.cmd run dev
```

Linux/macOS：

```bash
cd zotero-litwatch/web-ui
npm run dev
```

打开浏览器访问：

```text
http://localhost:3000
```

后端默认地址：

```text
http://localhost:8000
```

如果前端需要显式指定后端地址，Windows PowerShell 可使用：

```powershell
$env:NEXT_PUBLIC_API_URL="http://localhost:8000"
npm.cmd run dev
```

Linux/macOS 可使用：

```bash
export NEXT_PUBLIC_API_URL="http://localhost:8000"
npm run dev
```

---

## Zotero Chat CLI

在仓库根目录运行：

```powershell
uv run python main.py list
uv run python main.py scan "Collection Name"
uv run python main.py summarize "Collection Name" --limit 5
uv run python main.py research "Collection Name" -q "Question"
```

---

## 配置自己的 LitWatch 课题检索 YAML

LitWatch 不再默认携带某个具体课题的检索配置。公开版本只提供通用模板：

```text
configs/lit_watch_template.yaml
```

建议每个用户为自己的研究方向复制一份配置：

```powershell
Copy-Item configs/lit_watch_template.yaml configs/my_topic_lit_watch.yaml
notepad configs/my_topic_lit_watch.yaml
```

YAML 通常包含：

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

每条 query 建议覆盖一个明确方向，例如：

- core topic：课题核心问题；
- methods：主要方法；
- benchmarks：数据集、基准和评测；
- evaluation metrics：指标和验证方法；
- related work：相邻领域；
- limitations/open problems：局限、挑战和开放问题；
- recent work：近两三年的最新进展。

### 让 AI 帮你生成课题 YAML

可以把下面 prompt 发给 ChatGPT、Codex 或其他代码助手，让它基于模板生成你的课题配置：

```text
请根据我的研究课题，基于 configs/lit_watch_template.yaml 生成一个新的 LitWatch YAML 配置。

我的课题：
<在这里粘贴课题简介>

要求：
1. 保留 version/name/description/defaults/queries 结构。
2. 生成 8-12 条 query。
3. 覆盖 core topic、methods、benchmarks、evaluation metrics、related work、limitations/open problems、recent work。
4. 每条 query 必须包含 query/source/year_from/max_results/tags/target_subcollection/inclusion_reason。
5. 不要写 API key。
6. root_collection 使用简短、安全、无隐私的名字。
7. 输出为 configs/my_topic_lit_watch.yaml。
8. 不要直接运行检索；先让我人工检查 YAML。
```

人工检查 YAML 后，再运行 LitWatch 命令。

---

## LitWatch 工作流

### Step 1: Search public sources

根据配置检索公开文献元数据，并写出 raw candidates。请将 `configs/my_topic_lit_watch.yaml` 替换为你自己的课题配置。

```powershell
uv run python tools/lit_watch_search.py --config configs/my_topic_lit_watch.yaml --out artifacts/lit_watch/candidates_raw.jsonl
```

如只是快速试用模板，也可以使用：

```powershell
uv run python tools/lit_watch_search.py --config configs/lit_watch_template.yaml --out artifacts/lit_watch/candidates_raw.jsonl
```

### Step 2: Screen and deduplicate

规范化记录、去重、相关性打分，并生成筛选报告。

```powershell
uv run python tools/lit_watch_screen.py --input artifacts/lit_watch/candidates_raw.jsonl --out-dir artifacts/lit_watch
```

### Step 3: Dry-run Zotero import

预览将要导入 Zotero 的候选文献。任何 Zotero 写入前都应先执行 dry-run。

```powershell
uv run python tools/lit_watch_import_zotero.py --input artifacts/lit_watch/candidates_screened.jsonl --min-score 4 --dry-run
```

### Step 4: Commit import after human confirmation

只有在人工检查 dry-run 结果并明确确认后，才使用 `--commit` 写入 Zotero。

```powershell
uv run python tools/lit_watch_import_zotero.py --input artifacts/lit_watch/candidates_screened.jsonl --min-score 4 --commit
```

### Step 5: Generate deep research report

可以通过 Zotero Chat CLI 对导入后的 collection 生成调研报告：

```powershell
uv run python main.py list
uv run python main.py scan "Collection Name"
uv run python main.py summarize "Collection Name" --limit 30
uv run python main.py research "Collection Name" -q "Your research question"
```

### Step 6: Generate knowledge graph

```powershell
uv run python tools/lit_watch_kg.py --input artifacts/lit_watch/candidates_screened.jsonl --out-dir artifacts/lit_watch
```

打开图谱：

```powershell
start .\artifacts\lit_watch\literature_graph.html
```

### Step 7: Audit and related-work matrix

```powershell
uv run python tools/lit_watch_quality_audit.py --input-dir artifacts/lit_watch
```

---

## 输出文件

LitWatch 通常在 `artifacts/lit_watch/` 下生成：

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

## 知识图谱说明

LitWatch 生成的知识图谱主要用于探索文献主题关系、任务关系、方法关系和 evidence gate 关系。它不是严格的 citation graph。

默认图谱可能包含：

- paper 节点
- method 节点
- task 节点
- evidence_gate 节点
- benchmark 节点
- gap 节点

边类型可能包括：

- `uses`
- `addresses`
- `evaluates_on`
- `validates_with`
- `related_to`
- `leaves_open`
- `addresses_gap`

其中 paper-paper 边默认采用保守的 `related_to`，不应被解释为真实引用关系，除非上游元数据中明确包含 citation 信息并由脚本显式处理。

---

## 致谢与来源

本项目基于 Jianxinnn/Zotero-review-generation，也即原文档中的 Zotero Chat。原项目提供 Zotero collection 扫描、PDF 读取、AI 总结、Deep Research、Categorize、Chat、Semantic Search、Global Search、FastAPI 后端和 Next.js 前端。

当前扩展新增 LitWatch 脚本、通用课题配置模板、生成报告约定、导入安全工作流、知识图谱生成和发布/安全文档。

---

## 免责声明

本项目用于辅助研究者进行文献检索、筛选、入库和调研分析。自动检索和 AI 生成报告不能替代人工精读、引用核查和学术判断。

使用者应自行确认：

- 检索结果是否完整；
- Zotero 入库是否准确；
- AI 生成内容是否可靠；
- 文献引用是否真实、准确、可追溯；
- 是否遵守相关 API、出版商和数据库的使用条款。

---

## License
以 MIT License 文件为准。
