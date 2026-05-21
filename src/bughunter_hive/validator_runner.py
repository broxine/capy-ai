from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .audit import AuditLogger, utc_now
from .killswitch import KillSwitch
from .policy import ActionClass, ensure_action_allowed, ensure_target_allowed

USER_AGENT = "bughunter-hive/0.1 safe-validator"


class _HTMLStatsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms = 0
        self.links = 0
        self.scripts = 0
        self.inline_handlers = 0
        self.inputs = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value for key, value in attrs}
        if tag == "form":
            self.forms += 1
        if tag == "a":
            self.links += 1
        if tag == "script":
            self.scripts += 1
        if tag == "input":
            self.inputs += 1
        if any(key.startswith("on") for key in attrs_dict):
            self.inline_handlers += 1


@dataclass
class ValidationExecution:
    rank: int
    bug_class_id: str
    title: str
    target_url: str
    executed_at: str
    observations: list[str]
    request_artifact: str
    note_artifact: str
    summary: str


@dataclass
class ValidationExecutionBundle:
    program_slug: str
    generated_at: str
    source_bundle_path: str
    executions: list[ValidationExecution]


def execute_validation_bundle(
    *,
    repo_root: Path,
    bundle_path: Path,
    audit_log_path: Path,
    kill_switch_path: Path,
    allow_private_targets: bool = False,
    timeout: int = 10,
) -> Path:
    kill_switch = KillSwitch(kill_switch_path)
    kill_switch.assert_clear()
    ensure_action_allowed(ActionClass.SAFE_VALIDATION)

    bundle_payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    program_slug = bundle_payload["program_slug"]
    tasks = bundle_payload.get("tasks", [])
    audit = AuditLogger(audit_log_path)
    audit.log("validator.started", {"program_slug": program_slug, "bundle_path": str(bundle_path)})

    executions: list[ValidationExecution] = []
    for task in tasks:
        target_url = (task.get("target_urls") or [None])[0]
        if not target_url:
            continue
        ensure_target_allowed(target_url, _scope_domains(repo_root, task), allow_private_targets=allow_private_targets)
        http_payload = _fetch(target_url, timeout=timeout)
        note_artifact, request_artifact, observations = _write_task_artifacts(
            repo_root=repo_root,
            program_slug=program_slug,
            task=task,
            target_url=target_url,
            http_payload=http_payload,
        )
        summary = _summary_line(task["bug_class_id"], observations)
        execution = ValidationExecution(
            rank=task["rank"],
            bug_class_id=task["bug_class_id"],
            title=task["title"],
            target_url=target_url,
            executed_at=utc_now(),
            observations=observations,
            request_artifact=request_artifact,
            note_artifact=note_artifact,
            summary=summary,
        )
        executions.append(execution)
        audit.log(
            "validator.task_completed",
            {
                "program_slug": program_slug,
                "bug_class_id": execution.bug_class_id,
                "target_url": execution.target_url,
                "note_artifact": execution.note_artifact,
                "request_artifact": execution.request_artifact,
            },
        )

    result = ValidationExecutionBundle(
        program_slug=program_slug,
        generated_at=utc_now(),
        source_bundle_path=str(bundle_path),
        executions=executions,
    )

    result_dir = repo_root / "audit" / "validation-runs"
    result_dir.mkdir(parents=True, exist_ok=True)
    result_path = result_dir / f"{program_slug}-phase3-validation-run.json"
    result_path.write_text(json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8")

    playbook_path = repo_root / "knowledge" / "wiki" / "playbooks" / f"{program_slug}-phase3-validation-run.md"
    playbook_path.parent.mkdir(parents=True, exist_ok=True)
    playbook_path.write_text(_render_execution_markdown(result), encoding="utf-8")

    audit.log(
        "validator.completed",
        {"program_slug": program_slug, "result_path": str(result_path), "executions": len(executions)},
    )
    return result_path


def _scope_domains(repo_root: Path, task: dict) -> list[str]:
    for item in task.get("evidence_inputs", []):
        if item.startswith("knowledge/programs/"):
            path = repo_root / item
            if path.exists():
                payload = json.loads(path.read_text(encoding="utf-8"))
                return payload.get("scope_domains", [])
    return []


def _fetch(url: str, timeout: int) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(131072)
            return {
                "status": response.getcode(),
                "headers": dict(response.headers.items()),
                "body": body.decode("utf-8", "replace"),
            }
    except HTTPError as exc:
        return {
            "status": exc.code,
            "headers": dict(exc.headers.items()),
            "body": exc.read(131072).decode("utf-8", "replace"),
        }
    except URLError as exc:
        return {"status": None, "headers": {}, "body": str(exc)}


def _write_task_artifacts(
    *,
    repo_root: Path,
    program_slug: str,
    task: dict,
    target_url: str,
    http_payload: dict,
) -> tuple[str, str, list[str]]:
    notes_dir = repo_root / "audit" / "validation-notes"
    requests_dir = repo_root / "audit" / "validation-requests"
    notes_dir.mkdir(parents=True, exist_ok=True)
    requests_dir.mkdir(parents=True, exist_ok=True)

    task_slug = task["bug_class_id"]
    request_path = requests_dir / f"{program_slug}-{task_slug}.http"
    request_path.write_text(_render_http_trace(target_url, http_payload), encoding="utf-8")

    observations = _observe(task["bug_class_id"], http_payload)
    note_path = notes_dir / f"{program_slug}-{task_slug}.md"
    note_path.write_text(_render_notes(task, target_url, observations), encoding="utf-8")
    return (
        str(note_path.relative_to(repo_root)),
        str(request_path.relative_to(repo_root)),
        observations,
    )


def _render_http_trace(target_url: str, http_payload: dict) -> str:
    headers = "\n".join(f"{key}: {value}" for key, value in sorted(http_payload["headers"].items()))
    return (
        f"GET {target_url} HTTP/1.1\n"
        f"User-Agent: {USER_AGENT}\n\n"
        f"HTTP status: {http_payload['status']}\n"
        f"{headers}\n\n"
        f"{http_payload['body'][:4000]}\n"
    )


def _render_notes(task: dict, target_url: str, observations: list[str]) -> str:
    safe_check_lines = [f"- {item}" for item in task.get("safe_checks", [])] or ["- none"]
    observation_lines = [f"- {item}" for item in observations] or ["- none"]
    lines = [
        f"# Validation notes for {task['title']}",
        "",
        f"- target: `{target_url}`",
        f"- bug-class-id: `{task['bug_class_id']}`",
        "",
        "## Safe checks requested",
        *safe_check_lines,
        "",
        "## Observations",
        *observation_lines,
        "",
        "## Caveman handoff",
        "```text",
        task["caveman_handoff"],
        "```",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _observe(bug_class_id: str, http_payload: dict) -> list[str]:
    body = http_payload["body"]
    headers = {key.lower(): value for key, value in http_payload["headers"].items()}
    parser = _HTMLStatsParser()
    try:
        parser.feed(body)
    except Exception:
        pass

    observations = [
        f"http status {http_payload['status']}",
        f"forms={parser.forms} links={parser.links} scripts={parser.scripts} inputs={parser.inputs}",
    ]
    if "content-security-policy" not in headers:
        observations.append("csp missing on observed response")
    if "set-cookie" in headers:
        observations.append(f"set-cookie present: {headers['set-cookie'][:120]}")

    identifiers = _extract_identifier_candidates(body)
    if identifiers:
        observations.append(f"identifier-like tokens observed: {', '.join(identifiers[:5])}")

    lowered = body.lower()
    if bug_class_id == "web2-auth-session":
        for keyword in ("login", "oauth", "callback", "session", "signin"):
            if keyword in lowered:
                observations.append(f"auth keyword present: {keyword}")
    elif bug_class_id == "web2-idor-access-control":
        if identifiers:
            observations.append("access-control review should compare identifier exposure paths")
    elif bug_class_id == "web2-client-sink":
        if parser.inline_handlers:
            observations.append(f"inline event handlers observed: {parser.inline_handlers}")
    elif bug_class_id == "web3-signature-domain":
        for keyword in ("wallet", "sign", "permit", "eip-712", "signature"):
            if keyword in lowered:
                observations.append(f"signing keyword present: {keyword}")
    elif bug_class_id == "web3-upgrade-initialization":
        for keyword in ("proxy", "upgrade", "implementation", "admin"):
            if keyword in lowered:
                observations.append(f"upgrade keyword present: {keyword}")
    elif bug_class_id == "web3-accounting-oracle":
        for keyword in ("oracle", "price", "vault", "pool", "staking"):
            if keyword in lowered:
                observations.append(f"accounting keyword present: {keyword}")
    return observations


def _extract_identifier_candidates(body: str) -> list[str]:
    patterns = [
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        r"\buser[_-]id\b",
        r"\baccount[_-]id\b",
        r"/users/\d+",
        r"/accounts/\d+",
    ]
    results: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, body, re.IGNORECASE):
            if match not in results:
                results.append(match)
    return results


def _summary_line(bug_class_id: str, observations: list[str]) -> str:
    first = observations[0] if observations else "no observations"
    return (
        f"fact: {bug_class_id} inspected, {first}\n"
        "impact: evidence pack refreshed without changing target state\n"
        "next: human or browser-safe validator reviews artifacts"
    )


def _render_execution_markdown(result: ValidationExecutionBundle) -> str:
    lines = [
        f"# Phase 3 validation run for {result.program_slug}",
        "",
        f"- generated-at: `{result.generated_at}`",
        f"- source-bundle: `{result.source_bundle_path}`",
        "",
    ]
    for execution in result.executions:
        observation_lines = [f"- {item}" for item in execution.observations] or ["- none"]
        lines.extend(
            [
                f"## {execution.rank}. {execution.title}",
                "",
                f"- target-url: `{execution.target_url}`",
                f"- request-artifact: `{execution.request_artifact}`",
                f"- note-artifact: `{execution.note_artifact}`",
                "",
                "### Observations",
                *observation_lines,
                "",
                "### Caveman execution summary",
                "```text",
                execution.summary,
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
