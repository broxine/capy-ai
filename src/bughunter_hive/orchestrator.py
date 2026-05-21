from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .audit import AuditLogger, utc_now
from .planning import CampaignPlan, build_campaign_plan
from .programs import ProgramProfile, write_program_profile
from .recon import run_recon
from .report_mining import ReportSummary, mine_report


@dataclass
class OrchestratorRun:
    run_id: str
    generated_at: str
    manifest_path: str
    program_slug: str
    program_profile_path: str
    report_titles: list[str]
    finding_pages: list[str]
    top_hypotheses: list[str]
    recon_reports: list[str]
    team_handoffs: dict[str, str]


def run_orchestrator_from_manifest(
    *,
    repo_root: Path,
    manifest_path: Path,
    audit_log_path: Path,
    kill_switch_path: Path,
) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    generated_at = utc_now()
    audit = AuditLogger(audit_log_path)
    audit.log("orchestrator.started", {"manifest_path": str(manifest_path), "generated_at": generated_at})

    program = manifest["program"]
    profile = write_program_profile(
        repo_root=repo_root,
        name=program["name"],
        platform=program["platform"],
        program_url=program.get("program_url"),
        scope_domains=program.get("scope_domains", []),
        assets=program.get("assets", []),
        exclusions=program.get("exclusions", []),
        tags=program.get("tags", []),
        notes=program.get("notes", []),
    )

    report_summaries: list[ReportSummary] = []
    for item in manifest.get("reports", []):
        summary = mine_report(
            repo_root=repo_root,
            source_path=_resolve_path(manifest_path.parent, item["source"]),
            title=item["title"],
            kind=item.get("kind", "report"),
            reference_url=item.get("reference_url"),
        )
        report_summaries.append(summary)

    plan = build_campaign_plan(repo_root, profile, limit=manifest.get("plan_limit", 5))

    recon_reports: list[Path] = []
    recon_artifacts_dir = repo_root / "audit" / "recon"
    for target in manifest.get("recon_targets", []):
        report_path = run_recon(
            target=target,
            program=profile.slug,
            scope_domains=program.get("scope_domains", []),
            audit_path=audit_log_path,
            artifacts_dir=recon_artifacts_dir,
            kill_switch_path=kill_switch_path,
            allow_private_targets=bool(manifest.get("allow_private_targets", False)),
            timeout=int(manifest.get("recon_timeout", 10)),
        )
        recon_reports.append(report_path)

    run = OrchestratorRun(
        run_id=f"{profile.slug}-{generated_at.replace(':', '').replace('+', '_')}",
        generated_at=generated_at,
        manifest_path=str(manifest_path),
        program_slug=profile.slug,
        program_profile_path=f"knowledge/programs/{profile.slug}.json",
        report_titles=[item.title for item in report_summaries],
        finding_pages=[f"knowledge/wiki/findings/{item.finding_slug}.md" for item in report_summaries],
        top_hypotheses=[item.title for item in plan.hypotheses[:3]],
        recon_reports=[str(path.relative_to(repo_root)) for path in recon_reports],
        team_handoffs=_team_handoffs(profile, report_summaries, plan, recon_reports, repo_root),
    )

    run_dir = repo_root / "audit" / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    run_path = run_dir / f"{profile.slug}-phase2-run.json"
    run_path.write_text(json.dumps(asdict(run), indent=2) + "\n", encoding="utf-8")

    playbook_path = repo_root / "knowledge" / "wiki" / "playbooks" / f"{profile.slug}-phase2-run.md"
    playbook_path.parent.mkdir(parents=True, exist_ok=True)
    playbook_path.write_text(_render_run_markdown(run), encoding="utf-8")

    audit.log(
        "orchestrator.completed",
        {
            "program_slug": profile.slug,
            "run_path": str(run_path),
            "playbook_path": str(playbook_path),
            "recon_reports": run.recon_reports,
        },
    )
    return run_path


def _resolve_path(base_dir: Path, path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _team_handoffs(
    profile: ProgramProfile,
    reports: list[ReportSummary],
    plan: CampaignPlan,
    recon_reports: list[Path],
    repo_root: Path,
) -> dict[str, str]:
    top_hypothesis = plan.hypotheses[0].title if plan.hypotheses else "none"
    rnd_classes = sorted({bug for report in reports for bug in report.bug_classes}) or ["none"]
    recon_names = [str(path.relative_to(repo_root)) for path in recon_reports] or ["none"]
    return {
        "rnd": (
            f"fact: mined {len(reports)} public reports, classes {', '.join(rnd_classes[:3])}\n"
            "impact: prior disclosures now grounded in KB\n"
            "next: feed strategy with reusable primitives"
        ),
        "plan_strategy": (
            f"fact: top hypothesis {top_hypothesis.lower()}\n"
            "impact: first-pass validation order now ranked\n"
            "next: hand recon targets to execution"
        ),
        "execution": (
            f"fact: produced {len(recon_reports)} recon report(s), latest {recon_names[-1]}\n"
            "impact: passive evidence bundle ready\n"
            "next: validator reviews top sinks and auth edges"
        ),
        "ceo": (
            f"fact: program {profile.slug} profiled and routed end-to-end\n"
            "impact: phase-2 workflow completed without live actions\n"
            "next: escalate only safest validation tasks"
        ),
    }


def _render_run_markdown(run: OrchestratorRun) -> str:
    report_lines = [f"- {title}" for title in run.report_titles] or ["- none"]
    hypothesis_lines = [f"- {title}" for title in run.top_hypotheses] or ["- none"]
    recon_lines = [f"- `{path}`" for path in run.recon_reports] or ["- none"]
    sections = [
        f"# Phase 2 orchestrator run for {run.program_slug}",
        "",
        f"- generated-at: `{run.generated_at}`",
        f"- manifest: `{run.manifest_path}`",
        f"- profile: `{run.program_profile_path}`",
        "",
        "## Reports mined",
        *report_lines,
        "",
        "## Top hypotheses",
        *hypothesis_lines,
        "",
        "## Recon reports",
        *recon_lines,
        "",
        "## Team handoffs",
    ]
    for team, handoff in run.team_handoffs.items():
        sections.extend(["", f"### {team}", "```text", handoff, "```"])
    return "\n".join(sections).rstrip() + "\n"
