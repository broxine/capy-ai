from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .audit import AuditLogger, utc_now
from .scoring_policy import ScoringPolicy, load_scoring_policy


@dataclass
class TriageFinding:
    rank: int
    canonical_key: str
    title: str
    target_url: str
    cluster: str
    severity: str
    score: int
    confidence: str
    supporting_categories: list[str]
    evidence_paths: list[str]
    rationale: str
    next_safe_step: str
    disclosure_ready: bool
    caveman_handoff: str


@dataclass
class TriageBundle:
    program_slug: str
    generated_at: str
    source_review_path: str
    findings: list[TriageFinding]


def triage_review_candidates(
    *,
    repo_root: Path,
    review_path: Path,
    audit_log_path: Path,
) -> Path:
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    program_slug = payload["program_slug"]
    policy = load_scoring_policy(repo_root)
    audit = AuditLogger(audit_log_path)
    audit.log("triage.started", {"program_slug": program_slug, "review_path": str(review_path)})

    grouped: dict[tuple[str, str], list[dict]] = {}
    for candidate in payload.get("candidates", []):
        cluster = policy.category_cluster.get(candidate["category"], candidate["category"])
        key = (candidate["target_url"], cluster)
        grouped.setdefault(key, []).append(candidate)

    findings: list[TriageFinding] = []
    for (target_url, cluster), candidates in grouped.items():
        scores = [_score_candidate(item, policy) for item in candidates]
        score = max(scores) + max(0, len(candidates) - 1) * 2
        severity = _severity(score, policy)
        confidence = _confidence(candidates, policy)
        categories = sorted({item["category"] for item in candidates})
        evidence_paths = _unique(item for candidate in candidates for item in candidate.get("evidence_paths", []))
        rationale = " ".join(item["rationale"] for item in candidates)
        next_safe_step = candidates[0]["next_safe_step"]
        disclosure_ready = severity in {"medium", "high"} and len(categories) >= 1
        title = _title_for_cluster(cluster, candidates)
        canonical_key = f"{cluster}:{target_url}"
        findings.append(
            TriageFinding(
                rank=0,
                canonical_key=canonical_key,
                title=title,
                target_url=target_url,
                cluster=cluster,
                severity=severity,
                score=score,
                confidence=confidence,
                supporting_categories=categories,
                evidence_paths=evidence_paths,
                rationale=rationale,
                next_safe_step=next_safe_step,
                disclosure_ready=disclosure_ready,
                caveman_handoff=(
                    f"fact: {cluster} cluster on {target_url}, score {score}\n"
                    f"impact: {severity} triage candidate\n"
                    f"next: {next_safe_step}"
                ),
            )
        )

    findings.sort(key=lambda item: (-item.score, item.title, item.target_url))
    for index, finding in enumerate(findings, start=1):
        finding.rank = index

    bundle = TriageBundle(
        program_slug=program_slug,
        generated_at=utc_now(),
        source_review_path=str(review_path),
        findings=findings,
    )

    output_dir = repo_root / "audit" / "triage"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{program_slug}-phase6-triage.json"
    output_path.write_text(json.dumps(asdict(bundle), indent=2) + "\n", encoding="utf-8")

    playbook_path = repo_root / "knowledge" / "wiki" / "playbooks" / f"{program_slug}-phase6-triage.md"
    playbook_path.parent.mkdir(parents=True, exist_ok=True)
    playbook_path.write_text(_render_triage_markdown(bundle), encoding="utf-8")

    audit.log("triage.completed", {"program_slug": program_slug, "output_path": str(output_path), "finding_count": len(findings)})
    return output_path


def _score_candidate(candidate: dict, policy: ScoringPolicy) -> int:
    return policy.category_weight.get(candidate["category"], 3) + policy.confidence_weight.get(candidate["confidence"], 2)


def _severity(score: int, policy: ScoringPolicy) -> str:
    for threshold, label in policy.severity_thresholds:
        if score >= threshold:
            return label
    return "low"


def _confidence(candidates: list[dict], policy: ScoringPolicy) -> str:
    highest = max(candidates, key=lambda item: policy.confidence_weight.get(item["confidence"], 0))["confidence"]
    return highest


def _title_for_cluster(cluster: str, candidates: list[dict]) -> str:
    if cluster == "auth-session":
        return "Auth/session candidate from browser review"
    if cluster == "client-injection":
        return "Client-side injection candidate from browser review"
    if cluster == "wallet-signature":
        return "Wallet/signature candidate from browser review"
    return candidates[0]["title"]


def _unique(items) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def _render_triage_markdown(bundle: TriageBundle) -> str:
    lines = [
        f"# Phase 6 triage for {bundle.program_slug}",
        "",
        f"- generated-at: `{bundle.generated_at}`",
        f"- source-review: `{bundle.source_review_path}`",
        "",
    ]
    for finding in bundle.findings:
        evidence_lines = [f"- `{item}`" for item in finding.evidence_paths] or ["- none"]
        category_lines = [f"- `{item}`" for item in finding.supporting_categories] or ["- none"]
        lines.extend(
            [
                f"## {finding.rank}. {finding.title}",
                "",
                f"- severity: `{finding.severity}`",
                f"- score: `{finding.score}`",
                f"- confidence: `{finding.confidence}`",
                f"- target-url: `{finding.target_url}`",
                f"- disclosure-ready: `{finding.disclosure_ready}`",
                "",
                "### Supporting categories",
                *category_lines,
                "",
                "### Evidence paths",
                *evidence_lines,
                "",
                finding.rationale,
                "",
                f"### Next safe step\n- {finding.next_safe_step}",
                "",
                "### Caveman handoff",
                "```text",
                finding.caveman_handoff,
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
