#!/usr/bin/env python3
"""Dry-run literature search for the MicroSurgeon AI4EDA watch list.

This script queries public metadata APIs only. It does not read .env and does
not write to Zotero.
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


USER_AGENT = "MicroSurgeon-LitWatch/0.1 (public metadata dry-run)"
DEFAULT_TIMEOUT = 30


def parse_inline_list(value: str) -> List[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return [strip_quotes(value)] if value else []
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [strip_quotes(part.strip()) for part in inner.split(",")]


def strip_quotes(value: str) -> str:
    value = value.strip()
    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        return value[1:-1]
    return value


def load_query_config(path: Path) -> Dict[str, Any]:
    """Parse the small YAML subset used by configs/lit_watch_ai4eda.yaml."""
    text = path.read_text(encoding="utf-8")
    defaults: Dict[str, Any] = {}
    queries: List[Dict[str, Any]] = []
    section: Optional[str] = None
    current: Optional[Dict[str, Any]] = None
    list_key: Optional[str] = None

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if indent == 0 and line.endswith(":"):
            section = line[:-1]
            list_key = None
            continue

        if section == "defaults":
            if indent == 2 and ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if value == "":
                    defaults[key] = []
                    list_key = key
                else:
                    defaults[key] = coerce_value(value)
                    list_key = None
            elif indent == 4 and line.startswith("- ") and list_key:
                defaults.setdefault(list_key, []).append(strip_quotes(line[2:]))
            continue

        if section == "queries":
            if indent == 2 and line.startswith("- "):
                if current:
                    queries.append(current)
                current = {}
                payload = line[2:]
                if ":" in payload:
                    key, value = payload.split(":", 1)
                    current[key.strip()] = coerce_value(value.strip())
                continue
            if current is not None and indent >= 4 and ":" in line:
                key, value = line.split(":", 1)
                current[key.strip()] = coerce_value(value.strip())

    if current:
        queries.append(current)

    for query in queries:
        merged = dict(defaults)
        merged.update(query)
        query.clear()
        query.update(merged)
    return {"defaults": defaults, "queries": queries}


def coerce_value(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        return parse_inline_list(value)
    value = strip_quotes(value)
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def http_json(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            data = resp.read()
    except urllib.error.URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT, context=context) as resp:
            data = resp.read()
    return json.loads(data.decode("utf-8", errors="replace"))


def http_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT, context=context) as resp:
            return resp.read().decode("utf-8", errors="replace")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(v) for v in value if v)
    value = re.sub(r"<[^>]+>", " ", str(value))
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_doi(value: Any) -> str:
    text = clean_text(value)
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text, flags=re.I)
    return text.lower()


def openalex_abstract(inverted: Optional[Dict[str, List[int]]]) -> str:
    if not inverted:
        return ""
    positions: List[tuple[int, str]] = []
    for word, idxs in inverted.items():
        for idx in idxs:
            positions.append((idx, word))
    return " ".join(word for _, word in sorted(positions))


def get_year_from_date_parts(obj: Dict[str, Any]) -> Optional[int]:
    for key in ("published-print", "published-online", "published", "issued"):
        parts = obj.get(key, {}).get("date-parts") if isinstance(obj.get(key), dict) else None
        if parts and parts[0]:
            try:
                return int(parts[0][0])
            except Exception:
                return None
    return None


def arxiv_id_from_url(url: str) -> str:
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^/?#]+)", url or "", flags=re.I)
    return match.group(1).replace(".pdf", "") if match else ""


def record_base(
    *,
    title: str,
    authors: Iterable[str],
    year: Any,
    venue: str,
    doi: str,
    arxiv_id: str,
    url: str,
    abstract: str,
    source: str,
    citation_count: Any,
    open_access_url: str,
    query_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        year_value = int(year) if year else None
    except Exception:
        year_value = None
    try:
        citation_value = int(citation_count) if citation_count is not None else None
    except Exception:
        citation_value = None
    return {
        "title": clean_text(title),
        "authors": [clean_text(a) for a in authors if clean_text(a)],
        "year": year_value,
        "venue": clean_text(venue),
        "doi": normalize_doi(doi),
        "arxiv_id": clean_text(arxiv_id),
        "url": clean_text(url),
        "abstract": clean_text(abstract),
        "source": source,
        "citation_count": citation_value,
        "open_access_url": clean_text(open_access_url),
        "query": query_cfg["query"],
        "tags": query_cfg.get("tags", []),
        "target_subcollection": query_cfg.get("target_subcollection", ""),
        "inclusion_reason": query_cfg.get("inclusion_reason", ""),
    }


def search_openalex(query_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    params = {
        "search": query_cfg["query"],
        "per-page": str(query_cfg["max_results"]),
        "filter": f"from_publication_date:{query_cfg['year_from']}-01-01",
        "select": "id,doi,title,publication_year,primary_location,authorships,cited_by_count,abstract_inverted_index",
    }
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    data = http_json(url)
    records = []
    for item in data.get("results", []):
        authors = [
            a.get("author", {}).get("display_name", "")
            for a in item.get("authorships", [])
        ]
        loc = item.get("primary_location") or {}
        source = loc.get("source") or {}
        oa_url = (loc.get("landing_page_url") or loc.get("pdf_url") or "")
        records.append(
            record_base(
                title=item.get("title", ""),
                authors=authors,
                year=item.get("publication_year"),
                venue=source.get("display_name", ""),
                doi=item.get("doi", ""),
                arxiv_id=arxiv_id_from_url(loc.get("landing_page_url", "") or item.get("id", "")),
                url=loc.get("landing_page_url") or item.get("id", ""),
                abstract=openalex_abstract(item.get("abstract_inverted_index")),
                source="openalex",
                citation_count=item.get("cited_by_count"),
                open_access_url=oa_url,
                query_cfg=query_cfg,
            )
        )
    return records


def search_semantic_scholar(query_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    params = {
        "query": query_cfg["query"],
        "limit": str(min(int(query_cfg["max_results"]), 100)),
        "fields": "title,authors,year,venue,abstract,citationCount,externalIds,url,openAccessPdf",
    }
    url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params)
    data = http_json(url)
    records = []
    for item in data.get("data", []):
        year = item.get("year")
        if year and int(year) < int(query_cfg["year_from"]):
            continue
        external = item.get("externalIds") or {}
        oa = item.get("openAccessPdf") or {}
        records.append(
            record_base(
                title=item.get("title", ""),
                authors=[a.get("name", "") for a in item.get("authors", [])],
                year=year,
                venue=item.get("venue", ""),
                doi=external.get("DOI", ""),
                arxiv_id=external.get("ArXiv", ""),
                url=item.get("url", ""),
                abstract=item.get("abstract", ""),
                source="semantic_scholar",
                citation_count=item.get("citationCount"),
                open_access_url=oa.get("url", ""),
                query_cfg=query_cfg,
            )
        )
    return records


def search_arxiv(query_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    query = re.sub(r"\b(AND|OR)\b", " ", query_cfg["query"], flags=re.I)
    query = re.sub(r"[()\"]", " ", query)
    query = re.sub(r"\s+", " ", query).strip()
    params = {
        "search_query": "all:" + query,
        "start": "0",
        "max_results": str(min(int(query_cfg["max_results"]), 50)),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    text = http_text(url)
    root = ET.fromstring(text)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    records = []
    for entry in root.findall("a:entry", ns):
        entry_url = entry.findtext("a:id", default="", namespaces=ns)
        published = entry.findtext("a:published", default="", namespaces=ns)
        year = int(published[:4]) if published[:4].isdigit() else None
        if year and year < int(query_cfg["year_from"]):
            continue
        authors = [
            clean_text(author.findtext("a:name", default="", namespaces=ns))
            for author in entry.findall("a:author", ns)
        ]
        pdf_url = ""
        for link in entry.findall("a:link", ns):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href", "")
        records.append(
            record_base(
                title=entry.findtext("a:title", default="", namespaces=ns),
                authors=authors,
                year=year,
                venue="arXiv",
                doi="",
                arxiv_id=arxiv_id_from_url(entry_url),
                url=entry_url,
                abstract=entry.findtext("a:summary", default="", namespaces=ns),
                source="arxiv",
                citation_count=None,
                open_access_url=pdf_url,
                query_cfg=query_cfg,
            )
        )
    return records


def search_crossref(query_cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    params = {
        "query": query_cfg["query"],
        "rows": str(min(int(query_cfg["max_results"]), 100)),
        "filter": f"from-pub-date:{query_cfg['year_from']}-01-01",
        "select": "title,author,published-print,published-online,published,issued,container-title,DOI,URL,abstract,is-referenced-by-count",
    }
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    data = http_json(url)
    records = []
    for item in data.get("message", {}).get("items", []):
        authors = []
        for author in item.get("author", []):
            name = " ".join(part for part in [author.get("given", ""), author.get("family", "")] if part)
            authors.append(name)
        url_value = item.get("URL", "")
        records.append(
            record_base(
                title=item.get("title", [""])[0] if item.get("title") else "",
                authors=authors,
                year=get_year_from_date_parts(item),
                venue=item.get("container-title", [""])[0] if item.get("container-title") else "",
                doi=item.get("DOI", ""),
                arxiv_id=arxiv_id_from_url(url_value),
                url=url_value,
                abstract=item.get("abstract", ""),
                source="crossref",
                citation_count=item.get("is-referenced-by-count"),
                open_access_url="",
                query_cfg=query_cfg,
            )
        )
    return records


SEARCHERS = {
    "openalex": search_openalex,
    "semantic_scholar": search_semantic_scholar,
    "arxiv": search_arxiv,
    "crossref": search_crossref,
}


def log_line(log_path: Path, message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{timestamp} {message}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run public literature search.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    log_path = args.out.parent / "lit_watch_search.log"
    report_path = args.out.parent / "search_report.md"
    if log_path.exists():
        log_path.unlink()

    config = load_query_config(args.config)
    queries = config["queries"]
    total = 0
    warnings: List[str] = []
    source_counts: Dict[str, int] = {name: 0 for name in SEARCHERS}

    with args.out.open("w", encoding="utf-8") as out_fh:
        for idx, query_cfg in enumerate(queries, start=1):
            sources = query_cfg.get("source") or list(SEARCHERS)
            print(f"[{idx}/{len(queries)}] {query_cfg['target_subcollection']} :: {query_cfg['query'][:80]}")
            for source in sources:
                searcher = SEARCHERS.get(source)
                if not searcher:
                    warning = f"WARNING unknown source={source} query={query_cfg['query']}"
                    warnings.append(warning)
                    log_line(log_path, warning)
                    continue
                try:
                    records = searcher(query_cfg)
                    for record in records:
                        out_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                    total += len(records)
                    source_counts[source] = source_counts.get(source, 0) + len(records)
                    log_line(log_path, f"INFO source={source} count={len(records)} query={query_cfg['query']}")
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, ET.ParseError, Exception) as exc:
                    warning = (
                        f"WARNING source={source} error={type(exc).__name__}: {exc} "
                        f"query={query_cfg['query']}"
                    )
                    warnings.append(warning)
                    log_line(log_path, warning)
                time.sleep(0.25)

    report = [
        "# Literature Search Dry Run",
        "",
        f"- Config: `{args.config}`",
        f"- Output: `{args.out}`",
        f"- Raw candidates: {total}",
        f"- Warnings: {len(warnings)}",
        "",
        "## Source Counts",
        "",
    ]
    for source, count in sorted(source_counts.items()):
        report.append(f"- {source}: {count}")
    if warnings:
        report.extend(["", "## Warnings", ""])
        report.extend(f"- {w}" for w in warnings)
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"Raw candidates: {total}")
    print(f"Warnings: {len(warnings)}")
    print(f"Wrote: {args.out}")
    print(f"Log: {log_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
