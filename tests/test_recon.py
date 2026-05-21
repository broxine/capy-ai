from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bughunter_hive.recon import run_recon


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Server", "unit-test")
            self.end_headers()
            self.wfile.write(b"<html><title>Demo Target</title><body>Hello</body></html>")
            return
        if self.path == "/robots.txt":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"User-agent: *\nDisallow: /admin\n")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def test_run_recon_writes_report(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        target = f"http://127.0.0.1:{server.server_port}"
        report = run_recon(
            target=target,
            program="demo",
            scope_domains=["127.0.0.1"],
            audit_path=tmp_path / "events.jsonl",
            artifacts_dir=tmp_path / "artifacts",
            kill_switch_path=tmp_path / "kill.flag",
            allow_private_targets=True,
        )
        payload = json.loads(report.read_text(encoding="utf-8"))
        assert payload["title"] == "Demo Target"
        assert any(item["status"] == 200 for item in payload["endpoints_checked"])
        assert any(finding["title"] == "server-banner" for finding in payload["findings"])
    finally:
        server.shutdown()
        server.server_close()
