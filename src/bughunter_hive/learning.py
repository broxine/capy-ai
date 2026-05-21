from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .audit import AuditLogger, utc_now

VERDICTS = {"confirmed", "false_positive", "weak_signal", "needs_followup"}


@dataclass
class FeedbackItem:
    canonical_key: str
    verdict: str
    notes: str


@dataclass
class ClusterStats:
    cluster: str
    total: int
    confirmed: int
    false_positive: int
    weak_signal: int
    needs_followup: int
    confirmation_rate: float


@dataclass
class Recommendation:
    subject: str
    action: str
    rationale: str


@dataclass
class LearningBundle:
    program_slug: str
    generated_at: str
    source_triage_path: str
    feedback_path: str
    outcomes_recorded: list[FeedbackItem]
    cluster_stats: list[ClusterStats]
    skill_recommendations: list[Recommendation]
    taxonomy_recommendations: list[Recommendation]


def create_feedback_template(*, repo_root: Path, triage_path: Path) -> Path:
    payload = json.loads(triage_path.read_text(encoding="utf-8"))
    template = {
        "program_slug": payload["program_slug"],
        "outcomes": [
            {"canonical_key": item["canonical_key"], "verdict": "needs_followup", "notes": ""}
            for item in payload.get("findings", [])
        ],
    }
    output_dir = repo_root / "audit" / "feedback-templates"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{payload['program_slug']}-phase7-feedback-template.json"
    output_path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    return output_path


def run_learning_loop(
    *,
    repo_root: Path,
    triage_path: Path,
    feedback_path: Path,
    audit_log_path: Path,
) -> Path:
    triage_payload = json.loads(triage_path.read_text(encoding="utf-8"))
    feedback_payload = json.loads(feedback_path.read_text(encoding="utf-8"))
    program_slug = triage_payload["program_slug"]
    audit = AuditLogger(audit_log_path)
    audit.log("learning.started", {"program_slug": program_slug, "triage_path": str(triage_path), "feedback_path": str(feedback_path)})

    outcomes = _normalize_outcomes(feedback_payload.get("outcomes", []))
    _append_outcomes_ledger(repo_root, program_slug, triage_payload, outcomes)
    stats = _aggregate_cluster_stats(repo_root)
    skill_recommendations = _skill_recommendations(stats)
    taxonomy_recommendations = _taxonomy_recommendations(stats)

    bundle = LearningBundle(
        program_slug=program_slug,
        generated_at=utc_now(),
        source_triage_path=str(triage_path),
        feedback_path=str(feedback_path),
        outcomes_recorded=outcomes,
        cluster_stats=stats,
        skill_recommendations=skill_recommendations,
        taxonomy_recommendations=taxonomy_recommendations,
    )

    output_dir = repo_root / "audit" / "learning"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{program_slug}-phase7-learning.json"
    output_path.write_text(json.dumps(asdict(bundle), indent=2) + "\n", encoding="utf-8")

    rec_dir = repo_root / "audit" / "learning-recommendations"
    rec_dir.mkdir(parents=True, exist_ok=True)
    rec_dir.joinpath(f"{program_slug}-skills.md").write_text(_render_recommendations("Skill recommendations", skill_recommendations), encoding="utf-8")
    rec_dir.joinpath(f"{program_slug}-taxonomy.md").write_text(_render_recommendations("Taxonomy recommendations", taxonomy_recommendations), encoding="utf-8")

    playbook_path = repo_root / "knowledge" / "wiki" / "playbooks" / f"{program_slug}-phase7-learning.md"
    playbook_path.parent.mkdir(parents=True, exist_ok=True)
    playbook_path.write_text(_render_learning_markdown(bundle), encoding="utf-8")

    audit.log("learning.completed", {"program_slug": program_slug, "output_path": str(output_path)})
    return output_path


def _normalize_outcomes(items: list[dict]) -> list[FeedbackItem]:
    normalized: list[FeedbackItem] = []
    for item in items:
        verdict = item.get("verdict", "needs_followup")
        if verdict not in VERDICTS:
            raise ValueError(f"unsupported verdict: {verdict}")
        normalized.append(
            FeedbackItem(
                canonical_key=item["canonical_key"],
                verdict=verdict,
                notes=item.get("notes", ""),
            )
        )
    return normalized


def _append_outcomes_ledger(repo_root: Path, program_slug: str, triage_payload: dict, outcomes: list[FeedbackItem]) -> None:
    index = {item["canonical_key"]: item for item in triage_payload.get("findings", [])}
    ledger_path = repo_root / "knowledge" / "feedback" / "outcomes.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as handle:
        for outcome in outcomes:
            finding = index.get(outcome.canonical_key, {})
            handle.write(
                json.dumps(
                    {
                        "ts": utc_now(),
                        "program_slug": program_slug,
                        "canonical_key": outcome.canonical_key,
                        "cluster": finding.get("cluster", "unknown"),
                        "severity": finding.get("severity", "unknown"),
                        "verdict": outcome.verdict,
                        "notes": outcome.notes,
                    },
                    sort_keys=True,
                )
                + "\n"
            )


