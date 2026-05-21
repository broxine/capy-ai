import json
from pathlib import Path

from bughunter_hive.programs import load_program_profile, write_program_profile


def test_write_program_profile_creates_json_and_wiki(tmp_path: Path) -> None:
    profile = write_program_profile(
        repo_root=tmp_path,
        name="Immutable Demo",
        platform="web3",
        program_url="https://example.com/program",
        scope_domains=["api.example.com"],
        assets=["bridge-api", "wallet-ui"],
        exclusions=["mainnet live exploit"],
        tags=["bridge", "wallet"],
        notes=["check permit and signing flows"],
    )
    assert profile.slug == "immutable-demo"

    json_path = tmp_path / "knowledge" / "programs" / "immutable-demo.json"
    wiki_path = tmp_path / "knowledge" / "wiki" / "programs" / "immutable-demo.md"
    assert json.loads(json_path.read_text(encoding="utf-8"))["platform"] == "web3"
    assert "permit and signing flows" in wiki_path.read_text(encoding="utf-8")

    loaded = load_program_profile(tmp_path, "immutable-demo")
    assert loaded.name == "Immutable Demo"
