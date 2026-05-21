from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "source"


@dataclass
class SourceRecord:
    title: str
    kind: str
    slug: str
    ingested_at: str
    stored_path: str
    original_path: str


def register_source(repo_root: Path, source_path: Path, title: str, kind: str, slug: str | None = None) -> SourceRecord:
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    kb_root = repo_root / "knowledge"
    raw_dir = kb_root / "raw" / kind
    raw_dir.mkdir(parents=True, exist_ok=True)

    source_slug = slug or _slugify(title)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = raw_dir / f"{timestamp}-{source_slug}{source_path.suffix or '.txt'}"
    shutil.copy2(source_path, destination)

    record = SourceRecord(
        title=title,
        kind=kind,
        slug=source_slug,
        ingested_at=datetime.now(timezone.utc).isoformat(),
        stored_path=str(destination.relative_to(repo_root)),
        original_path=str(source_path),
    )

    catalog = kb_root / "catalog" / "sources.jsonl"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    with catalog.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")

    return record
