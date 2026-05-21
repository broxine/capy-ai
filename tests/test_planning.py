from pathlib import Path

from bughunter_hive.planning import build_campaign_plan
from bughunter_hive.programs import write_program_profile


def test_build_campaign_plan_ranks_relevant_hypotheses(tmp_path: Path) -> None:
    profile = write_program_profile(
        repo_root=tmp_path,
        name="Bridge Wallet Demo",
        platform="web3",
        program_url=None,
        scope_domains=["wallet.example.com"],
        assets=["wallet-ui", "permit-api", "bridge"],
        exclusions=[],
        tags=["wallet", "bridge"],
        notes=["typed data signing and permit flow"],
    )

    plan = build_campaign_plan(tmp_path, profile, limit=3)
    assert plan.program_slug == "bridge-wallet-demo"
    assert plan.hypotheses
    assert plan.hypotheses[0].bug_class_id == "web3-signature-domain"
    assert "run safe checks only" in plan.hypotheses[0].caveman_handoff
