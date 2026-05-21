from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .audit import utc_now
from .programs import ProgramProfile, load_program_profile
from .taxonomy import BugClass, get_bug_class_by_name


@dataclass
class ValidationTask:
    rank: int
    title: str
    bug_class_id: str
    objective: str
    target_urls: list[str]
    evidence_inputs: list[str]
    safe_checks: list[str]
    suggested_artifacts: list[str]
    safety_notes: list[str]
    caveman_handoff: str


@dataclass
class ValidationBundle:
    program_slug: str
    generated_at: str
    source_run_path: str
    tasks: list[ValidationTask]


def build_validation_bundle(repo_root: Path, run_path: Path, max_tasks: int = 3) -> Path:
    run_payload = json.loads(run_path.read_text(encoding="utf-8"))
    program_slug = run_payload["program_slug"]
    profile = load_program_profile(repo_root, program_slug)
    top_hypotheses = run_payload.get("top_hypotheses", [])[:max_tasks]
    recon_reports = run_payload.get("recon_reports", [])
    finding_pages = run_payload.get("finding_pages", [])
    target_urls = _target_urls_from_recon_reports(repo_root, recon_reports)

    tasks: list[ValidationTask] = []
    for index, title in enumerate(top_hypotheses, start=1):
        bug_class = get_bug_class_by_name(title)
        if bug_class is None:
            continue
        tasks.append(
            ValidationTask(
                rank=index,
                title=bug_class.name,
                bug_class_id=bug_class.id,
                objective=_objective(profile, bug_class),
                target_urls=target_urls,
                evidence_inputs=_evidence_inputs(profile, recon_reports, finding_pages),
                safe_checks=list(bug_class.safe_checks),
                suggested_artifacts=_suggested_artifacts(profile, bug_class),
                safety_notes=_safety_notes(profile, bug_class),
                caveman_handoff=_caveman_handoff(profile, bug_class),
            )
        )

    bundle = ValidationBundle(
        program_slug=program_slug,
        generated_at=utc_now(),
        source_run_path=str(run_path),
        tasks=tasks,
    )

    bundle_dir = repo_root / "audit" / "validation"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundle_dir / f"{program_slug}-phase2-validation.json"
    bundle_path.write_text(json.dumps(asdict(bundle), indent=2) + "\n", encoding="utf-8")

    wiki_path = repo_root / "knowledge" / "wiki" / "playbooks" / f"{program_slug}-phase2-validation.md"
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    wiki_path.write_text(_render_bundle_markdown(bundle), encoding="utf-8")
    return bundle_path


def _objective(profile: ProgramProfile, bug_class: BugClass) -> str:
    return f"Validate whether {profile.name} exposes {bug_class.name.lower()} using only reversible checks."


def _evidence_inputs(profile: ProgramProfile, recon_reports: list[str], finding_pages: list[str]) -> list[str]:
    inputs = [f"knowledge/programs/{profile.slug}.json", *recon_reports, *finding_pages]
    return [item for item in inputs if item]


def _target_urls_from_recon_reports(repo_root: Path, recon_reports: list[str]) -> list[str]:
    urls: list[str] = []
    for report_path in recon_reports:
        path = repo_root / report_path
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        target = payload.get("target")
        if target:
            urls.append(target)
    return urls


def _suggested_artifacts(profile: ProgramProfile, bug_class: BugClass) -> list[str]:
    base = [
        f"screenshots/{profile.slug}-{bug_class.id}.png",
        f"notes/{profile.slug}-{bug_class.id}.md",
    ]
    if profile.platform in {"web2", "hybrid"}:
        base.append(f"requests/{profile.slug}-{bug_class.id}.http")
    if profile.platform in {"web3", "hybrid"}:
        base.append(f"simulations/{profile.slug}-{bug_class.id}.md")
    return base


def _safety_notes(profile: ProgramProfile, bug_class: BugClass) -> list[str]:
    notes = [
        "no live exploitation",
        "no state-changing requests unless explicitly approved later",
        "capture only minimum proof needed",
    ]
    if profile.platform in {"web3", "hybrid"} and bug_class.id.startswith("web3-"):
        notes.append("prefer local simulation or static contract review before any on-chain interaction")
    if profile.platform in {"web2", "hybrid"} and bug_class.id.startswith("web2-"):
        notes.append("prefer browser observation and read-only requests before authenticated replay")
    return notes


def _caveman_handoff(profile: ProgramProfile, bug_class: BugClass) -> str:
    return (
        f"fact: validate {bug_class.id} on {profile.slug}\n"
        "impact: could upgrade from signal to confirmed issue\n"
        "next: run only reversible checks and capture artifacts"
    )


def _render_bundle_markdown(bundle: ValidationBundle) -> str:
    lines = [
        f"# Phase 2 validation bundle for {bundle.program_slug}",
        "",
        f"- generated-at: `{bundle.generated_at}`",
        f"- source-run: `{bundle.source_run_path}`",
        "",
    ]
    for task in bundle.tasks:
        evidence_lines = [f"- `{item}`" for item in task.evidence_inputs] or ["- none"]
        check_lines = [f"- {item}" for item in task.safe_checks] or ["- none"]
        artifact_lines = [f"- `{item}`" for item in task.suggested_artifacts] or ["- none"]
        safety_lines = [f"- {item}" for item in task.safety_notes] or ["- none"]
        lines.extend(
            [
                f"## {task.rank}. {task.title}",
                "",
                f"- bug-class-id: `{task.bug_class_id}`",
                f"- objective: {task.objective}",
                f"- target-urls: {', '.join(task.target_urls) if task.target_urls else 'none'}",
                "",
                "### Evidence inputs",
                *evidence_lines,
                "",
                "### Safe checks",
                *check_lines,
                "",
                "### Suggested artifacts",
                *artifact_lines,
                "",
                "### Safety notes",
                *safety_lines,
                "",
                "### Caveman handoff",
                "```text",
                task.caveman_handoff,
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
