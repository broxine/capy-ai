from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .audit import AuditLogger, utc_now


@dataclass
class FindingCandidate:
    rank: int
    category: str
    title: str
    target_url: str
    confidence: str
    rationale: str
    evidence_paths: list[str]
    next_safe_step: str
    caveman_handoff: str


@dataclass
class BrowserReviewBundle:
    program_slug: str
    generated_at: str
    source_browser_run_path: str
    candidates: list[FindingCandidate]


def review_browser_validation(
    *,
    repo_root: Path,
    browser_validation_path: Path,
    audit_log_path: Path,
) -> Path:
    payload = json.loads(browser_validation_path.read_text(encoding="utf-8"))
    program_slug = payload["program_slug"]
    audit = AuditLogger(audit_log_path)
    audit.log(
        "browser_review.started",
        {"program_slug": program_slug, "browser_validation_path": str(browser_validation_path)},
    )

    candidates: list[FindingCandidate] = []
    for execution in payload.get("executions", []):
        dom_path = repo_root / execution["dom_artifact"]
        note_path = repo_root / execution["screenshot_artifact"]
        dom_text = dom_path.read_text(encoding="utf-8", errors="replace") if dom_path.exists() else ""
        candidates.extend(_derive_candidates(execution, dom_text, [execution["dom_artifact"], execution["screenshot_artifact"]]))

    bundle = BrowserReviewBundle(
        program_slug=program_slug,
        generated_at=utc_now(),
        source_browser_run_path=str(browser_validation_path),
        candidates=candidates,
    )

    output_dir = repo_root / "audit" / "review-candidates"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{program_slug}-phase5-review.json"
    output_path.write_text(json.dumps(asdict(bundle), indent=2) + "\n", encoding="utf-8")

    playbook_path = repo_root / "knowledge" / "wiki" / "playbooks" / f"{program_slug}-phase5-review.md"
    playbook_path.parent.mkdir(parents=True, exist_ok=True)
    playbook_path.write_text(_render_review_markdown(bundle), encoding="utf-8")

    audit.log(
        "browser_review.completed",
        {"program_slug": program_slug, "output_path": str(output_path), "candidate_count": len(candidates)},
    )
    return output_path


def _derive_candidates(execution: dict, dom_text: str, evidence_paths: list[str]) -> list[FindingCandidate]:
    candidates: list[FindingCandidate] = []
    lowered = dom_text.lower()
    target_url = execution["target_url"]

    def add(category: str, title: str, confidence: str, rationale: str, next_step: str) -> None:
        candidates.append(
            FindingCandidate(
                rank=len(candidates) + 1,
                category=category,
                title=title,
                target_url=target_url,
                confidence=confidence,
                rationale=rationale,
                evidence_paths=evidence_paths,
                next_safe_step=next_step,
                caveman_handoff=(
                    f"fact: {category} cues on {target_url}\n"
                    f"impact: {title.lower()}\n"
                    f"next: {next_step}"
                ),
            )
        )

    forms = len(re.findall(r"<form\b", dom_text, re.IGNORECASE))
    if forms > 0 and any(keyword in lowered for keyword in ("login", "signin", "oauth", "password", "email")):
        add(
            "login-surface",
            "Login or auth surface worth callback/session review",
            "medium",
            "Rendered DOM exposes form elements plus auth-related keywords.",
            "map form actions, callback URLs, and state/redirect params without submitting credentials",
        )

    if any(keyword in lowered for keyword in ("redirect_uri", "callback", "state=", "code=", "oauth")):
        add(
            "callback-parameter",
            "OAuth callback or redirect parameters visible",
            "medium",
            "DOM contains callback-style parameters or OAuth markers that often gate session-binding bugs.",
            "enumerate callback params and compare state/code handling in read-only browser flows",
        )

    if any(keyword in lowered for keyword in ("innerhtml", "document.write", "postmessage", "addeventlistener(\"message", "addeventlistener('message")):
        add(
            "dom-sink",
            "Potential DOM sink or postMessage surface",
            "high",
            "DOM or inline scripts expose common client-side sink patterns.",
            "trace sink sources and trusted origins before any payload testing",
        )

    if re.search(r"\son[a-z]+=", dom_text, re.IGNORECASE):
        add(
            "dom-sink",
            "Inline event-handler surface present",
            "medium",
            "Rendered HTML contains inline event handlers, which can widen client-side sink review.",
            "inventory inline handlers and map user-controlled inputs that reach them",
        )

    if any(keyword in lowered for keyword in ("wallet", "metamask", "signature", "sign typed data", "permit", "eip-712")):
        add(
            "wallet-signature",
            "Wallet or signature flow visible in rendered surface",
            "medium",
            "Rendered DOM contains wallet/signature keywords associated with domain separation and replay review.",
            "map signing prompts, typed-data labels, and nonce/domain cues from UI and DOM only",
        )

    return candidates


def _render_review_markdown(bundle: BrowserReviewBundle) -> str:
    lines = [
        f"# Phase 5 browser review for {bundle.program_slug}",
        "",
        f"- generated-at: `{bundle.generated_at}`",
        f"- source-browser-run: `{bundle.source_browser_run_path}`",
        "",
    ]
    for candidate in bundle.candidates:
        evidence_lines = [f"- `{item}`" for item in candidate.evidence_paths] or ["- none"]
        lines.extend(
            [
                f"## {candidate.rank}. {candidate.title}",
                "",
                f"- category: `{candidate.category}`",
                f"- confidence: `{candidate.confidence}`",
                f"- target-url: `{candidate.target_url}`",
                "",
                candidate.rationale,
                "",
                "### Evidence paths",
                *evidence_lines,
                "",
                f"### Next safe step\n- {candidate.next_safe_step}",
                "",
                "### Caveman handoff",
                "```text",
                candidate.caveman_handoff,
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
