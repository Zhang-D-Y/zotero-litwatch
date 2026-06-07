#!/usr/bin/env python3
"""Dry-run/commit screened literature candidates into Zotero.

Default behavior is dry-run. This script never downloads PDFs or creates
attachments. It reads Zotero configuration through the existing project
settings, but never prints secrets.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pyzotero import zotero

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import get_settings


ROOT_COLLECTION = "AI4EDA-MicroSurgeon-LitWatch"
REPORT_PATH = Path("artifacts/lit_watch/import_report.md")
COLLECTION_OVERRIDE: Optional[str] = None


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    value = str(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def norm_title(title: str) -> str:
    title = clean_text(title).lower()
    title = re.sub(r"[^a-z0-9]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def norm_doi(doi: str) -> str:
    doi = clean_text(doi).lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    return doi


def norm_arxiv(arxiv_id: str) -> str:
    value = clean_text(arxiv_id).lower()
    value = re.sub(r"^arxiv:", "", value)
    value = re.sub(r"v\d+$", "", value)
    return value


def arxiv_from_record(record: Dict[str, Any]) -> str:
    value = norm_arxiv(record.get("arxiv_id", ""))
    if value:
        return value
    for field in ("url", "open_access_url", "doi"):
        text = clean_text(record.get(field, ""))
        match = re.search(r"arxiv\.org/(?:abs|pdf)/([^/?#]+)", text, flags=re.I)
        if match:
            return norm_arxiv(match.group(1).replace(".pdf", ""))
        doi_match = re.search(r"10\.48550/arxiv\.([^/?#\s]+)", text, flags=re.I)
        if doi_match:
            return norm_arxiv(doi_match.group(1))
    return ""


def load_candidates(path: Path, min_score: int, recommendation: Optional[str] = None) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if int(record.get("score") or 0) >= min_score:
                if recommendation and clean_text(record.get("recommendation", "")) != recommendation:
                    continue
                records.append(record)
    return records


def duplicate_key(record: Dict[str, Any]) -> Tuple[str, str]:
    doi = norm_doi(record.get("doi", ""))
    if doi:
        return "doi", doi
    arxiv_id = arxiv_from_record(record)
    if arxiv_id:
        return "arxiv", arxiv_id
    return "title", norm_title(record.get("title", ""))


def dedupe_input(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    seen: Dict[Tuple[str, str], Dict[str, Any]] = {}
    duplicates: List[Dict[str, Any]] = []
    for record in records:
        key = duplicate_key(record)
        if not key[1]:
            key = ("title", f"missing-title-{len(seen)}")
        existing = seen.get(key)
        if existing is None:
            seen[key] = record
            continue
        winner = choose_better(existing, record)
        loser = record if winner is existing else existing
        seen[key] = winner
        duplicates.append(
            {
                "kind": key[0],
                "value": key[1],
                "kept": winner.get("title", ""),
                "removed": loser.get("title", ""),
            }
        )
    return list(seen.values()), duplicates


def choose_better(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    a_score = int(a.get("score") or 0)
    b_score = int(b.get("score") or 0)
    if a_score != b_score:
        return a if a_score > b_score else b
    a_cites = int(a.get("citation_count") or 0)
    b_cites = int(b.get("citation_count") or 0)
    if a_cites != b_cites:
        return a if a_cites > b_cites else b
    return a if len(a.get("abstract") or "") >= len(b.get("abstract") or "") else b


def make_zotero() -> zotero.Zotero:
    settings = get_settings()
    if not settings.zotero.library_id or not settings.zotero.api_key:
        raise ValueError("Zotero library_id and api_key are required")
    library_id = settings.zotero.library_id
    if settings.zotero.library_type == "user" and not str(library_id).isdigit():
        resolved = resolve_user_library_id(settings.zotero.api_key)
        if resolved:
            library_id = resolved
    return zotero.Zotero(
        library_id,
        settings.zotero.library_type,
        settings.zotero.api_key,
    )


def resolve_user_library_id(api_key: str) -> Optional[str]:
    req = urllib.request.Request(
        "https://api.zotero.org/keys/current",
        headers={"Zotero-API-Key": api_key, "User-Agent": "MicroSurgeon-LitWatch/0.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None
    user_id = data.get("userID") or data.get("user", {}).get("id")
    return str(user_id) if user_id else None


def fetch_all_collections(zot: zotero.Zotero) -> List[Dict[str, Any]]:
    return zot.everything(zot.collections())


def fetch_existing_items(zot: zotero.Zotero) -> Dict[str, Dict[str, str]]:
    """Build DOI/arXiv/title indexes for existing Zotero top-level items."""
    raw_items = zot.everything(zot.items(itemType="-attachment"))
    doi_index: Dict[str, str] = {}
    arxiv_index: Dict[str, str] = {}
    title_index: Dict[str, str] = {}
    for item in raw_items:
        data = item.get("data", {})
        key = data.get("key", "")
        title = clean_text(data.get("title", ""))
        doi = norm_doi(data.get("DOI", ""))
        url = clean_text(data.get("url", ""))
        if doi:
            doi_index[doi] = key
            arxiv_from_doi = norm_arxiv(re.sub(r"^10\.48550/arxiv\.", "", doi, flags=re.I)) if doi.startswith("10.48550/arxiv.") else ""
            if arxiv_from_doi:
                arxiv_index[arxiv_from_doi] = key
        arxiv_match = re.search(r"arxiv\.org/(?:abs|pdf)/([^/?#]+)", url, flags=re.I)
        if arxiv_match:
            arxiv_index[norm_arxiv(arxiv_match.group(1).replace(".pdf", ""))] = key
        title_norm = norm_title(title)
        if title_norm:
            title_index[title_norm] = key
    return {"doi": doi_index, "arxiv": arxiv_index, "title": title_index}


def find_existing_duplicate(record: Dict[str, Any], indexes: Dict[str, Dict[str, str]]) -> Optional[Dict[str, str]]:
    doi = norm_doi(record.get("doi", ""))
    if doi and doi in indexes["doi"]:
        return {"kind": "doi", "value": doi, "item_key": indexes["doi"][doi]}
    arxiv_id = arxiv_from_record(record)
    if arxiv_id and arxiv_id in indexes["arxiv"]:
        return {"kind": "arxiv", "value": arxiv_id, "item_key": indexes["arxiv"][arxiv_id]}
    title = norm_title(record.get("title", ""))
    if title and title in indexes["title"]:
        return {"kind": "title", "value": title, "item_key": indexes["title"][title]}
    return None


def collection_name(record: Dict[str, Any]) -> str:
    if COLLECTION_OVERRIDE:
        return COLLECTION_OVERRIDE
    return clean_text(record.get("target_subcollection", "")) or "00_uncategorized"


def original_collection_name(record: Dict[str, Any]) -> str:
    return clean_text(record.get("target_subcollection", "")) or "00_uncategorized"


def collection_plan(records: List[Dict[str, Any]]) -> Dict[str, int]:
    counter = Counter(collection_name(record) for record in records)
    return dict(sorted(counter.items()))


def get_collection_key_by_name(collections: List[Dict[str, Any]], name: str, parent_key: Optional[str] = None) -> Optional[str]:
    for col in collections:
        data = col.get("data", {})
        if data.get("name") != name:
            continue
        current_parent = data.get("parentCollection") or None
        if parent_key is None or current_parent == parent_key:
            return data.get("key")
    return None


def ensure_collection(
    zot: zotero.Zotero,
    collections: List[Dict[str, Any]],
    name: str,
    parent_key: Optional[str] = None,
    dry_run: bool = True,
) -> str:
    existing = get_collection_key_by_name(collections, name, parent_key)
    if existing:
        return existing
    if dry_run:
        return f"DRYRUN-{name}"
    payload = {"name": name}
    if parent_key:
        payload["parentCollection"] = parent_key
    created = zot.create_collections([payload])
    key = extract_created_key(created)
    if not key:
        collections[:] = fetch_all_collections(zot)
        key = get_collection_key_by_name(collections, name, parent_key)
    if not key:
        raise RuntimeError(f"Could not create or locate Zotero collection: {name}")
    collections.append({"data": {"key": key, "name": name, "parentCollection": parent_key or False}})
    return key


def extract_created_key(response: Any) -> Optional[str]:
    if isinstance(response, dict):
        successful = response.get("successful") or {}
        if successful:
            first = next(iter(successful.values()))
            return first.get("key") or first.get("data", {}).get("key")
    return None


def creator_from_name(name: str) -> Dict[str, str]:
    return {"creatorType": "author", "name": clean_text(name)}


def item_type(record: Dict[str, Any]) -> str:
    venue = (record.get("venue") or "").lower()
    url = (record.get("url") or "").lower()
    source = (record.get("source") or "").lower()
    if "arxiv" in venue or "arxiv" in url or source == "arxiv":
        return "preprint"
    if any(term in venue for term in ["conference", "proceedings", "symposium", "workshop", "dac", "iccad", "date"]):
        return "conferencePaper"
    return "journalArticle"


def build_item_payload(record: Dict[str, Any], collection_key: str, zot: zotero.Zotero) -> Dict[str, Any]:
    itype = item_type(record)
    try:
        item = zot.item_template(itype)
    except Exception:
        itype = "journalArticle"
        item = zot.item_template(itype)

    item["title"] = clean_text(record.get("title", ""))
    item["creators"] = [creator_from_name(author) for author in (record.get("authors") or [])[:20]]
    if record.get("abstract"):
        item["abstractNote"] = clean_text(record.get("abstract", ""))
    if record.get("year"):
        item["date"] = str(record.get("year"))
    venue = clean_text(record.get("venue", ""))
    if venue:
        if itype == "conferencePaper":
            item["proceedingsTitle"] = venue
            item["conferenceName"] = venue
        elif itype == "preprint":
            item["repository"] = venue
        else:
            item["publicationTitle"] = venue
    doi = norm_doi(record.get("doi", ""))
    if doi:
        item["DOI"] = doi
    url = clean_text(record.get("url", "")) or clean_text(record.get("open_access_url", ""))
    if url:
        item["url"] = url
    tags = sorted(set(clean_tags(record)))
    item["tags"] = [{"tag": tag} for tag in tags]
    item["collections"] = [collection_key]
    return item


def clean_tags(record: Dict[str, Any]) -> List[str]:
    tags = list(record.get("tags") or [])
    tags.extend(
        [
            "AI4EDA-MicroSurgeon",
            f"lit_watch_score_{int(record.get('score') or 0)}",
            f"source_{clean_text(record.get('source', 'unknown')).replace(' ', '_')}",
            f"recommendation_{clean_text(record.get('recommendation', 'unspecified')).replace(' ', '_')}",
        ]
    )
    sub = collection_name(record)
    if sub:
        tags.append(sub)
    original_sub = original_collection_name(record)
    if original_sub and original_sub != sub:
        tags.append(original_sub)
    return [re.sub(r"\s+", "_", clean_text(tag)) for tag in tags if clean_text(tag)]


def classify_lit_role(record: Dict[str, Any]) -> str:
    title = clean_text(record.get("title", "")).lower()
    text = f"{title} {record.get('abstract', '')} {record.get('tags', '')}".lower()
    if title.startswith("the art of rtl debugging"):
        return "related work / background"
    if any(marker in text for marker in ["phoenix", "fault localization", "repair", "patch", "debug", "self-correction", "autoverifix", "arsp", "vitad", "ft-pilot"]):
        return "baseline / related work"
    if any(marker in text for marker in ["formal", "equivalence", "verification", "correctness", "specification"]):
        return "related work"
    return "background"


def full_read_needed(record: Dict[str, Any]) -> str:
    role = classify_lit_role(record)
    score = int(record.get("score") or 0)
    if score >= 5 or "baseline" in role:
        return "Yes"
    return "Yes, but after the score-5 direct baselines"


def claim_relation(record: Dict[str, Any]) -> str:
    title = clean_text(record.get("title", ""))
    title_l = title.lower()
    text = f"{title} {record.get('abstract', '')} {' '.join(record.get('tags') or [])}".lower()
    target = original_collection_name(record)
    if "ft-pilot" in title_l or "vulnerability-guided" in title_l:
        return "Supports the red-team/threat-driven bug framing, and threatens novelty as a vulnerability-guided RTL rewriting baseline."
    if title_l.startswith("from bugs to fixes") or re.search(r"\brag\b|retrieval", text):
        return "Supports the memory/retrieval claim for MicroSurgeon, and threatens novelty if its repair loop already demonstrates durable retrieval-driven RTL patching."
    if "phoenix" in title_l:
        return "Threatens the evaluation novelty claim by offering a hardware-engineering benchmark or baseline suite that Stage B should compare against or cite."
    if "debug like a human" in title_l or "fault localization" in title_l:
        return "Supports the need for localization-aware blue-team repair, and threatens novelty around processor-scale RTL debugging baselines."
    if "timing violation" in title_l or "vitad" in title_l:
        return "Supports the boundary claim that timing-adjacent RTL debugging exists, while helping separate semantic repair from deterministic timing-ECO tooling."
    if "towards llm-powered verilog rtl assistant" in title_l:
        return "Supports the self-verification/self-correction claim, and threatens novelty where MicroSurgeon relies on similar simulator-feedback repair loops."
    if "autoverifix" in title_l:
        return "Supports the functional-correctness repair claim, and threatens novelty as a direct correctness-driven Verilog repair baseline."
    if any(marker in title_l for marker in ["veri-sure", "specloop", "cktformalizer", "vericoder", "arsp"]) or any(marker in text for marker in ["formal equivalence", "formal verification", "contract-aware", "specification", "autoformalization", "correctness validation", "semantic partitioning"]):
        return "Supports the correctness-gate claim that RTL repair must be judged by semantic/formal evidence, and threatens novelty if the same gate is already central to the method."
    if any(marker in text for marker in ["repair", "patch", "self-correction", "bug identification"]):
        return "Supports the semantic RTL bug-repair claim, and threatens novelty as a direct blue-team repair baseline."
    if title_l.startswith("the art of rtl debugging"):
        return "Supports related-work coverage for RTL debugging terminology and success criteria; use it to ground claims rather than as a system baseline."
    if target == "02_rtl_repair_debug":
        return "Supports the RTL repair/debug related-work claim and may serve as a baseline depending on experimental overlap."
    return "Supports related-work coverage for the MicroSurgeon framing."


def build_note_payload(record: Dict[str, Any], parent_key: str) -> Dict[str, Any]:
    tags = ", ".join(clean_tags(record))
    why_import = clean_text(record.get("inclusion_reason", "")) or clean_text(record.get("reason", ""))
    claim = claim_relation(record)
    read_needed = full_read_needed(record)
    role = classify_lit_role(record)
    note_html = f"""
