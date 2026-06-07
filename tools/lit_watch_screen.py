#!/usr/bin/env python3
"""Screen and deduplicate dry-run literature candidates.

This script is local-only and never writes to Zotero.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


DIRECT_REPAIR = [
    "rtl repair",
    "verilog repair",
    "bug repair",
    "bug fixing",
    "debugging",
    "repair",
    "patch",
    "correctness",
    "formal equivalence",
    "logic equivalence",
    "lec",
    "equivalence checking",
]
RTL_EDA = [
    "eda",
    "electronic design automation",
    "rtl",
    "verilog",
    "systemverilog",
    "hardware design",
    "digital design",
    "openroad",
    "opensta",
    "timing eco",
    "engineering change order",
    "functional eco",
    "timing closure",
    "timing optimization",
    "gate sizing",
    "buffer insertion",
    "physical design",
    "sta",
]
LLM_AGENT = [
    "large language model",
    "llm",
    "gpt",
    "language model",
    "agent",
    "autonomous agent",
    "rag",
    "retrieval augmented",
]
MEMORY = ["memory", "retrieval", "distillation", "self-reflection", "self improvement", "lifelong"]
BENCH = ["benchmark", "dataset", "evaluation", "test suite"]
ADVERSARIAL = ["red team", "blue team", "adversarial", "bug injection", "mutation testing", "poison"]
GENERATION = [
    "generation",
    "code generation",
    "generate",
    "generating",
    "generated",
    "hdl generation",
    "rtl generation",
    "verilog generation",
]
TOOL_FEEDBACK = [
    "tool feedback",
    "compiler feedback",
    "simulation feedback",
    "verifier feedback",
    "feedback",
    "test feedback",
    "counterexample",
    "cex",
]


def norm_title(title: str) -> str:
    title = (title or "").lower()
    title = re.sub(r"[^a-z0-9]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def compact_doi(doi: str) -> str:
    doi = (doi or "").strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    return doi


def compact_arxiv(arxiv_id: str) -> str:
    value = (arxiv_id or "").strip().lower()
    value = re.sub(r"v\d+$", "", value)
    return value


def has_any(text: str, terms: List[str]) -> bool:
    for term in terms:
        pattern = r"(?<![a-z0-9])" + re.escape(term).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
        if re.search(pattern, text):
            return True
    return False


def score_candidate(record: Dict[str, Any]) -> Tuple[int, str]:
    fields = [
        record.get("title", ""),
        record.get("abstract", ""),
        record.get("venue", ""),
        " ".join(record.get("authors", []) or []),
        record.get("url", ""),
        record.get("open_access_url", ""),
    ]
    text = " ".join(str(x).lower() for x in fields if x)

    has_llm = has_any(text, LLM_AGENT)
    has_rtl = has_any(text, RTL_EDA)
    has_repair = has_any(text, DIRECT_REPAIR)
    has_memory = has_any(text, MEMORY)
    has_bench = has_any(text, BENCH)
    has_adv = has_any(text, ADVERSARIAL)
    has_generation = has_any(text, GENERATION)
    has_feedback = has_any(text, TOOL_FEEDBACK)
    has_generation_exception = has_repair or has_feedback

    if has_generation and has_llm and has_rtl and not has_generation_exception:
        return 3, "Background only: HDL/RTL generation without debug, repair, correctness, or tool-feedback evidence."
    if has_llm and has_rtl and (has_repair or has_feedback):
        return 5, "Direct match: LLM/agent plus RTL/EDA repair, debugging, or correctness evidence."
    if has_rtl and has_repair:
        return 4, "Relevant: RTL/EDA repair, debugging, ECO, or formal equivalence/correctness gate."
    if has_llm and has_rtl:
        return 4, "Relevant: LLM/agent applied to EDA, RTL, Verilog, or hardware design."
    if has_llm and (has_memory or has_bench):
        return 3, "Background: LLM agent memory/retrieval/distillation or benchmark/evaluation."
    if has_llm and ("code repair" in text or "program repair" in text):
        return 3, "Background: LLM code/program repair with possible transfer to RTL repair."
    if has_rtl and (has_bench or has_adv):
        return 3, "Background: RTL benchmark, evaluation, adversarial, or bug-injection context."
    if has_llm or has_rtl or has_repair or has_memory:
        return 2, "Weakly related: shares one major keyword family but lacks the full MicroSurgeon intersection."
    return 1, "Excluded: insufficient connection to LLM agents, EDA/RTL, repair, correctness, or memory."


def duplicate_identity(record: Dict[str, Any]) -> Tuple[str, str]:
    doi = compact_doi(record.get("doi", ""))
    if doi:
        return "doi", doi
    arxiv = compact_arxiv(record.get("arxiv_id", ""))
    if arxiv:
        return "arxiv", arxiv
    title = norm_title(record.get("title", ""))
    if title:
        return "title", title
    return "", ""


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                records.append(
                    {
                        "title": "",
                        "source": "parse_error",
                        "screen_warning": f"line {line_no}: {exc}",
                    }
                )
    return records


def load_exclusion_records(paths: List[Path]) -> Tuple[Dict[Tuple[str, str], str], List[str]]:
    exact: Dict[Tuple[str, str], str] = {}
    titles: List[str] = []
    for path in paths:
        if not path.exists():
            continue
        for record in load_jsonl(path):
            title = record.get("title", "")
            key = duplicate_identity(record)
            if key[0] and key[1]:
                exact[key] = title
            title_norm = norm_title(title)
            if title_norm:
                titles.append(title_norm)
    return exact, titles


def is_excluded(record: Dict[str, Any], exact: Dict[Tuple[str, str], str], titles: List[str]) -> Tuple[bool, str]:
    key = duplicate_identity(record)
    if key[0] and key[1] and key in exact:
        return True, f"already covered in exclude set by {key[0]}={key[1]}"
    title_norm = norm_title(record.get("title", ""))
    if not title_norm:
        return False, ""
    if ("title", title_norm) in exact:
        return True, "already covered in exclude set by normalized title"
    for existing in titles:
        if abs(len(title_norm) - len(existing)) > 15:
            continue
        ratio = difflib.SequenceMatcher(None, title_norm, existing).ratio()
        if ratio >= 0.94:
            return True, f"already covered in exclude set by title similarity {ratio:.2f}"
    return False, ""


def choose_better(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    existing_score = existing.get("score", 0)
    incoming_score = incoming.get("score", 0)
    if incoming_score != existing_score:
        return incoming if incoming_score > existing_score else existing
    existing_cites = existing.get("citation_count") or 0
    incoming_cites = incoming.get("citation_count") or 0
    if incoming_cites != existing_cites:
        return incoming if incoming_cites > existing_cites else existing
    existing_abstract = len(existing.get("abstract") or "")
    incoming_abstract = len(incoming.get("abstract") or "")
    return incoming if incoming_abstract > existing_abstract else existing


def deduplicate(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    kept: List[Dict[str, Any]] = []
    duplicates: List[Dict[str, Any]] = []
    doi_index: Dict[str, int] = {}
    arxiv_index: Dict[str, int] = {}

    for record in records:
        doi = compact_doi(record.get("doi", ""))
        arxiv = compact_arxiv(record.get("arxiv_id", ""))
        title_norm = norm_title(record.get("title", ""))
        dup_idx = None
        dup_reason = ""

        if doi and doi in doi_index:
            dup_idx = doi_index[doi]
            dup_reason = f"same DOI {doi}"
        elif arxiv and arxiv in arxiv_index:
            dup_idx = arxiv_index[arxiv]
            dup_reason = f"same arXiv {arxiv}"
        elif title_norm:
            for idx, existing in enumerate(kept):
                other = existing.get("_title_norm", "")
                if not other:
                    continue
                if title_norm == other:
                    dup_idx = idx
                    dup_reason = "same normalized title"
                    break
                if abs(len(title_norm) - len(other)) <= 15:
                    ratio = difflib.SequenceMatcher(None, title_norm, other).ratio()
                    if ratio >= 0.94:
                        dup_idx = idx
                        dup_reason = f"title similarity {ratio:.2f}"
                        break

        record["_title_norm"] = title_norm
        if dup_idx is None:
            kept.append(record)
            if doi:
                doi_index[doi] = len(kept) - 1
            if arxiv:
                arxiv_index[arxiv] = len(kept) - 1
            continue

        existing = kept[dup_idx]
        winner = choose_better(existing, record)
        loser = existing if winner is record else record
        duplicates.append(
            {
                "duplicate_title": loser.get("title", ""),
                "kept_title": winner.get("title", ""),
                "reason": dup_reason,
                "duplicate_source": loser.get("source", ""),
                "kept_source": winner.get("source", ""),
            }
        )
        if winner is record:
            kept[dup_idx] = record
            if doi:
                doi_index[doi] = dup_idx
            if arxiv:
                arxiv_index[arxiv] = dup_idx

    for record in kept:
        record.pop("_title_norm", None)
    return kept, duplicates


def write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_csv(path: Path, records: List[Dict[str, Any]]) -> None:
    fields = [
        "title",
        "authors",
        "year",
        "venue",
        "doi",
        "arxiv_id",
        "url",
        "source",
        "citation_count",
        "open_access_url",
        "query",
        "tags",
        "target_subcollection",
        "score",
        "reason",
        "inclusion_reason",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = {field: record.get(field, "") for field in fields}
            row["authors"] = "; ".join(record.get("authors", []) or [])
            row["tags"] = "; ".join(record.get("tags", []) or [])
            writer.writerow(row)


def recommendation_for(record: Dict[str, Any]) -> str:
    target = record.get("target_subcollection", "")
    score = int(record.get("score") or 0)
    title = str(record.get("title", "")).lower()
    text = " ".join(
        str(record.get(field, "")).lower()
        for field in ("title", "abstract", "inclusion_reason", "reason")
    )
    background_markers = [
        "sva generation",
        "assertion generation",
        "verification gap",
        "path exploration",
        "trojan detection",
        "data contamination",
        "ip protection",
        "qor optimization",
        "code optimization",
        "timing eco",
        "functional eco",
        "openroad agent",
        "mapping study",
        "benchmark",
        "survey",
        "review",
        "case study",
        "code generation",
        "verilog generation",
        "rtl generation",
        "llm-generated",
        "enhanced rtl synthesis",
        "fine-tuning",
        "soft prompts",
        "prompting",
        "evaluation metric",
        "hallucination",
        "co-design",
        "dataset",
        "corpus",
        "backend aware synthesis",
        "simulation semantics",
        "equivalence checking between",
        "correctness proofs",
        "high-level synthesis",
    ]
    import_markers = [
        "from bugs to fixes",
        "self-verification and self-correction",
        "veri-sure",
        "specloop",
        "phoenix-bench",
        "ft-pilot",
        "vulnerability-guided",
        "auto verific",
        "autoverifix",
        "vericoder",
        "vitad",
        "arsp",
        "automated repair",
        "debug like a human",
        "fault localization",
        "cktformalizer",
        "the art of rtl debugging",
    ]
    if any(marker in title for marker in import_markers):
        return "should_import"
    if any(marker in text for marker in background_markers):
        return "background"
    if score >= 5 and target in {
        "02_rtl_repair_debug",
        "03_formal_correctness_gate",
        "05_memory_retrieval_distillation",
        "07_red_blue_adversarial_eda",
    }:
        return "should_import"
    if score >= 4 and target == "04_timing_eco_deterministic":
        return "background"
    if score >= 4 and ("survey" in text or "review" in text):
        return "background"
    return "background"


def print_top(records: List[Dict[str, Any]], limit: int = 30, min_score: int = 1) -> None:
    records = [record for record in records if int(record.get("score") or 0) >= min_score]
    print("")
    print(f"Top {min(limit, len(records))} candidates with score >= {min_score}")
    print("-" * 120)
    for idx, record in enumerate(records[:limit], start=1):
        print(f"{idx:02d}. {record.get('title','')}")
        print(
            f"    year={record.get('year') or ''} | venue={record.get('venue') or ''} | "
            f"doi={record.get('doi') or ''} | source={record.get('source') or ''} | "
            f"score={record.get('score')}"
        )
        print(f"    reason={record.get('reason','')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Screen and deduplicate lit-watch candidates.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--exclude", action="append", default=[], type=Path, help="Existing JSONL candidate file to exclude by DOI, arXiv, or title.")
    parser.add_argument("--print-min-score", default=1, type=int, help="Only print candidates at or above this score.")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    records = load_jsonl(args.input)

    for record in records:
        score, reason = score_candidate(record)
        record["score"] = score
        record["reason"] = reason

    deduped, duplicates = deduplicate(records)
    excluded_existing: List[Dict[str, Any]] = []
    if args.exclude:
        exact, titles = load_exclusion_records(args.exclude)
        new_deduped: List[Dict[str, Any]] = []
        for record in deduped:
            excluded, reason = is_excluded(record, exact, titles)
            if excluded:
                copy = dict(record)
                copy["exclude_reason"] = reason
                excluded_existing.append(copy)
            else:
                new_deduped.append(record)
        deduped = new_deduped

    for record in deduped:
        record["recommendation"] = recommendation_for(record)
    deduped.sort(
        key=lambda r: (
            r.get("score") or 0,
            r.get("citation_count") or 0,
            r.get("year") or 0,
            r.get("title") or "",
        ),
        reverse=True,
    )

    jsonl_path = args.out_dir / "candidates_screened.jsonl"
    csv_path = args.out_dir / "candidates_screened.csv"
    report_path = args.out_dir / "dedupe_report.md"
    summary_path = args.out_dir / "screen_report.md"

    write_jsonl(jsonl_path, deduped)
    write_csv(csv_path, deduped)

    score_counts = Counter(record.get("score") for record in deduped)
    source_counts = Counter(record.get("source") for record in deduped)
    high_count = sum(1 for record in deduped if (record.get("score") or 0) >= 4)
    import_count = sum(1 for record in deduped if record.get("recommendation") == "should_import")
    background_count = sum(1 for record in deduped if record.get("recommendation") == "background")

    report_lines = [
        "# Dedupe Report",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Input: `{args.input}`",
        f"- Raw candidates: {len(records)}",
        f"- Deduped candidates: {len(deduped)}",
        f"- Duplicates removed: {len(duplicates)}",
        f"- Excluded by prior rounds: {len(excluded_existing)}",
        "",
        "## Duplicate Examples",
        "",
    ]
    for duplicate in duplicates[:100]:
        report_lines.append(
            f"- {duplicate['reason']}: kept `{duplicate['kept_title']}`; "
            f"removed `{duplicate['duplicate_title']}`"
        )
    if not duplicates:
        report_lines.append("- None")
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    summary_lines = [
        "# Screening Report",
        "",
        f"- Raw candidates: {len(records)}",
        f"- Deduped candidates: {len(deduped)}",
        f"- Excluded by prior rounds: {len(excluded_existing)}",
        f"- Score >= 4 candidates: {high_count}",
        f"- Recommended should_import: {import_count}",
        f"- Recommended background: {background_count}",
        "",
        "## Score Counts",
        "",
    ]
    for score in sorted(score_counts, reverse=True):
        summary_lines.append(f"- {score}: {score_counts[score]}")
    summary_lines.extend(["", "## Source Counts", ""])
    for source, count in sorted(source_counts.items()):
        summary_lines.append(f"- {source}: {count}")
    high_records = [record for record in deduped if int(record.get("score") or 0) >= 4]
    summary_lines.extend(["", "## Score >= 4 New Candidates", ""])
    if high_records:
        for record in high_records:
            summary_lines.append(
                f"- [{record.get('recommendation')}] score={record.get('score')} "
                f"{record.get('year') or ''} `{record.get('title', '')}`"
            )
            summary_lines.append(
                f"  DOI/arXiv: {record.get('doi') or record.get('arxiv_id') or 'n/a'}; "
                f"target: {record.get('target_subcollection', '')}; reason: {record.get('reason', '')}"
            )
    else:
        summary_lines.append("- None")
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(f"Raw candidates: {len(records)}")
    print(f"Deduped candidates: {len(deduped)}")
    print(f"Excluded by prior rounds: {len(excluded_existing)}")
    print(f"Score >= 4 candidates: {high_count}")
    print(f"Wrote: {jsonl_path}")
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {report_path}")
    print(f"Wrote: {summary_path}")
    print_top(deduped, 30, args.print_min_score)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
