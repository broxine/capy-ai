from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_POLICY = {
    "category_cluster": {
        "login-surface": "auth-session",
        "callback-parameter": "auth-session",
        "dom-sink": "client-injection",
        "wallet-signature": "wallet-signature",
    },
    "category_weight": {
        "login-surface": 4,
        "callback-parameter": 5,
        "dom-sink": 6,
        "wallet-signature": 6,
    },
    "confidence_weight": {
        "low": 2,
        "medium": 4,
        "high": 6,
    },
    "severity_thresholds": [
        [12, "high"],
        [8, "medium"],
        [0, "low"],
    ],
}


@dataclass
class ScoringPolicy:
    category_cluster: dict[str, str]
    category_weight: dict[str, int]
    confidence_weight: dict[str, int]
    severity_thresholds: list[tuple[int, str]]


def load_scoring_policy(repo_root: Path) -> ScoringPolicy:
    path = repo_root / "config" / "scoring-policy.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = DEFAULT_POLICY
    return ScoringPolicy(
        category_cluster=payload["category_cluster"],
        category_weight=payload["category_weight"],
        confidence_weight=payload["confidence_weight"],
        severity_thresholds=[(int(item[0]), str(item[1])) for item in payload["severity_thresholds"]],
    )