def _aggregate_cluster_stats(repo_root: Path) -> list[ClusterStats]:
    ledger_path = repo_root / "knowledge" / "feedback" / "outcomes.jsonl"
    if not ledger_path.exists():
        return []
    raw = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    grouped: dict[str, list[dict]] = {}
    for item in raw:
        grouped.setdefault(item["cluster"], []).append(item)
    stats: list[ClusterStats] = []
    for cluster, items in sorted(grouped.items()):
        total = len(items)
        confirmed = sum(1 for item in items if item["verdict"] == "confirmed")
        false_positive = sum(1 for item in items if item["verdict"] == "false_positive")
        weak_signal = sum(1 for item in items if item["verdict"] == "weak_signal")
        needs_followup = sum(1 for item in items if item["verdict"] == "needs_followup")
        confirmation_rate = confirmed / total if total else 0.0
        stats.append(
            ClusterStats(
                cluster=cluster,
                total=total,
                confirmed=confirmed,
                false_positive=false_positive,
                weak_signal=weak_signal,
                needs_followup=needs_followup,
                confirmation_rate=round(confirmation_rate, 3),
            )
        )
    return stats


def _skill_recommendations(stats: list[ClusterStats]) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    for stat in stats:
        if stat.confirmation_rate >= 0.5 and stat.confirmed >= 1:
            recommendations.append(
                Recommendation(
                    subject=f"cluster:{stat.cluster}",
                    action="expand skill checklist",
                    rationale=f"{stat.cluster} confirms often enough ({stat.confirmation_rate}) to justify a deeper reusable skill path.",
                )
            )
        if stat.false_positive >= stat.confirmed + 1:
            recommendations.append(
                Recommendation(
                    subject=f"cluster:{stat.cluster}",
                    action="tighten heuristics",
                    rationale=f"{stat.cluster} is producing too many false positives ({stat.false_positive}/{stat.total}).",
                )
            )
    return recommendations


def _taxonomy_recommendations(stats: list[ClusterStats]) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    for stat in stats:
        if stat.confirmation_rate >= 0.5 and stat.total >= 2:
            recommendations.append(
                Recommendation(
                    subject=f"cluster:{stat.cluster}",
                    action="increase category weight",
                    rationale=f"Historical confirmation rate {stat.confirmation_rate} suggests this cluster deserves stronger prioritization.",
                )
            )
        if stat.false_positive >= 2:
            recommendations.append(
                Recommendation(
                    subject=f"cluster:{stat.cluster}",
                    action="lower category weight or require extra evidence",
                    rationale=f"Repeated false positives indicate the current scoring is too generous.",
                )
            )
    return recommendations


def _render_recommendations(title: str, recommendations: list[Recommendation]) -> str:
    lines = [f"# {title}", ""]
    if not recommendations:
        lines.append("- none")
    else:
        for item in recommendations:
            lines.extend([f"- `{item.subject}` → **{item.action}**: {item.rationale}"])
    return "\n".join(lines).rstrip() + "\n"


def _render_learning_markdown(bundle: LearningBundle) -> str:
    lines = [
        f"# Phase 7 learning loop for {bundle.program_slug}",
        "",
        f"- generated-at: `{bundle.generated_at}`",
        f"- source-triage: `{bundle.source_triage_path}`",
        f"- feedback-path: `{bundle.feedback_path}`",
        "",
        "## Outcomes recorded",
    ]
    for outcome in bundle.outcomes_recorded:
        lines.extend([f"- `{outcome.canonical_key}` → `{outcome.verdict}` ({outcome.notes or 'no notes'})"])
    lines.extend(["", "## Cluster stats"])
    for stat in bundle.cluster_stats:
        lines.extend([f"- `{stat.cluster}` total={stat.total} confirmed={stat.confirmed} false_positive={stat.false_positive} rate={stat.confirmation_rate}"])
    lines.extend(["", "## Skill recommendations"])
    for item in bundle.skill_recommendations or [Recommendation("none", "none", "none")]:
        if item.subject == "none":
            lines.append("- none")
        else:
            lines.append(f"- `{item.subject}` → **{item.action}**: {item.rationale}")
    lines.extend(["", "## Taxonomy recommendations"])
    for item in bundle.taxonomy_recommendations or [Recommendation("none", "none", "none")]:
        if item.subject == "none":
            lines.append("- none")
        else:
            lines.append(f"- `{item.subject}` → **{item.action}**: {item.rationale}")
    return "\n".join(lines).rstrip() + "\n"
