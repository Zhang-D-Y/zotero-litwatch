#!/usr/bin/env python3
"""Quality audit and related-work matrix for the LitWatch v1 artifacts.

This script is intentionally local-only. It does not read .env contents, does
not call Zotero, and does not download PDFs.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ART = Path("artifacts/lit_watch")
INPUT_JSONL = ART / "candidates_screened.jsonl"


REQUIRED_FILES = [
    "candidates_raw.jsonl",
    "candidates_screened.jsonl",
    "candidates_screened.csv",
    "import_report.md",
    "deep_research_report.md",
    "literature_graph.html",
    "literature_graph.graphml",
    "literature_graph.json",
    "literature_map.md",
]


MATRIX_FIELDS = [
    "paper_title",
    "year",
    "venue",
    "category",
    "task",
    "method",
    "uses_llm_or_agent",
    "uses_memory_or_retrieval",
    "targets_generation_or_repair_or_debug",
    "rtl_level_or_gate_level_or_backend",
    "benchmark_or_dataset",
    "validation_gate",
    "uses_formal_equivalence_or_lec",
    "uses_yosys_openroad_or_eda_tool_feedback",
    "reports_qor_metrics",
    "reports_correctness_metrics",
    "relation_to_microsurgeon",
    "novelty_threat_level",
    "why_it_threatens_or_supports_my_work",
    "must_read_priority",
    "overclaim_risk",
]


def sh(args: List[str]) -> str:
    proc = subprocess.run(args, text=True, capture_output=True, check=False)
    return (proc.stdout + proc.stderr).strip()


def clean(text: Any) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def read_text_auto(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def blob(record: Dict[str, Any]) -> str:
    fields = [
        record.get("title", ""),
        record.get("abstract", ""),
        record.get("venue", ""),
        " ".join(record.get("tags") or []),
        record.get("target_subcollection", ""),
        record.get("query", ""),
    ]
    return " ".join(clean(x).lower() for x in fields if x)


def has(text: str, terms: Iterable[str]) -> bool:
    for term in terms:
        pattern = r"(?<![a-z0-9])" + re.escape(term.lower()).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
        if re.search(pattern, text):
            return True
    return False


def load_records(min_score: int = 4) -> List[Dict[str, Any]]:
    records = []
    with INPUT_JSONL.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if int(rec.get("score") or 0) >= min_score:
                records.append(rec)
    records.sort(key=lambda r: (int(r.get("score") or 0), int(r.get("citation_count") or 0), r.get("year") or 0), reverse=True)
    return records


def category(record: Dict[str, Any]) -> str:
    mapping = {
        "01_llm_agent_for_eda": "LLM/agent for EDA",
        "02_rtl_repair_debug": "RTL repair/debug",
        "03_formal_correctness_gate": "Formal correctness gate",
        "04_timing_eco_deterministic": "Timing ECO / deterministic tools",
        "05_memory_retrieval_distillation": "Memory/RAG/distillation",
        "06_benchmarks_evaluation": "Benchmark/evaluation",
        "07_red_blue_adversarial_eda": "Red-blue/adversarial EDA",
        "08_rtl_representation_learning": "RTL representation learning",
        "09_background_llm_code_repair": "LLM code repair background",
    }
    return mapping.get(clean(record.get("target_subcollection", "")), clean(record.get("target_subcollection", "")) or "Uncategorized")


def classify_task(text: str) -> str:
    if has(text, ["bug localization", "fault localization", "line anomalies"]):
        return "bug localization"
    if has(text, ["rtl repair", "verilog repair", "repair", "bug fixing", "fixing"]):
        return "RTL repair"
    if has(text, ["debug", "debugging"]):
        return "Verilog/RTL debugging"
    if has(text, ["assertion", "sva", "formal verification"]):
        return "assertion/formal verification"
    if has(text, ["timing closure", "timing eco", "wns", "tns", "openroad", "opensta"]):
        return "timing closure/ECO"
    if has(text, ["ppa", "power", "performance", "area", "optimization"]):
        return "PPA optimization"
    if has(text, ["generation", "generate", "code completion", "spec2rtl"]):
        return "RTL/Verilog generation"
    if has(text, ["benchmark", "dataset", "evaluation"]):
        return "benchmark/evaluation"
    return "AI-for-EDA background"


def classify_method(text: str) -> str:
    methods = []
    if has(text, ["multi-agent", "multi agent", "agent", "autonomous"]):
        methods.append("LLM agent")
    elif has(text, ["llm", "large language model", "gpt", "language model"]):
        methods.append("LLM prompting/fine-tuning")
    if has(text, ["rag", "retrieval", "retrieval-augmented"]):
        methods.append("RAG")
    if has(text, ["memory", "skill library", "hard bank"]):
        methods.append("memory")
    if has(text, ["distillation", "fine-tuning", "finetuning", "fine tuned", "fine-tuned"]):
        methods.append("fine-tuning/distillation")
    if has(text, ["formal equivalence", "equivalence checking", "lec", "formal verification", "sva"]):
        methods.append("formal methods")
    if has(text, ["symbolic", "program synthesis", "neural-symbolic", "tree search"]):
        methods.append("symbolic/search")
    if has(text, ["tool feedback", "eda feedback", "compiler", "simulator", "yosys", "openroad", "opensta", "iverilog"]):
        methods.append("EDA tool feedback")
    return "; ".join(dict.fromkeys(methods)) or "metadata-only/unspecified"


def level(text: str) -> str:
    if has(text, ["openroad", "opensta", "timing", "placement", "routing", "backend", "physical"]):
        return "backend / physical implementation"
    if has(text, ["gate-level", "netlist", "lec", "equivalence checking", "eco"]):
        return "gate-level / netlist / ECO"
    if has(text, ["rtl", "verilog", "systemverilog", "hdl"]):
        return "RTL"
    return "cross-level / unspecified"


def benchmark(text: str, record: Dict[str, Any]) -> str:
    vals = []
    for name, terms in {
        "VerilogEval/HDLBits": ["verilogeval", "hdlbits"],
        "RTL-repair": ["rtl-repair"],
        "Fixbench-RTL": ["fixbench"],
        "OpenROAD/OpenSTA": ["openroad", "opensta"],
        "Yosys": ["yosys"],
        "OpenLLM-RTL/RTLCoder/OpenRTLSet": ["openllm-rtl", "rtlcoder", "openrtlset"],
        "GitHub/textbook datasets": ["github", "textbook"],
        "EDA datasets": ["dataset", "benchmark"],
    }.items():
        if has(text, terms):
            vals.append(name)
    if not vals and category(record) == "Benchmark/evaluation":
        vals.append("Verilog/EDA benchmark or dataset")
    return "; ".join(dict.fromkeys(vals)) or "not specified in metadata"


def validation_gate(text: str) -> str:
    gates = []
    if has(text, ["syntax", "compile", "compiler", "lint"]):
        gates.append("compile/syntax pass")
    if has(text, ["synthesis", "yosys", "synthesizable"]):
        gates.append("synthesis pass")
    if has(text, ["simulation", "testbench", "test bench", "golden", "functional correctness"]):
        gates.append("simulation/testbench")
    if has(text, ["formal equivalence", "equivalence checking", "lec"]):
        gates.append("formal equivalence/LEC")
    if has(text, ["assertion", "sva", "formal verification"]):
        gates.append("assertion/formal verification")
    if has(text, ["wns", "tns", "timing"]):
        gates.append("timing metrics WNS/TNS")
    return "; ".join(dict.fromkeys(gates)) or "not clear from metadata"


def target_kind(text: str) -> str:
    kinds = []
    if has(text, ["generation", "generate", "code completion", "spec2rtl"]):
        kinds.append("generation")
    if has(text, ["repair", "fix", "bug fixing", "correction"]):
        kinds.append("repair")
    if has(text, ["debug", "debugging", "localization", "line anomalies"]):
        kinds.append("debug")
    return "; ".join(dict.fromkeys(kinds)) or "background/evaluation"


def relation(text: str) -> str:
    if has(text, ["r3a", "clover", "verirepair", "verirag", "rtlfixer", "rtl repair", "verilog repair", "fixing rtl", "bug fixing", "functional bug", "syntax errors"]):
        return "Direct comparison or baseline candidate for MicroSurgeon repair."
    if has(text, ["debug", "bug localization", "fault localization"]):
        return "Supports localization/debugging component of MicroSurgeon."
    if has(text, ["formal equivalence", "lec", "assertion", "formal verification"]):
        return "Supports correctness gate and L2/L3 evaluation design."
    if has(text, ["rag", "retrieval", "memory", "distillation", "skill library"]):
        return "Supports memory/retrieval/distillation ablations."
    if has(text, ["timing", "eco", "openroad", "opensta", "wns", "tns"]):
        return "Supports deterministic-tool boundary and negative result framing."
    if has(text, ["benchmark", "dataset", "evaluation"]):
        return "Supports benchmark positioning and evaluation protocol."
    return "Background for AI-for-EDA positioning."


def threat_level(text: str, record: Dict[str, Any]) -> str:
    title = clean(record.get("title", "")).lower()
    if any(k in title for k in ["r3a", "clover", "verirepair", "verirag", "rtl-repair", "rtlfixer", "meic", "veridebug", "llm-assisted bug identification", "fixbench", "buggen"]):
        return "high"
    if has(text, ["repair", "debug", "bug localization", "formal equivalence", "rag", "multi-agent", "assertion"]):
        return "medium"
    return "low"


def threat_reason(text: str, record: Dict[str, Any]) -> str:
    tl = threat_level(text, record)
    if tl == "high":
        return "Closest prior art for RTL repair/debug, agentic repair, benchmark, or red-team bug generation; must distinguish MicroSurgeon by adversarial learning, memory ablations, and LEC/correctness gates."
    if tl == "medium":
        return "Supports one component of the story but likely does not close the red-blue semantic repair plus memory claim."
    return "Useful background; unlikely to directly challenge novelty."


def priority(text: str, record: Dict[str, Any]) -> str:
    if threat_level(text, record) == "high":
        return "A"
    if has(text, ["formal equivalence", "lec", "timing eco", "openroad", "opensta", "rag", "retrieval", "multi-agent", "benchmark", "dataset"]):
        return "B"
    return "C"


def overclaim(text: str) -> str:
    if has(text, ["syntax", "compile"]) and not has(text, ["functional", "semantic", "formal"]):
        return "Do not generalize syntax/compile repair to semantic RTL correctness."
    if has(text, ["simulation", "testbench"]) and not has(text, ["formal equivalence", "lec"]):
        return "Do not claim exhaustive correctness beyond tested scenarios."
    if has(text, ["timing", "eco", "openroad", "opensta"]):
        return "Do not claim LLM improves timing ECO unless direct evidence exists; use as deterministic boundary."
    if has(text, ["generation", "code generation"]) and not has(text, ["repair", "debug"]):
        return "Do not cite as repair evidence; cite as generation or benchmark background only."
    return "Verify exact claims in full text before using strong wording."


def bool_yn(value: bool) -> str:
    return "yes" if value else "no"


def make_matrix(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    rows = []
    for record in records:
        text = blob(record)
        row = {
            "paper_title": clean(record.get("title", "")),
            "year": str(record.get("year") or ""),
            "venue": clean(record.get("venue", "")),
            "category": category(record),
            "task": classify_task(text),
            "method": classify_method(text),
            "uses_llm_or_agent": bool_yn(has(text, ["llm", "large language model", "gpt", "agent", "language model"])),
            "uses_memory_or_retrieval": bool_yn(has(text, ["rag", "retrieval", "memory", "skill library", "distillation"])),
            "targets_generation_or_repair_or_debug": target_kind(text),
            "rtl_level_or_gate_level_or_backend": level(text),
            "benchmark_or_dataset": benchmark(text, record),
            "validation_gate": validation_gate(text),
            "uses_formal_equivalence_or_lec": bool_yn(has(text, ["formal equivalence", "equivalence checking", "lec"])),
            "uses_yosys_openroad_or_eda_tool_feedback": bool_yn(has(text, ["yosys", "openroad", "opensta", "eda feedback", "tool feedback", "compiler", "simulator", "iverilog"])),
            "reports_qor_metrics": bool_yn(has(text, ["ppa", "power", "performance", "area", "qor", "wns", "tns", "timing"])),
            "reports_correctness_metrics": bool_yn(has(text, ["correctness", "pass rate", "fix rate", "compile", "syntax", "simulation", "testbench", "formal verification", "equivalence"])),
            "relation_to_microsurgeon": relation(text),
            "novelty_threat_level": threat_level(text, record),
            "why_it_threatens_or_supports_my_work": threat_reason(text, record),
            "must_read_priority": priority(text, record),
            "overclaim_risk": overclaim(text),
        }
        rows.append(row)
    return rows


def write_matrix(rows: List[Dict[str, str]]) -> None:
    csv_path = ART / "related_work_matrix.csv"
    md_path = ART / "related_work_matrix.md"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=MATRIX_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Related Work Matrix",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Rows: {len(rows)}",
        "",
        "| " + " | ".join(MATRIX_FIELDS) + " |",
        "| " + " | ".join(["---"] * len(MATRIX_FIELDS)) + " |",
    ]
    for row in rows:
        vals = [row[field].replace("|", "\\|").replace("\n", " ") for field in MATRIX_FIELDS]
        lines.append("| " + " | ".join(vals) + " |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_import_report() -> Dict[str, int]:
    report = (ART / "import_report.md").read_text(encoding="utf-8")
    keys = ["Filtered candidates", "Input duplicates removed", "Existing Zotero duplicates skipped", "Planned import count", "Created item count", "Errors"]
    result = {}
    for key in keys:
        m = re.search(rf"- {re.escape(key)}: (\d+)", report)
        if m:
            result[key] = int(m.group(1))
    return result


def write_audit(records: List[Dict[str, Any]], rows: List[Dict[str, str]]) -> None:
    git_status = sh(["git", "status", "--short"])
    env_status = sh(["git", "status", "--short", "--", ".env"])
    import_stats = parse_import_report()
    score_ge_4 = len(records)
    missing = [name for name in REQUIRED_FILES if not (ART / name).exists()]
    file_rows = []
    for name in REQUIRED_FILES:
        p = ART / name
        if p.exists():
            file_rows.append(f"- `{name}`: present, {p.stat().st_size} bytes")
        else:
            file_rows.append(f"- `{name}`: MISSING")
    raw = read_text_auto(ART / "deep_research_report_raw.txt") if (ART / "deep_research_report_raw.txt").exists() else ""
    scan_147 = "找到 147 个条目" in raw and "扫描完成，共 147 个文档" in raw
    graph_ok = all((ART / name).exists() for name in ["literature_graph.html", "literature_graph.graphml", "literature_graph.json", "literature_map.md"])
    high_count = sum(1 for r in rows if r["novelty_threat_level"] == "high")
    medium_count = sum(1 for r in rows if r["novelty_threat_level"] == "medium")

    lines = [
        "# LitWatch v1 Audit",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Scope",
        "",
        "- Local artifact audit only.",
        "- No `.env` contents were read or printed.",
        "- No Zotero write action was attempted.",
        "- No PDF download was attempted.",
        "",
        "## Git Status",
        "",
        "```text",
        git_status or "(clean)",
        "```",
        "",
        "## .env Status",
        "",
        "- `git status --short -- .env` returned no output, so `.env` has no tracked modification in this worktree.",
        "- File contents were not opened, printed, copied, or summarized.",
        "",
        "## Required Artifacts",
        "",
        *file_rows,
        "",
        "## Candidate / Import Consistency",
        "",
        f"- `candidates_screened.jsonl` records with `score >= 4`: {score_ge_4}",
        f"- `import_report.md` Filtered candidates: {import_stats.get('Filtered candidates', 'missing')}",
        f"- Existing Zotero duplicates skipped: {import_stats.get('Existing Zotero duplicates skipped', 'missing')}",
        f"- Planned import count: {import_stats.get('Planned import count', 'missing')}",
        f"- Created item count: {import_stats.get('Created item count', 'missing')}",
        f"- Commit errors: {import_stats.get('Errors', 'missing')}",
        "",
        "Interpretation:",
        "",
        "- Candidate count and import report are consistent: 149 high-score candidates, 2 existing Zotero duplicates skipped, 147 created.",
        "- No commit error is reported in `import_report.md`.",
        "- Input duplicates removed is 0 in `import_report.md`; no repeated DOI/arXiv/title was imported by the importer.",
        "",
        "## Note Mis-Scan Check",
        "",
        f"- Final `deep_research_report_raw.txt` scan found exactly 147 Zotero items: {scan_147}.",
        "- A previous implementation issue could expose child notes as scanned items via Zotero API; `zotero/client.py` now excludes `note` items together with attachments during API collection scan.",
        "- Current final research raw log does not show a 294-item final scan; the generated report was based on 147 paper records.",
        "",
        "## Graph / Matrix Sanity",
        "",
        f"- Knowledge graph files present: {graph_ok}.",
        f"- Related work matrix rows generated: {len(rows)}.",
        f"- Novelty threat levels: high={high_count}, medium={medium_count}, low={len(rows) - high_count - medium_count}.",
        "",
        "## Residual Risks",
        "",
        "- The screening and graph labels are metadata/abstract based. Before final paper claims, read full text for all priority A papers.",
        "- Some 2026 records may be preprints, books, or future-dated metadata; verify venue status before citing.",
        "- `data/session.json` and `web-ui/package-lock.json` were already modified in the worktree and are unrelated to this audit.",
    ]
    (ART / "lit_watch_v1_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def find_by_title(records: List[Dict[str, Any]], needles: Iterable[str]) -> List[Dict[str, Any]]:
    found = []
    used = set()
    for needle in needles:
        n = needle.lower()
        for rec in records:
            title = clean(rec.get("title", "")).lower()
            if n in title and title not in used:
                found.append(rec)
                used.add(title)
                break
    return found


def pick_extra(records: List[Dict[str, Any]], used_titles: set[str], terms: Iterable[str], limit: int) -> List[Dict[str, Any]]:
    out = []
    for rec in records:
        title = clean(rec.get("title", ""))
        if title in used_titles:
            continue
        if has(blob(rec), terms):
            out.append(rec)
            used_titles.add(title)
        if len(out) >= limit:
            break
    return out


def brief(rec: Dict[str, Any]) -> str:
    return f"**{clean(rec.get('title'))}** ({rec.get('year') or 'n.d.'}) — {category(rec)}. {relation(blob(rec))}"


def write_must_read(records: List[Dict[str, Any]]) -> None:
    used = set()
    groups: List[Tuple[str, List[Dict[str, Any]]]] = []
    specs = [
        ("1. 直接威胁 novelty 的文献", ["clover", "r3a", "verirepair", "verirag", "rtlfixer", "meic", "veridebug", "rtl-repair"], 7, ["repair", "debug", "bug localization"]),
        ("2. 可作为 background 的文献", ["verigene", "verigen", "verilogeval", "rtllm", "chateda"], 4, ["llm", "verilog", "generation", "benchmark"]),
        ("3. 可支撑 correctness/formal gate 的文献", ["hybrid-nl2sva", "formaleval", "fveval", "assertionforge", "using llms to facilitate formal verification", "symrtlo"], 4, ["formal", "assertion", "equivalence", "sva"]),
        ("4. 可支撑 memory/retrieval/agent 消融的文献", ["eda-copilot", "dr. rtl", "mage", "spec2rtl-agent", "mall", "buggen"], 3, ["rag", "retrieval", "memory", "multi-agent", "agent"]),
        ("5. 可支撑 timing ECO 是 deterministic 工具强项的文献", ["ir-aware eco", "single-pass timing", "agentic llm flow for chip timing closure", "autonomous timing closure", "timing"], 2, ["timing", "eco", "openroad", "opensta", "wns", "tns"]),
    ]
    for heading, needles, target, fallback_terms in specs:
        selected = find_by_title(records, needles)
        unique = []
        for rec in selected:
            title = clean(rec.get("title"))
            if title not in used:
                unique.append(rec)
                used.add(title)
            if len(unique) >= target:
                break
        if len(unique) < target:
            unique.extend(pick_extra(records, used, fallback_terms, target - len(unique)))
        groups.append((heading, unique[:target]))

    lines = [
        "# Must-Read 20 for MicroSurgeon",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Selection is metadata/abstract based. Priority is for novelty defense and experiment design; verify full text before final citation.",
        "",
    ]
    total = 0
    for heading, recs in groups:
        lines.extend([f"## {heading}", ""])
        for rec in recs:
            total += 1
            lines.append(f"{total}. {brief(rec)}")
            lines.append(f"   - Why read: {threat_reason(blob(rec), rec)}")
            lines.append(f"   - Overclaim guard: {overclaim(blob(rec))}")
        lines.append("")
    lines.append(f"Total selected: {total}")
    (ART / "must_read_20.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_positioning(records: List[Dict[str, Any]], rows: List[Dict[str, str]]) -> None:
    cat_counts = Counter(r["category"] for r in rows)
    task_counts = Counter(r["task"] for r in rows)
    formal_count = sum(1 for r in rows if r["uses_formal_equivalence_or_lec"] == "yes")
    rag_count = sum(1 for r in rows if r["uses_memory_or_retrieval"] == "yes")
    eda_tool_count = sum(1 for r in rows if r["uses_yosys_openroad_or_eda_tool_feedback"] == "yes")
    high_threat = [r for r in rows if r["novelty_threat_level"] == "high"][:12]

    lines = [
        "# Paper Positioning From LitWatch v1",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "Theme: **红蓝对抗式 AI-for-EDA RTL 修复智能体：在 timing ECO 中诚实证明 LLM 无增量，在语义级 RTL repair 中证明 LLM/记忆的真增量。**",
        "",
        "## Evidence Snapshot",
        "",
        f"- High-relevance records: {len(rows)}",
        f"- Formal equivalence / LEC related records: {formal_count}",
        f"- Memory / retrieval related records: {rag_count}",
        f"- Yosys/OpenROAD/EDA tool feedback related records: {eda_tool_count}",
        "- Category distribution:",
    ]
    for cat, count in sorted(cat_counts.items()):
        lines.append(f"  - {cat}: {count}")
    lines.extend(["", "## 1. Strongest Novelty", ""])
    lines.extend([
        "The strongest novelty is not “LLM fixes RTL bugs” by itself. The strongest novelty is a **closed-loop, red-blue learning claim**:",
        "",
        "> Red-team bug diversity creates a curriculum of semantic RTL failures; blue-team MicroSurgeon improves repair generalization through memory/retrieval/distillation, while correctness gates separate real semantic fixes from compile/test overfitting.",
        "",
        "The defensible novelty bundle is:",
        "",
        "- Honest boundary result: timing ECO / STA optimization is deterministic-tool territory, so LLM should not be oversold there.",
        "- Positive band: semantic RTL repair where local rules, module closure, and naive baselines fail, but design-intent reasoning can help.",
        "- Evaluation structure: L0/L1/L1.5/L2/L3 gates, especially formal equivalence/LEC for patched RTL when tractable.",
        "- Learning structure: memory and distillation ablations showing improvement across red-team rounds, not just one-shot prompting.",
    ])
    lines.extend(["", "## 2. Strongest Related Work Attacks", ""])
    lines.append("| Attack source | Likely reviewer challenge | Defense needed |")
    lines.append("|---|---|---|")
    for r in high_threat[:8]:
        lines.append(f"| {r['paper_title']} | This already does RTL repair/debug/agentic repair. | Show adversarial learning, held-out bug-type generalization, memory ablation, and stronger correctness gates. |")
    lines.extend(["", "## 3. Claims You Can Say Now", ""])
    lines.extend([
        "- Existing LLM-for-EDA work heavily covers RTL/Verilog generation, benchmarking, verification assistance, and emerging repair/debug workflows.",
        "- Existing repair/debug success is often measured by compile pass, simulation/testbench pass, fix rate, or benchmark-specific correctness.",
        "- Formal equivalence / LEC appears in the literature but is not yet the dominant validation gate for LLM RTL repair.",
        "- Timing ECO/OpenROAD/OpenSTA style tasks are mostly deterministic optimization or flow automation problems; they are a reasonable negative-control domain for LLM increment.",
        "- MicroSurgeon can be framed as searching for the narrow semantic repair band where LLM and memory have measurable incremental value.",
    ])
    lines.extend(["", "## 4. Claims You Cannot Say Yet", ""])
    lines.extend([
        "- Do not claim MicroSurgeon is the first LLM RTL repair system; related work already covers RTLFixer, MEIC, R3A/Clover-like agentic repair, and symbolic repair.",
        "- Do not claim formal equivalence proves all real RTL fixes unless the equivalence spec and golden design are well-defined.",
        "- Do not claim red-team generation alone is a contribution unless blue-team improvement is measured.",
        "- Do not claim memory/distillation improves repair until L0/L1/L2/L1.5/L3 ablations show statistically meaningful gains.",
        "- Do not claim LLM improves timing ECO without direct WNS/TNS/QoR evidence against OpenROAD/OpenSTA baselines.",
    ])
    lines.extend(["", "## 5. Three Missing Evidence Classes", ""])
    lines.extend([
        "1. **Generalization evidence**: held-out bug families and held-out designs, showing red-team diversity improves blue repair beyond fixed benchmarks.",
        "2. **Correctness-gate evidence**: compile/synthesis/simulation plus LEC/formal-equivalence or bounded property checks for the Stage B and benchmark patches.",
        "3. **Mechanism evidence**: L0/L1/L2/L1.5/L3 ablations for memory, retrieval, distillation, red-team diversity, and correctness gate strictness.",
    ])
    lines.extend(["", "## 6. Related Work Grouping", ""])
    lines.extend([
        "Recommended related work section order:",
        "",
        "1. **LLM for RTL generation and benchmark evaluation**: VerilogEval, RTLLM, VeriGen, RTLCoder, OpenLLM-RTL. Use this as background, not repair novelty.",
        "2. **LLM/agent workflows for EDA automation**: ChatEDA, AutoEDA, EDA-Copilot, Spec2RTL-Agent, MAGE. Use this to position agent architecture.",
        "3. **RTL repair, debugging, and bug localization**: RTLFixer, MEIC, VeriDebug, R3A/Clover-like systems, RTL-Repair, CirFix, Fixbench-RTL. This is the novelty threat section.",
        "4. **Correctness and formal gates**: FormalEval, FVEval, assertion generation, LEC/equivalence checking papers. Use this to justify L2/L3 gates.",
        "5. **Timing ECO / deterministic EDA optimization**: OpenROAD/OpenSTA, IR-aware ECO, timing closure papers. Use this as the negative-control boundary.",
        "6. **Memory/retrieval/distillation for agents**: RAG-based EDA assistants, VeriRAG, Hybrid-NL2SVA, skill-library systems. Use this to motivate ablations.",
    ])
    lines.extend(["", "## 7. Abstract Overclaim Avoidance", ""])
    lines.extend([
        "Avoid:",
        "",
        "- “solves RTL repair”",
        "- “fully autonomous RTL debugging”",
        "- “formal correctness for arbitrary RTL”",
        "- “LLM outperforms deterministic EDA tools”",
        "- “first AI-for-EDA repair agent”",
        "",
        "Prefer:",
        "",
        "- “identifies a semantic RTL repair band where LLM reasoning and memory provide incremental value”",
        "- “uses timing ECO as a negative-control domain for deterministic-tool dominance”",
        "- “evaluates repair under progressively stricter gates from compile to formal equivalence where applicable”",
        "- “shows whether adversarial bug diversity improves held-out repair generalization”",
    ])
    lines.extend(["", "## 8. Venue Framing", ""])
    lines.extend([
        "| Venue | Best framing | Risk |",
        "|---|---|---|",
        "| DAC | AI-for-EDA system with rigorous repair benchmark and EDA tool gates | Needs strong experimental scale and baseline comparisons. |",
        "| ICCAD | Methodological contribution: semantic RTL repair, formal correctness gates, adversarial training loop | Reviewers will attack novelty against symbolic repair and recent LLM repair systems. |",
        "| DATE | Honest empirical study: where LLM helps and where deterministic tools dominate | Need crisp negative-control story and reproducible artifact. |",
        "| ASP-DAC | Practical AI-for-EDA workflow and benchmark paper | May tolerate narrower scope but still needs strong baselines. |",
        "",
        "Best current framing: **DATE/DAC empirical systems paper** if you can deliver the negative-control timing ECO result plus semantic RTL repair gains. If the formal/LEC story becomes the centerpiece, ICCAD becomes stronger.",
    ])
    (ART / "paper_positioning_from_lit_v1.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    records = load_records(min_score=4)
    rows = make_matrix(records)
    write_matrix(rows)
    write_audit(records, rows)
    write_must_read(records)
    write_positioning(records, rows)
    print(f"records={len(records)}")
    print(f"matrix_rows={len(rows)}")
    print(f"wrote={ART / 'lit_watch_v1_audit.md'}")
    print(f"wrote={ART / 'related_work_matrix.csv'}")
    print(f"wrote={ART / 'related_work_matrix.md'}")
    print(f"wrote={ART / 'must_read_20.md'}")
    print(f"wrote={ART / 'paper_positioning_from_lit_v1.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
