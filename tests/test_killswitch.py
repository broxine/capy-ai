from pathlib import Path

from bughunter_hive.killswitch import KillSwitch, KillSwitchEngaged


def test_killswitch_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "kill.flag"
    switch = KillSwitch(path)
    assert switch.status()["engaged"] is False
    switch.engage("pause")
    assert switch.status()["engaged"] is True
    try:
        switch.assert_clear()
    except KillSwitchEngaged:
        pass
    else:
        raise AssertionError("expected kill switch to block execution")
    switch.clear()
    assert switch.status()["engaged"] is False
