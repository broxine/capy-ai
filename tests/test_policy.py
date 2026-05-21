from bughunter_hive.policy import ActionClass, ensure_action_allowed, ensure_target_allowed


def test_scope_domain_allows_subdomain() -> None:
    spec = ensure_target_allowed("https://api.example.com", ["example.com"])
    assert spec.host == "api.example.com"


def test_private_target_blocked_by_default() -> None:
    try:
        ensure_target_allowed("http://127.0.0.1:8000", ["127.0.0.1"])
    except PermissionError as exc:
        assert "blocked" in str(exc)
    else:
        raise AssertionError("expected permission error")


def test_live_exploit_requires_approval() -> None:
    try:
        ensure_action_allowed(ActionClass.LIVE_EXPLOIT)
    except PermissionError as exc:
        assert "approval" in str(exc)
    else:
        raise AssertionError("expected permission error")
