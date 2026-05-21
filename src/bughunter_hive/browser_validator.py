from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .audit import AuditLogger, utc_now
from .killswitch import KillSwitch
from .policy import ActionClass, ensure_action_allowed


@dataclass
class BrowserExecution:
    rank: int
    title: str
    bug_class_id: str
    target_url: str
    screenshot_artifact: str
    dom_artifact: str
    observations: list[str]
    summary: str


@dataclass
class BrowserValidationBundle:
    program_slug: str
    generated_at: str
    source_validation_run_path: str
    browser_binary: str
    executions: list[BrowserExecution]


def run_browser_validation(
    *,
    repo_root: Path,
    validation_run_path: Path,
    audit_log_path: Path,
    kill_switch_path: Path,
    timeout: int = 15,
) -> Path:
    kill_switch = KillSwitch(kill_switch_path)
    kill_switch.assert_clear()
    ensure_action_allowed(ActionClass.SAFE_VALIDATION)

    browser_binary = _find_browser_binary()
    payload = json.loads(validation_run_path.read_text(encoding="utf-8"))
    program_slug = payload["program_slug"]
    audit = AuditLogger(audit_log_path)
    audit.log(
        "browser_validator.started",
        {"program_slug": program_slug, "validation_run_path": str(validation_run_path), "browser_binary": browser_binary},
    )

    screenshot_dir = repo_root / "audit" / "browser-screenshots"
    dom_dir = repo_root / "audit" / "browser-dom"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    dom_dir.mkdir(parents=True, exist_ok=True)

    executions: list[BrowserExecution] = []
    for execution in payload.get("executions", []):
        screenshot_path = screenshot_dir / f"{program_slug}-{execution['bug_class_id']}.png"
        dom_path = dom_dir / f"{program_slug}-{execution['bug_class_id']}.html"
        _capture(browser_binary, execution["target_url"], screenshot_path, dom_path, timeout)
        dom_text = dom_path.read_text(encoding="utf-8", errors="replace")
        observations = _observe_browser_dom(dom_text)
        summary = _browser_summary(execution["bug_class_id"], observations)
        executions.append(
            BrowserExecution(
                rank=execution["rank"],
                title=execution["title"],
                bug_class_id=execution["bug_class_id"],
                target_url=execution["target_url"],
                screenshot_artifact=str(screenshot_path.relative_to(repo_root)),
                dom_artifact=str(dom_path.relative_to(repo_root)),
                observations=observations,
                summary=summary,
            )
        )
        audit.log(
            "browser_validator.task_completed",
            {
                "program_slug": program_slug,
                "bug_class_id": execution["bug_class_id"],
                "target_url": execution["target_url"],
                "screenshot_artifact": str(screenshot_path.relative_to(repo_root)),
                "dom_artifact": str(dom_path.relative_to(repo_root)),
            },
        )

    result = BrowserValidationBundle(
        program_slug=program_slug,
        generated_at=utc_now(),
        source_validation_run_path=str(validation_run_path),
        browser_binary=browser_binary,
        executions=executions,
    )

    bundle_dir = repo_root / "audit" / "browser-validation-runs"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = bundle_dir / f"{program_slug}-phase4-browser-validation.json"
    bundle_path.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")

    playbook_path = repo_root / "knowledge" / "wiki" / "playbooks" / f"{program_slug}-phase4-browser-validation.md"
    playbook_path.parent.mkdir(parents=True, exist_ok=True)
    playbook_path.write_text(_render_browser_markdown(result), encoding="utf-8")

    audit.log(
        "browser_validator.completed",
        {"program_slug": program_slug, "bundle_path": str(bundle_path), "executions": len(executions)},
    )
    return bundle_path


def _find_browser_binary() -> str:
    for candidate in ("google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise FileNotFoundError("no supported browser binary found")


def _capture(browser_binary: str, target_url: str, screenshot_path: Path, dom_path: Path, timeout: int) -> None:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    dom_path.parent.mkdir(parents=True, exist_ok=True)
    dom_output = subprocess.run(
        [
            browser_binary,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--dump-dom",
            target_url,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    dom_path.write_text(dom_output.stdout, encoding="utf-8")
    subprocess.run(
        [
            browser_binary,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--hide-scrollbars",
            "--window-size=1440,1080",
            f"--screenshot={screenshot_path}",
            target_url,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )


def _observe_browser_dom(dom_text: str) -> list[str]:
    observations: list[str] = []
    title_match = re.search(r"<title>(.*?)</title>", dom_text, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = re.sub(r"\s+", " ", title_match.group(1)).strip()
        observations.append(f"title={title}")
    forms = len(re.findall(r"<form\b", dom_text, re.IGNORECASE))
    scripts = len(re.findall(r"<script\b", dom_text, re.IGNORECASE))
    links = len(re.findall(r"<a\b", dom_text, re.IGNORECASE))
    inline_handlers = len(re.findall(r"\son[a-z]+=", dom_text, re.IGNORECASE))
    observations.append(f"forms={forms} scripts={scripts} links={links} inline_handlers={inline_handlers}")
    if "content-security-policy" not in dom_text.lower():
        observations.append("dom dump does not reveal CSP meta tag")
    for keyword in ("oauth", "login", "wallet", "permit", "callback", "session"):
        if keyword in dom_text.lower():
            observations.append(f"dom keyword present: {keyword}")
    return observations


def _browser_summary(bug_class_id: str, observations: list[str]) -> str:
    lead = observations[0] if observations else "no browser observations"
    return (
        f"fact: browser check for {bug_class_id}, {lead}\n"
        "impact: visual/DOM evidence added without live exploitation\n"
        "next: reviewer inspects screenshot and dom diff before stronger testing"
    )


def _render_browser_markdown(result: BrowserValidationBundle) -> str:
    lines = [
        f"# Phase 4 browser validation for {result.program_slug}",
        "",
        f"- generated-at: `{result.generated_at}`",
        f"- source-validation-run: `{result.source_validation_run_path}`",
        f"- browser-binary: `{result.browser_binary}`",
        "",
    ]
    for execution in result.executions:
        obs_lines = [f"- {item}" for item in execution.observations] or ["- none"]
        lines.extend(
            [
                f"## {execution.rank}. {execution.title}",
                "",
                f"- target-url: `{execution.target_url}`",
                f"- screenshot: `{execution.screenshot_artifact}`",
                f"- dom: `{execution.dom_artifact}`",
                "",
                "### Browser observations",
                *obs_lines,
                "",
                "### Caveman browser summary",
                "```text",
                execution.summary,
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
