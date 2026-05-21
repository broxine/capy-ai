from __future__ import annotations

from pathlib import Path


class KillSwitchEngaged(RuntimeError):
    pass


class KillSwitch:
    def __init__(self, path: Path) -> None:
        self.path = path

    def status(self) -> dict[str, str | bool]:
        if self.path.exists():
            reason = self.path.read_text(encoding="utf-8").strip() or "engaged"
            return {"engaged": True, "reason": reason}
        return {"engaged": False, "reason": "clear"}

    def engage(self, reason: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(reason.strip() or "manual stop", encoding="utf-8")

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def assert_clear(self) -> None:
        status = self.status()
        if status["engaged"]:
            raise KillSwitchEngaged(f"kill switch engaged: {status['reason']}")
