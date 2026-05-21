from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .knowledge import SourceRecord, register_source
from .programs import slugify


@dataclass
class ReportSummary:
    source: SourceRecord
    title: str
    finding_slug: str
    bug_classes: list[str]
    validation_clues: list[str]
    impact_clues: list[str]
    summary_excerpt: str


BUG_CLASS_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("idor-access-control", ("idor", "access control", "broken access control", "authorization bypass")),
    ("auth-session", ("oauth", "jwt", "session", "authentication bypass", "account takeover")),
    ("client-injection", ("xss", "dom xss", "postmessage", "content-security-policy", "csrf token leak")),
    ("signature-domain", ("permit", "signature replay", "domain separator", "eip-712", "meta-tx")),
    ("upgrade-initialization", ("proxy", "initializer", "upgradeability", "storage collision")),
    ("accounting-oracle", ("oracle", "rounding", "share price", "accounting", "liquidation")),
)

VALIDATION_PATTERNS: tuple[str, ...] = (
    "proof of concept",
    "steps to reproduce",
    "reproduce",
    "validation",
    "request",
    "response",
)

IMPACT_PATTERNS: tuple[str, ...] = (
    "account takeover",
    "unauthorized access",
    "fund loss",
    "token theft",
    "xss",
    "admin takeover",
)


def mine_report(
    *,
    repo_root: Path,
    source_path: Path,
    title: str,
    kind: str,
    reference_url: str | None = None,
) -> ReportSummary:
    source = register_source(repo_root, source_path, title=title, kind=kind)
    text = source_path.read_text(encoding="utf-8", errors="replace")
    finding_slug = slugify(title)
    summary = ReportSummary(
        source=source,
        title=title,
        finding_slug=finding_slug,
        bug_classes=_extract_matches(text, BUG_CLASS_PATTERNS),
        validation_clues=_extract_literals(text, VALIDATION_PATTERNS),
        impact_clues=_extract_literals(text, IMPACT_PATTERNS),
        summary_excerpt=_excerpt(text),
    )
    finding_dir = repo_root / "knowledge" / "wiki" / "findings"
    finding_dir.mkdir(parents=True, exist_ok=True)
    finding_dir.joinpath(f"{finding_slug}.md").write_text(
        _render_finding_page(summary, reference_url),
        encoding="utf-8",
    )
    return summary


def _extract_matches(text: str, patterns: tuple[tuple[str, tuple[str, ...]], ...]) -> list[str]:
    lowered = text.lower()
    matches: list[str] = []
    for label, keywords in patterns:
        if any(keyword in lowered for keyword in keywords):
            matches.append(label)
    return matches


def _extract_literals(text: str, patterns: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [pattern for pattern in patterns if pattern in lowered]


def _excerpt(text: str, limit: int = 280) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:limit]


def _render_bullets(items: list[str]) -> str:
    if not items:
        return "- none\n"
    return "".join(f"- {item}\n" for item in items)


def _render_finding_page(summary: ReportSummary, reference_url: str | None) -> str:
    reference_block = f"- reference-url: {reference_url}\n" if reference_url else ""
    return (
        f"# {summary.title}\n\n"
        f"- source-path: `{summary.source.stored_path}`\n"
        f"{reference_block}"
        f"- source-kind: `{summary.source.kind}`\n\n"
        "## Bug classes\n"
        f"{_render_bullets(summary.bug_classes)}\n"
        "## Validation clues\n"
        f"{_render_bullets(summary.validation_clues)}\n"
        "## Impact clues\n"
        f"{_render_bullets(summary.impact_clues)}\n"
        "## Excerpt\n"
        f"{summary.summary_excerpt}\n"
    )
