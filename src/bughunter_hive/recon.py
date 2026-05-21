from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .audit import AuditLogger, utc_now
from .killswitch import KillSwitch
from .policy import ActionClass, ensure_action_allowed, ensure_target_allowed

USER_AGENT = "bughunter-hive/0.1 passive-recon"


@dataclass
class ReconFinding:
    severity: str
    title: str
    detail: str


@dataclass
class ReconResult:
    program: str
    target: str
    scanned_at: str
    title: str | None
    headers: dict[str, str]
    findings: list[ReconFinding]
    endpoints_checked: list[dict[str, Any]]


def _request(url: str, timeout: int = 10) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(65536)
            return {
                "url": url,
                "status": response.getcode(),
                "headers": dict(response.headers.items()),
                "body": body.decode("utf-8", "replace"),
                "ok": True,
            }
    except HTTPError as exc:
        body = exc.read(65536).decode("utf-8", "replace")
        return {
            "url": url,
            "status": exc.code,
            "headers": dict(exc.headers.items()),
            "body": body,
            "ok": False,
        }
    except URLError as exc:
        return {
            "url": url,
            "status": None,
            "headers": {},
            "body": str(exc),
            "ok": False,
        }


def _extract_title(html: str) -> str | None:
    match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip() or None


def run_recon(
    *,
    target: str,
    program: str,
    scope_domains: list[str],
    audit_path: Path,
    artifacts_dir: Path,
    kill_switch_path: Path,
    allow_private_targets: bool = False,
    timeout: int = 10,
) -> Path:
    kill_switch = KillSwitch(kill_switch_path)
    kill_switch.assert_clear()
    ensure_action_allowed(ActionClass.PASSIVE_RECON)
    spec = ensure_target_allowed(target, scope_domains, allow_private_targets=allow_private_targets)

    audit = AuditLogger(audit_path)
    audit.log("recon.started", {"target": target, "program": program})

    base = _request(target, timeout=timeout)
    base_root = target.rstrip("/") + "/"
    robots = _request(urljoin(base_root, "robots.txt"), timeout=timeout)
    security = _request(urljoin(base_root, ".well-known/security.txt"), timeout=timeout)

    headers = {key.lower(): value for key, value in base["headers"].items()}
    findings: list[ReconFinding] = []

    if base["status"]:
        findings.append(ReconFinding("info", "base-response", f"HTTP status {base['status']} from target root"))
    if headers.get("server"):
        findings.append(ReconFinding("info", "server-banner", f"Server header exposed: {headers['server']}"))
    if spec.scheme == "https" and "strict-transport-security" not in headers:
        findings.append(ReconFinding("low", "missing-hsts", "HTTPS target does not advertise HSTS on the base response"))
    if "content-security-policy" not in headers:
        findings.append(ReconFinding("info", "missing-csp", "Base response does not include a Content-Security-Policy header"))
    if security["status"] == 200:
        findings.append(ReconFinding("info", "security-txt", "security.txt is published"))
    else:
        findings.append(ReconFinding("info", "security-txt-missing", "security.txt not found on the standard path"))
    if robots["status"] == 200 and robots["body"]:
        sample = " | ".join(line.strip() for line in robots["body"].splitlines()[:5] if line.strip())
        findings.append(ReconFinding("info", "robots-present", sample[:240]))

    result = ReconResult(
        program=program,
        target=target,
        scanned_at=utc_now(),
        title=_extract_title(base["body"]),
        headers=headers,
        findings=findings,
        endpoints_checked=[
            {"url": base["url"], "status": base["status"]},
            {"url": robots["url"], "status": robots["status"]},
            {"url": security["url"], "status": security["status"]},
        ],
    )

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_path = artifacts_dir / f"{program}-{spec.host.replace('.', '-')}.json"
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(result), handle, indent=2)
        handle.write("\n")

    audit.log("recon.completed", {"target": target, "program": program, "report_path": str(report_path)})
    return report_path
