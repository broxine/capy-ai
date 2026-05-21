from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .audit import utc_now


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "program"


@dataclass
class ProgramProfile:
    name: str
    slug: str
    platform: str
    program_url: str | None
    scope_domains: list[str]
    assets: list[str]
    exclusions: list[str]
    tags: list[str]
    notes: list[str]
    created_at: str


def write_program_profile(
    *,
    repo_root: Path,
    name: str,
    platform: str,
    program_url: str | None,
    scope_domains: list[str],
    assets: list[str],
    exclusions: list[str],
    tags: list[str],
    notes: list[str],
) -> ProgramProfile:
    profile = ProgramProfile(
        name=name,
        slug=slugify(name),
        platform=platform,
        program_url=program_url,
        scope_domains=scope_domains,
        assets=assets,
        exclusions=exclusions,
        tags=tags,
        notes=notes,
        created_at=utc_now(),
    )

    profile_dir = repo_root / "knowledge" / "programs"
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profile_dir / f"{profile.slug}.json"
    profile_path.write_text(json.dumps(asdict(profile), indent=2) + "\n", encoding="utf-8")

    wiki_dir = repo_root / "knowledge" / "wiki" / "programs"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    wiki_path = wiki_dir / f"{profile.slug}.md"
    wiki_path.write_text(_render_program_page(profile), encoding="utf-8")

    return profile


def load_program_profile(repo_root: Path, slug_or_path: str) -> ProgramProfile:
    path = Path(slug_or_path)
    if not path.exists():
        path = repo_root / "knowledge" / "programs" / f"{slug_or_path}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ProgramProfile(**payload)


def _render_section(items: list[str]) -> str:
    if not items:
        return "- none\n"
    return "".join(f"- {item}\n" for item in items)


def _render_program_page(profile: ProgramProfile) -> str:
    url_line = profile.program_url or "not-set"
    return (
        f"# {profile.name}\n\n"
        f"- slug: `{profile.slug}`\n"
        f"- platform: `{profile.platform}`\n"
        f"- program-url: {url_line}\n"
        f"- created-at: `{profile.created_at}`\n\n"
        "## Scope domains\n"
        f"{_render_section(profile.scope_domains)}\n"
        "## Assets\n"
        f"{_render_section(profile.assets)}\n"
        "## Exclusions\n"
        f"{_render_section(profile.exclusions)}\n"
        "## Tags\n"
        f"{_render_section(profile.tags)}\n"
        "## Analyst notes\n"
        f"{_render_section(profile.notes)}"
    )
