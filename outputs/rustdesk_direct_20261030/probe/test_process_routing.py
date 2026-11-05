"""Test process routing using only isolated loopback listeners and a private core."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
import urllib.request


CORE = Path(r"C:\ProgramData\clash-verge-service\cores\verge-mihomo.exe")
CURL = Path(r"C:\Windows\System32\curl.exe")
HERE = Path(__file__).resolve().parent


def free_port():
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"rustdesk-process-probe-ok")

    def log_message(self, *_args):
        pass


def run(mode, executable):
    proxy_port, api_port = free_port(), free_port()
    config = HERE / ("private_" + mode + ".yaml")
    config.write_text(
        "mode: " + mode + "\n"
        "mixed-port: " + str(proxy_port) + "\n"
        "bind-address: 127.0.0.1\nallow-lan: false\n"
        "external-controller: 127.0.0.1:" + str(api_port) + "\n"
        "find-process-mode: strict\nlog-level: info\n"
        "rules:\n  - PROCESS-NAME,RustDesk.exe,DIRECT\n  - MATCH,GLOBAL\n",
        encoding="utf-8",
    )
    output = HERE / ("private_" + mode + ".log")
    with output.open("wb") as log:
        process = subprocess.Popen([str(CORE), "-d", str(HERE), "-f", str(config)],
                                   stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline = time.monotonic() + 8
            while True:
                try:
                    with socket.create_connection(("127.0.0.1", api_port), timeout=.5):
                        break
                except OSError:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("private proxy did not start")
                    time.sleep(.1)
            request = urllib.request.Request(
                f"http://127.0.0.1:{api_port}/proxies/GLOBAL",
                data=json.dumps({"name": "REJECT"}).encode(), method="PUT",
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=3) as response:
                assert response.status == 204, "could not select reject in private GLOBAL"
            command = [str(executable), "--silent", "--show-error", "--noproxy", "",
                       "--proxy", f"http://127.0.0.1:{proxy_port}", "--max-time", "5",
                       f"http://127.0.0.1:{server.server_port}/test"]
            response = subprocess.run(command, capture_output=True, timeout=7)
            return response.returncode, response.stdout.decode(errors="replace")
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    test_exe = HERE / "RustDesk.exe"
    shutil.copyfile(CURL, test_exe)
    server = HTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        global_result = run("global", test_exe)
        rule_result = run("rule", test_exe)
        unrelated_result = run("rule", CURL)
        result = {
            "global_mode_rule_ignored": global_result != (0, "rustdesk-process-probe-ok"),
            "rule_mode_rustdesk_direct": rule_result == (0, "rustdesk-process-probe-ok"),
            "rule_mode_other_uses_global": unrelated_result != (0, "rustdesk-process-probe-ok"),
            "real_proxy_or_rustdesk_changed": False,
            "loopback_only": True,
        }
        print(json.dumps(result, ensure_ascii=False))
        if not all(result[k] for k in ("global_mode_rule_ignored", "rule_mode_rustdesk_direct", "rule_mode_other_uses_global")):
            raise SystemExit(1)
    finally:
        server.shutdown()
        server.server_close()
        test_exe.unlink(missing_ok=True)
