from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BugClass:
    id: str
    name: str
    platforms: tuple[str, ...]
    triggers: tuple[str, ...]
    rationale: str
    safe_checks: tuple[str, ...]


BUG_CLASSES: tuple[BugClass, ...] = (
    BugClass(
        id="web2-idor-access-control",
        name="IDOR / broken access control",
        platforms=("web2", "hybrid"),
        triggers=("api", "admin", "dashboard", "graphql", "user", "account"),
        rationale="Public programs still leak object-level authorization bugs through predictable identifiers and role seams.",
        safe_checks=(
            "map identifier formats without mutating state",
            "compare unauthenticated vs authenticated object exposure",
            "check whether cross-account reads are trivially enumerable",
        ),
    ),
    BugClass(
        id="web2-auth-session",
        name="Auth and session boundary flaws",
        platforms=("web2", "hybrid"),
        triggers=("auth", "login", "oauth", "session", "sso", "jwt"),
        rationale="Auth handoffs and token handling create frequent logic gaps, especially across OAuth and SSO flows.",
        safe_checks=(
            "enumerate auth entry points and callback URLs",
            "inspect cookie flags, redirect handling, and token scope",
            "look for passive clues of privilege confusion or missing binding",
        ),
    ),
    BugClass(
        id="web2-client-sink",
        name="Client-side injection and unsafe browser trust",
        platforms=("web2", "hybrid"),
        triggers=("web", "app", "portal", "dashboard", "search", "share"),
        rationale="Modern apps still expose DOM sinks, postMessage trust mistakes, and CSP gaps.",
        safe_checks=(
            "inventory script sources, CSP, and frame policies",
            "map reflected parameters and DOM sinks without payload escalation",
            "review postMessage listeners and origin assumptions",
        ),
    ),
    BugClass(
        id="web3-signature-domain",
        name="Signature replay / missing domain separation",
        platforms=("web3", "hybrid"),
        triggers=("wallet", "sign", "permit", "bridge", "order", "meta-tx"),
        rationale="Permit, meta-tx, and off-chain authorization paths fail when nonces, domains, or chain IDs are weakly bound.",
        safe_checks=(
            "locate signing flows and typed-data schemas",
            "compare nonce, expiry, and chain/domain binding assumptions",
            "review whether signatures are reused across contexts",
        ),
    ),
    BugClass(
        id="web3-upgrade-initialization",
        name="Unsafe upgradeability / initialization",
        platforms=("web3", "hybrid"),
        triggers=("proxy", "upgrade", "governance", "admin", "vault"),
        rationale="Upgradeable systems keep failing around initializer access, storage collisions, and privileged upgrade paths.",
        safe_checks=(
            "map upgrade surfaces and admin roles from docs and public artifacts",
            "inspect initialization assumptions and one-time guards",
            "look for mismatched implementation vs proxy trust boundaries",
        ),
    ),
    BugClass(
        id="web3-accounting-oracle",
        name="Accounting, oracle, and price invariant breaks",
        platforms=("web3", "hybrid"),
        triggers=("oracle", "price", "vault", "staking", "pool", "amm"),
        rationale="Economic bugs often emerge where pricing, rounding, or stale oracle assumptions touch user balances.",
        safe_checks=(
            "trace price dependencies and freshness assumptions",
            "list rounding boundaries and share-accounting rules",
            "identify low-liquidity or externally influenceable inputs",
        ),
    ),
)


def get_bug_class_by_id(bug_class_id: str) -> BugClass | None:
    for bug_class in BUG_CLASSES:
        if bug_class.id == bug_class_id:
            return bug_class
    return None


def get_bug_class_by_name(name: str) -> BugClass | None:
    normalized = name.strip().lower()
    for bug_class in BUG_CLASSES:
        if bug_class.name.lower() == normalized:
            return bug_class
    return None
