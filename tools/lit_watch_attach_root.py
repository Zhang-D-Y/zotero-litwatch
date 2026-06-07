#!/usr/bin/env python3
"""Attach LitWatch subcollection items to the root collection.

This fixes CLI compatibility for main.py summarize/research, which scan the
named collection directly and do not recurse into subcollections.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from pyzotero import zotero

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import get_settings


ROOT_COLLECTION = "AI4EDA-MicroSurgeon-LitWatch"


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


def make_zotero() -> zotero.Zotero:
    settings = get_settings()
    library_id = settings.zotero.library_id
    if settings.zotero.library_type == "user" and not str(library_id).isdigit():
        resolved = resolve_user_library_id(settings.zotero.api_key)
        if resolved:
            library_id = resolved
    return zotero.Zotero(library_id, settings.zotero.library_type, settings.zotero.api_key)


def get_collection_key(collections: List[Dict[str, Any]], name: str, parent: Optional[str] = None) -> Optional[str]:
    for col in collections:
        data = col.get("data", {})
        if data.get("name") != name:
            continue
        if parent is None or (data.get("parentCollection") or None) == parent:
            return data.get("key")
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    if args.commit and args.dry_run:
        raise SystemExit("Use only one of --dry-run or --commit")
    dry_run = not args.commit

    zot = make_zotero()
    collections = zot.everything(zot.collections())
    root_key = get_collection_key(collections, ROOT_COLLECTION)
    if not root_key:
        raise SystemExit(f"Root collection not found: {ROOT_COLLECTION}")

    subcollections = [
        col for col in collections
        if (col.get("data", {}).get("parentCollection") or None) == root_key
    ]

    seen: Dict[str, Dict[str, Any]] = {}
    for sub in subcollections:
        sub_key = sub["data"]["key"]
        items = zot.everything(zot.collection_items(sub_key))
        for item in items:
            data = item.get("data", {})
            if data.get("itemType") in {"attachment", "note"}:
                continue
            key = data.get("key")
            if key and root_key not in (data.get("collections") or []):
                seen[key] = item

    print(f"Root collection: {ROOT_COLLECTION}")
    print(f"Subcollections scanned: {len(subcollections)}")
    print(f"Items to attach to root: {len(seen)}")
    if dry_run:
        return 0

    attached = 0
    for item in seen.values():
        response = zot.addto_collection(root_key, item)
        if response is True or 200 <= getattr(response, "status_code", 0) < 300:
            attached += 1
    print(f"Attached to root: {attached}")
    return 0 if attached == len(seen) else 1


if __name__ == "__main__":
    raise SystemExit(main())
