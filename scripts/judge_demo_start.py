"""Windows one-click supervisor. Ctrl+C closes only the two child processes it owns."""
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from web.judge_demo import ROOT, initialize


def main():
    os.chdir(REPO)
    binary = REPO / 'outputs/judge-tools/cloudflared.exe'
    if not binary.is_file():
        raise SystemExit('Install official cloudflared into outputs/judge-tools/cloudflared.exe first. See docs/judge-demo.md')
    if not (REPO / 'web/frontend/dist/index.html').is_file():
        raise SystemExit('Frontend build missing. Build it before opening a tunnel.')
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', 7861))
        except OSError:
            raise SystemExit('Port 7861 is already in use. Close the previous demo window; do not stop your personal app.')
    initialize()
    if os.name == 'nt':
        identity = subprocess.check_output(['whoami'], text=True).strip()
        acl = subprocess.run(['icacls', str(ROOT), '/inheritance:r', '/grant:r', identity+':(OI)(CI)F', 'SYSTEM:(OI)(CI)F'], capture_output=True)
        if acl.returncode:
            raise SystemExit('Cannot restrict demo credential folder. Run from your normal Windows account; tunnel NOT started.')
    backend = tunnel = None
    try:
        log = (ROOT / 'backend.log').open('a', encoding='utf-8')
        backend = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'web.judge_demo:create_app', '--app-dir', str(REPO), '--factory', '--host', '127.0.0.1', '--port', '7861', '--no-access-log'], stdout=log, stderr=log)
        import httpx
        with httpx.Client(trust_env=False, timeout=2) as client:
            for _ in range(30):
                if backend.poll() is not None:
                    raise RuntimeError('Backend failed; inspect local backend.log')
                try:
                    if client.get('http://127.0.0.1:7861/api/growth/state').status_code == 401:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError('Protected backend readiness check failed; tunnel NOT started')
        tunnel = subprocess.Popen([str(binary), 'tunnel', '--url', 'http://127.0.0.1:7861', '--protocol', 'http2', '--no-autoupdate'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        print('Starting protected judge demo. Keep this window open. Ctrl+C stops sharing.')
        print('Credentials are stored ONLY in: ' + str(ROOT / 'judge-credentials.txt'))
        def watch():
            with (ROOT / 'tunnel.log').open('a', encoding='utf-8') as output:
                for line in tunnel.stdout:
                    output.write(line); output.flush()
                    match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', line)
                    if match:
                        url = match.group()
                        (ROOT / 'public-origin.txt').write_text(url, encoding='utf-8')
                        print('Judge URL: ' + url, flush=True)
        threading.Thread(target=watch, daemon=True).start()
        while backend.poll() is None and tunnel.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        print('Stopping demo; database and drafts are retained.')
    finally:
        for process in (tunnel, backend):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == '__main__':
    main()
