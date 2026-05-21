from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .audit import AuditLogger, utc_now


@dataclass
class DisclosureDraft:
    rank: int
    title: str
    target_url: str
    severity: str
    cluster: str
    summary: str
    evidence_paths: list[str]
    reproduction_outline: list[str]
    impact_statement: str
    report_markdown_path: str


@dataclass
class DisclosureBundle:
    program_slug: str
    generated_at: str
    source_triage_path: str
    drafts: list[DisclosureDraft]


def generate_disclosure_drafts(
    *,
    repo_root: Path,
    triage_path: Path,
    audit_log_path: Path,
    max_drafts: int = 5,
) -> Path:
    payload = json.loads(triage_path.read_text(encoding="utf-8"))
    program_slug = payload["program_slug"]
    findings = [item for item in payload.get("findings", []) if item.get("disclosure_ready")]
    findings = findings[:max_drafts]
    audit = AuditLogger(audit_log_path)
    audit.log("disclosure.started", {"program_slug": program_slug, "triage_path": str(triage_path)})

    drafts: list[DisclosureDraft] = []
    draft_dir = repo_root / "audit" / "disclosure-drafts"
    draft_dir.mkdir(parents=True, exist_ok=True)

    for index, finding in enumerate(findings, start=1):
        md_path = draft_dir / f"{program_slug}-{finding['cluster']}.md"
        reproduction = _reproduction_outline(finding)
        md_path.write_text(_render_disclosure_markdown(finding, reproduction), encoding="utf-8")
        drafts.append(
            DisclosureDraft(
                rank=index,
                title=_draft_title(finding),
                target_url=finding["target_url"],
                severity=finding["severity"],
                cluster=finding["cluster"],
                summary=_summary(finding),
                evidence_paths=finding["evidence_paths"],
                reproduction_outline=reproduction,
                impact_statement=_impact_statement(finding),
                report_markdown_path=str(md_path.relative_to(repo_root)),
            )
        )

    bundle = DisclosureBundle(
        program_slug=program_slug,
        generated_at=utc_now(),
        source_triage_path=str(triage_path),
        drafts=drafts,
    )

    bundle_path = draft_dir / f"{program_slug}-phase6-disclosures.json"
    bundle_path.write_text(json.dumps(asdict(bundle), indent=2) + "\n", encoding="utf-8")

    playbook_path = repo_root / "knowledge" / "wiki" / "playbooks" / f"{program_slug}-phase6-disclosures.md"
    playbook_path.parent.mkdir(parents=True, exist_ok=True)
    playbook_path.write_text(_render_bundle_markdown(bundle), encoding="utf-8")

    audit.log("disclosure.completed", {"program_slug": program_slug, "bundle_path": str(bundle_path), "draft_count": len(drafts)})
    return bundle_path


def _draft_title(finding: dict) -> str:
    return f"[Draft] {finding['title']}"


def _summary(finding: dict) -> str:
    return (
        f"Browser and validation artifacts indicate a {finding['cluster']} candidate on {finding['target_url']} "
        f"with severity {finding['severity']} and score {finding['score']}."
    )


def _impact_statement(finding: dict) -> str:
    if finding["cluster"] == "auth-session":
        return "Potential session confusion, callback abuse, or broken redirect/state binding."
    if finding["cluster"] == "client-injection":
        return "Potential client-side trust break, sink abuse, or postMessage-origin weakness."
    if finding["cluster"] == "wallet-signature":
        return "Potential wallet signature replay, weak domain separation, or unsafe signing UX assumptions."
    return "Potential valid security issue requiring deeper but still safe verification."


def _reproduction_outline(finding: dict) -> list[str]:
    return [
        "Review the attached screenshot and DOM artifact.",
        "Replay only read-only navigation around the observed target surface.",
        f"Follow the next safe step: {finding['next_safe_step']}",
        "Do not submit destructive payloads or state-changing requests without explicit approval.",
    ]


def _render_disclosure_markdown(finding: dict, reproduction: list[str]) -> str:
    evidence = "\n".join(f"- `{item}`" for item in finding["evidence_paths"]) or "- none"
    repro = "\n".join(f"- {item}" for item in reproduction)
    return (
        f"# {_draft_title(finding)}\n\n"
        f"- target-url: `{finding['target_url']}`\n"
        f"- severity: `{finding['severity']}`\n"
        f"- cluster: `{finding['cluster']}`\n\n"
        "## Summary\n"
        f"{_summary(finding)}\n\n"
        "## Evidence\n"
        f"{evidence}\n\n"
        "## Reproduction outline\n"
        f"{repro}\n\n"
        "## Impact hypothesis\n"
        f"{_impact_statement(finding)}\n"
    )


def _render_bundle_markdown(bundle: DisclosureBundle) -> str:
    lines = [
        f"# Phase 6 disclosure drafts for {bundle.program_slug}",
        "",
        f"- generated-at: `{bundle.generated_at}`",
        f"- source-triage: `{bundle.source_triage_path}`",
        "",
    ]
    for draft in bundle.drafts:
        evidence_lines = [f"- `{item}`" for item in draft.evidence_paths] or ["- none"]
        reproduction_lines = [f"- {item}" for item in draft.reproduction_outline] or ["- none"]
        lines.extend(
            [
                f"## {draft.rank}. {draft.title}",
                "",
                f"- severity: `{draft.severity}`",
                f"- cluster: `{draft.cluster}`",
                f"- target-url: `{draft.target_url}`",
                f"- draft-path: `{draft.report_markdown_path}`",
                "",
                draft.summary,
                "",
                "### Evidence paths",
                *evidence_lines,
                "",
                "### Reproduction outline",
                *reproduction_lines,
                "",
                "### Impact statement",
                f"- {draft.impact_statement}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
