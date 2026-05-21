from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .audit import utc_now
from .programs import ProgramProfile
from .taxonomy import BUG_CLASSES, BugClass


@dataclass
class CampaignHypothesis:
    rank: int
    bug_class_id: str
    title: str
    score: int
    rationale: str
    evidence_targets: list[str]
    safe_checks: list[str]
    caveman_handoff: str


@dataclass
class CampaignPlan:
    program_slug: str
    generated_at: str
    hypotheses: list[CampaignHypothesis]


def build_campaign_plan(repo_root: Path, profile: ProgramProfile, limit: int = 5) -> CampaignPlan:
    scored: list[tuple[int, BugClass, list[str]]] = []
    haystack = " ".join(
        [
            profile.name,
            profile.platform,
            *(profile.scope_domains or []),
            *(profile.assets or []),
            *(profile.tags or []),
            *(profile.notes or []),
        ]
    ).lower()

    for bug_class in BUG_CLASSES:
        score = 0
        evidence: list[str] = []

        if profile.platform in bug_class.platforms:
            score += 4
            evidence.append(f"platform-fit:{profile.platform}")
        elif profile.platform == "hybrid" and "hybrid" in bug_class.platforms:
            score += 4
            evidence.append("platform-fit:hybrid")

        for trigger in bug_class.triggers:
            if trigger in haystack:
                score += 2
                evidence.append(f"trigger:{trigger}")

        if any(keyword in haystack for keyword in ("public-api", "graphql", "admin")) and "web2" in bug_class.id:
            score += 1
        if any(keyword in haystack for keyword in ("bridge", "vault", "staking", "oracle")) and "web3" in bug_class.id:
            score += 1

        if score > 0:
            scored.append((score, bug_class, sorted(set(evidence))))

    scored.sort(key=lambda item: (-item[0], item[1].id))

    hypotheses: list[CampaignHypothesis] = []
    for index, (score, bug_class, evidence) in enumerate(scored[:limit], start=1):
        hypotheses.append(
            CampaignHypothesis(
                rank=index,
                bug_class_id=bug_class.id,
                title=bug_class.name,
                score=score,
                rationale=bug_class.rationale,
                evidence_targets=evidence,
                safe_checks=list(bug_class.safe_checks),
                caveman_handoff=_caveman_handoff(bug_class, evidence),
            )
        )

    plan = CampaignPlan(
        program_slug=profile.slug,
        generated_at=utc_now(),
        hypotheses=hypotheses,
    )

    plan_dir = repo_root / "audit" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    json_path = plan_dir / f"{profile.slug}-phase1-plan.json"
    json_path.write_text(json.dumps(asdict(plan), indent=2) + "\n", encoding="utf-8")

    wiki_dir = repo_root / "knowledge" / "wiki" / "playbooks"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    wiki_path = wiki_dir / f"{profile.slug}-phase1-plan.md"
    wiki_path.write_text(_render_plan_markdown(profile, plan), encoding="utf-8")

    return plan


def _caveman_handoff(bug_class: BugClass, evidence: list[str]) -> str:
    trigger_text = ", ".join(evidence[:3]) or "generic-signal"
    return (
        f"fact: {trigger_text}\n"
        f"impact: {bug_class.name.lower()} worth first-pass validation\n"
        f"next: run safe checks only"
    )


def _render_plan_markdown(profile: ProgramProfile, plan: CampaignPlan) -> str:
    lines = [
        f"# Phase 1 campaign plan for {profile.name}",
        "",
        f"- generated-at: `{plan.generated_at}`",
        f"- platform: `{profile.platform}`",
        "",
    ]
    for hypothesis in plan.hypotheses:
        lines.extend(
            [
                f"## {hypothesis.rank}. {hypothesis.title}",
                "",
                f"- bug-class-id: `{hypothesis.bug_class_id}`",
                f"- score: `{hypothesis.score}`",
                f"- evidence-targets: {', '.join(hypothesis.evidence_targets) if hypothesis.evidence_targets else 'none'}",
                "",
                hypothesis.rationale,
                "",
                "### Safe checks",
                *(f"- {item}" for item in hypothesis.safe_checks),
                "",
                "### Caveman handoff",
                "```text",
                hypothesis.caveman_handoff,
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