<h2>MicroSurgeon LitWatch Note</h2>
<p><b>Why import:</b> {html.escape(why_import)}</p>
<p><b>Claim threat/support:</b> {html.escape(claim)}</p>
<p><b>Needs full-text close read:</b> {html.escape(read_needed)}</p>
<p><b>Use as:</b> {html.escape(role)}</p>
<p><b>Search source:</b> {html.escape(clean_text(record.get("source", "")))}</p>
<p><b>Query:</b> {html.escape(clean_text(record.get("query", "")))}</p>
<p><b>Relevance score:</b> {int(record.get("score") or 0)}</p>
<p><b>Recommendation:</b> {html.escape(clean_text(record.get("recommendation", "")))}</p>
<p><b>Screening reason:</b> {html.escape(clean_text(record.get("reason", "")))}</p>
<p><b>Inclusion reason:</b> {html.escape(clean_text(record.get("inclusion_reason", "")))}</p>
<p><b>Relation to MicroSurgeon:</b> Candidate evidence for AI-for-EDA RTL repair/debugging, correctness gates, memory/retrieval/distillation, benchmark design, or deterministic-tool boundary analysis.</p>
<p><b>Target subcollection:</b> {html.escape(collection_name(record))}</p>
<p><b>Original screened subcollection:</b> {html.escape(original_collection_name(record))}</p>
<p><b>Tags:</b> {html.escape(tags)}</p>
""".strip()
    return {"itemType": "note", "parentItem": parent_key, "note": note_html}


def create_item(zot: zotero.Zotero, item: Dict[str, Any]) -> str:
    result = zot.create_items([item])
    key = extract_created_key(result)
    if not key:
        raise RuntimeError(f"Could not create item: {item.get('title', '')}")
    return key


def write_report(
    *,
    mode: str,
    input_path: Path,
    report_path: Path,
    min_score: int,
    recommendation: Optional[str],
    collection_override: Optional[str],
    filtered_count: int,
    input_duplicate_count: int,
    existing_duplicate_count: int,
    importable: List[Dict[str, Any]],
    skipped_existing: List[Dict[str, Any]],
    collections: Dict[str, int],
    created_count: int = 0,
    errors: Optional[List[str]] = None,
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    errors = errors or []
    lines = [
        "# Zotero Import Report",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Mode: {mode}",
        f"- Input: `{input_path}`",
        f"- Root collection: `{ROOT_COLLECTION}`",
        f"- Min score: {min_score}",
        f"- Recommendation filter: `{recommendation or 'none'}`",
        f"- Collection override: `{collection_override or 'none'}`",
        f"- Filtered candidates: {filtered_count}",
        f"- Input duplicates removed: {input_duplicate_count}",
        f"- Existing Zotero duplicates skipped: {existing_duplicate_count}",
        f"- Planned import count: {len(importable)}",
        f"- Created item count: {created_count}",
        f"- Errors: {len(errors)}",
        "",
        "## Collection Plan",
        "",
    ]
    lines.append(f"- {ROOT_COLLECTION}: {len(importable)}")
    for name, count in collections.items():
        lines.append(f"- {ROOT_COLLECTION}/{name}: {count}")
    lines.extend(["", "## Existing Duplicates Skipped", ""])
    if skipped_existing:
        for item in skipped_existing[:200]:
            lines.append(
                f"- {item['duplicate']['kind']} `{item['duplicate']['value']}` "
                f"matches Zotero item `{item['duplicate']['item_key']}`: {item['record'].get('title', '')}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Importable Candidates", ""])
    for idx, record in enumerate(importable, start=1):
        lines.append(
            f"{idx}. [{int(record.get('score') or 0)}] {record.get('title', '')} "
            f"({record.get('year') or ''}) -> {collection_name(record)}"
        )
        lines.append(f"   - Original screened subcollection: {original_collection_name(record)}")
        lines.append(f"   - Note / why import: {clean_text(record.get('inclusion_reason', '')) or clean_text(record.get('reason', ''))}")
        lines.append(f"   - Note / claim threat-support: {claim_relation(record)}")
        lines.append(f"   - Note / needs full-text close read: {full_read_needed(record)}")
        lines.append(f"   - Note / use as: {classify_lit_role(record)}")
    if errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in errors)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_plan(importable: List[Dict[str, Any]], skipped_existing: List[Dict[str, Any]], collections: Dict[str, int], report_path: Path) -> None:
    print(f"Root collection: {ROOT_COLLECTION}")
    print(f"Importable candidates: {len(importable)}")
    print(f"Existing Zotero duplicates skipped: {len(skipped_existing)}")
    print("Subcollections:")
    for name, count in collections.items():
        print(f"  - {name}: {count}")
    print("Duplicate check:")
    if skipped_existing:
        print("  - Existing Zotero duplicates were found and will be skipped.")
    else:
        print("  - No duplicate DOI/arXiv/title found against Zotero for importable candidates.")
    print(f"Report: {report_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import screened lit-watch candidates into Zotero.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--min-score", type=int, default=4)
    parser.add_argument("--recommendation", default=None, help="Optional exact recommendation filter, e.g. should_import.")
    parser.add_argument("--subcollection-override", default=None, help="Optional subcollection name for every imported record.")
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Plan only; do not write Zotero.")
    mode.add_argument("--commit", action="store_true", help="Write items and notes to Zotero.")
    args = parser.parse_args()

    global COLLECTION_OVERRIDE
    COLLECTION_OVERRIDE = clean_text(args.subcollection_override) or None
    dry_run = not args.commit
    records = load_candidates(args.input, args.min_score, clean_text(args.recommendation) or None)
    unique_records, input_duplicates = dedupe_input(records)

    zot = make_zotero()
    collections_raw = fetch_all_collections(zot)
    indexes = fetch_existing_items(zot)

    importable: List[Dict[str, Any]] = []
    skipped_existing: List[Dict[str, Any]] = []
    for record in unique_records:
        duplicate = find_existing_duplicate(record, indexes)
        if duplicate:
            skipped_existing.append({"record": record, "duplicate": duplicate})
        else:
            importable.append(record)

    plan = collection_plan(importable)
    write_report(
        mode="dry-run" if dry_run else "commit-pending",
        input_path=args.input,
        report_path=args.report,
        min_score=args.min_score,
        recommendation=clean_text(args.recommendation) or None,
        collection_override=COLLECTION_OVERRIDE,
        filtered_count=len(records),
        input_duplicate_count=len(input_duplicates),
        existing_duplicate_count=len(skipped_existing),
        importable=importable,
        skipped_existing=skipped_existing,
        collections=plan,
    )
    print_plan(importable, skipped_existing, plan, args.report)

    if dry_run:
        return 0

    created = 0
    errors: List[str] = []
    root_key = ensure_collection(zot, collections_raw, ROOT_COLLECTION, dry_run=False)
    sub_keys: Dict[str, str] = {}
    for sub_name in plan:
        sub_keys[sub_name] = ensure_collection(zot, collections_raw, sub_name, parent_key=root_key, dry_run=False)

    for record in importable:
        try:
            sub_key = sub_keys[collection_name(record)]
            item_payload = build_item_payload(record, sub_key, zot)
            item_key = create_item(zot, item_payload)
            note_payload = build_note_payload(record, item_key)
            create_item(zot, note_payload)
            created += 1
        except Exception as exc:
            errors.append(f"{record.get('title', '')}: {type(exc).__name__}: {exc}")

    write_report(
        mode="commit",
        input_path=args.input,
        report_path=args.report,
        min_score=args.min_score,
        recommendation=clean_text(args.recommendation) or None,
        collection_override=COLLECTION_OVERRIDE,
        filtered_count=len(records),
        input_duplicate_count=len(input_duplicates),
        existing_duplicate_count=len(skipped_existing),
        importable=importable,
        skipped_existing=skipped_existing,
        collections=plan,
        created_count=created,
        errors=errors,
    )
    print(f"Committed items: {created}")
    print(f"Errors: {len(errors)}")
    print(f"Report: {args.report}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
