from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse


class ActionClass(StrEnum):
    PASSIVE_RECON = "passive_recon"
    SAFE_VALIDATION = "safe_validation"
    LIVE_EXPLOIT = "live_exploit"


@dataclass(frozen=True)
class TargetSpec:
    url: str
    host: str
    scheme: str


def parse_target(url: str) -> TargetSpec:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("target must use http or https")
    if not parsed.hostname:
        raise ValueError("target must include a hostname")
    return TargetSpec(url=url, host=parsed.hostname.lower(), scheme=parsed.scheme)


def _is_private_or_loopback(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host == "localhost"
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local)


def ensure_target_allowed(url: str, allowed_domains: list[str], allow_private_targets: bool = False) -> TargetSpec:
    spec = parse_target(url)
    if _is_private_or_loopback(spec.host) and not allow_private_targets:
        raise PermissionError("private and loopback targets are blocked by default")

    normalized = [item.lower() for item in allowed_domains if item.strip()]
    if normalized and not any(spec.host == item or spec.host.endswith(f".{item}") for item in normalized):
        raise PermissionError("target host is outside declared scope domains")
    return spec


def ensure_action_allowed(action: ActionClass, live_approval: bool = False) -> None:
    if action == ActionClass.LIVE_EXPLOIT and not live_approval:
        raise PermissionError("live exploit actions require explicit approval")
