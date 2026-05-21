from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .audit import AuditLogger, utc_now
from .scoring_policy import ScoringPolicy, load_scoring_policy


CLUSTER_CATEGORY_MAP = {
    "auth-session": ["login-surface", "callback-parameter"],
    "client-injection": ["dom-sink"],
    "wallet-signature": ["wallet-signature"],
}

CLUSTER_SKILL_MAP = {
    "auth-session": "skills/bughunter-safe-validation/SKILL.md",
    "client-injection": "skills/bughunter-safe-validation/SKILL.md",
    "wallet-signature": "skills/bughunter-safe-validation/SKILL.md",
}


@dataclass
class ConfigChange:
    field: str
    key: str
    old_value: int
    new_value: int
    rationale: str


@dataclass
class SkillChange:
    path: str
    cluster: str
    action: str
    rationale: str


@dataclass
class AutoPatchPlan:
    program_slug: str
    generated_at: str
    source_learning_path: str
    config_changes: list[ConfigChange]
    skill_changes: list[SkillChange]
    proposed_scoring_policy_path: str


def plan_autopatches(
    *,
    repo_root: Path,
    learning_path: Path,
    audit_log_path: Path,
) -> Path:
    payload = json.loads(learning_path.read_text(encoding="utf-8"))
    policy = load_scoring_policy(repo_root)
    audit = AuditLogger(audit_log_path)
    program_slug = payload["program_slug"]
    audit.log("autopatch.started", {"program_slug": program_slug, "learning_path": str(learning_path)})

    config_changes, proposed_policy = _propose_config_changes(policy, payload.get("taxonomy_recommendations", []))
    skill_changes = _propose_skill_changes(payload.get("skill_recommendations", []))

    proposed_dir = repo_root / "audit" / "autopatch-configs"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    proposed_policy_path = proposed_dir / f"{program_slug}-scoring-policy.proposed.json"
    proposed_policy_path.write_text(json.dumps(proposed_policy, indent=2) + "\n", encoding="utf-8")

    plan = AutoPatchPlan(
        program_slug=program_slug,
        generated_at=utc_now(),
        source_learning_path=str(learning_path),
        config_changes=config_changes,
        skill_changes=skill_changes,
        proposed_scoring_policy_path=str(proposed_policy_path.relative_to(repo_root)),
    )

    output_dir = repo_root / "audit" / "autopatch-plans"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{program_slug}-phase8-autopatch.json"
    output_path.write_text(json.dumps(asdict(plan), indent=2) + "\n", encoding="utf-8")

    playbook_path = repo_root / "knowledge" / "wiki" / "playbooks" / f"{program_slug}-phase8-autopatch.md"
    playbook_path.parent.mkdir(parents=True, exist_ok=True)
    playbook_path.write_text(_render_autopatch_markdown(plan), encoding="utf-8")

    audit.log("autopatch.completed", {"program_slug": program_slug, "output_path": str(output_path)})
    return output_path


def _propose_config_changes(policy: ScoringPolicy, recommendations: list[dict]) -> tuple[list[ConfigChange], dict]:
    proposed = {
        "category_cluster": dict(policy.category_cluster),
        "category_weight": dict(policy.category_weight),
        "confidence_weight": dict(policy.confidence_weight),
        "severity_thresholds": [[threshold, label] for threshold, label in policy.severity_thresholds],
    }
    changes: list[ConfigChange] = []
    for item in recommendations:
        subject = item["subject"]
        if not subject.startswith("cluster:"):
            continue
        cluster = subject.split(":", 1)[1]
        delta = 1 if item["action"] == "increase category weight" else -1
        for category in CLUSTER_CATEGORY_MAP.get(cluster, []):
            old_value = proposed["category_weight"].get(category, 3)
            new_value = max(1, old_value + delta)
            if new_value == old_value:
                continue
            proposed["category_weight"][category] = new_value
            changes.append(
                ConfigChange(
                    field="category_weight",
                    key=category,
                    old_value=old_value,
                    new_value=new_value,
                    rationale=item["rationale"],
                )
            )
    return changes, proposed


def _propose_skill_changes(recommendations: list[dict]) -> list[SkillChange]:
    changes: list[SkillChange] = []
    for item in recommendations:
        subject = item["subject"]
        if not subject.startswith("cluster:"):
            continue
        cluster = subject.split(":", 1)[1]
        path = CLUSTER_SKILL_MAP.get(cluster)
        if not path:
            continue
        changes.append(
            SkillChange(
                path=path,
                cluster=cluster,
                action=item["action"],
                rationale=item["rationale"],
            )
        )
    return changes


def _render_autopatch_markdown(plan: AutoPatchPlan) -> str:
    lines = [
        f"# Phase 8 autopatch plan for {plan.program_slug}",
        "",
        f"- generated-at: `{plan.generated_at}`",
        f"- source-learning: `{plan.source_learning_path}`",
        f"- proposed-policy: `{plan.proposed_scoring_policy_path}`",
        "",
        "## Config changes",
    ]
    for change in plan.config_changes or [None]:
        if change is None:
            lines.append("- none")
        else:
            lines.append(f"- `{change.field}.{change.key}`: `{change.old_value}` → `{change.new_value}` — {change.rationale}")
    lines.extend(["", "## Skill changes"])
    for change in plan.skill_changes or [None]:
        if change is None:
            lines.append("- none")
        else:
            lines.append(f"- `{change.path}` ({change.cluster}) → **{change.action}**: {change.rationale}")
    return "\n".join(lines).rstrip() + "\n"
