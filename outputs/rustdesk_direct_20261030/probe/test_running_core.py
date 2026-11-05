"""Probe the active Clash process rule using only a loopback HTTP server.

The probe runs a copy of Windows curl named RustDesk.exe to check process-name
matching. It does not start or control the actual RustDesk application.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import json
import shutil
import subprocess
import threading
import time

HERE = Path(__file__).resolve().parent
CLIENT = HERE / 'RustDesk.exe'
RECEIPT = HERE / 'live_probe_receipt.json'


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        RECEIPT.write_text(json.dumps({'local_server_received_request': True}), encoding='utf8')
        time.sleep(18)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'hz-local-probe-ok')

    def log_message(self, *_args):
        pass


def main():
    shutil.copyfile(r'C:\Windows\System32\curl.exe', CLIENT)
    server = HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print('Local-only process-rule probe started', flush=True)
    try:
        result = subprocess.run([str(CLIENT), '--silent', '--show-error', '--noproxy', '',
                                 '--proxy', 'http://127.0.0.1:7897', '--max-time', '25',
                                 f'http://127.0.0.1:{server.server_port}/hz_rustdesk_rule_probe'],
                                capture_output=True, timeout=28)
        ok = result.returncode == 0 and result.stdout == b'hz-local-probe-ok'
        print(json.dumps({'ok': ok, 'response_received_from_loopback': ok,
                          'actual_rustdesk_controlled': False, 'robot_contacted': False}), flush=True)
        return 0 if ok else 1
    finally:
        server.shutdown()
        server.server_close()
        CLIENT.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
