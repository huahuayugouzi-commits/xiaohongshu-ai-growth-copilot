#!/usr/bin/env bash
# Run only on the authorized server, after extracting a reviewed runtime archive.
set -euo pipefail
umask 077
[[ $EUID -eq 0 ]] || { echo 'Run with sudo'; exit 1; }
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || { echo 'Ubuntu 24.04 required'; exit 1; }
release=$(realpath "$(dirname "$0")/../..")
[[ $release =~ ^/opt/growth-copilot/releases/[A-Za-z0-9._-]+$ ]] || { echo 'Extract into /opt/growth-copilot/releases/RELEASE_ID first'; exit 1; }
[[ -f $release/release-manifest.json && -f $release/web/frontend/dist/index.html ]] || exit 1
python3 - "$release" <<'PY'
import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1])
for name,sha in json.loads((root/'release-manifest.json').read_text()).items():
    path=(root/name).resolve()
    assert path.is_relative_to(root) and path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest()==sha, 'Release checksum mismatch'
PY
# Dependency installation is deliberate; no dependency trimming or model downloads.
apt-get update
apt-get install -y python3 python3-venv python3-dev build-essential libglib2.0-0 libgl1 ffmpeg
id growth >/dev/null 2>&1 || useradd --system --home-dir /var/lib/growth-copilot --shell /usr/sbin/nologin growth
install -d -m 0700 -o growth -g growth /var/lib/growth-copilot /var/backups/growth-copilot
install -d -m 0700 /etc/growth-copilot
if [[ ! -f /etc/growth-copilot/app.env ]]; then
    install -m 0600 "$release/deploy/ubuntu24/app.env.example" /etc/growth-copilot/app.env
fi
[[ ! -L $release/.venv ]] || { echo 'Refusing symlink venv'; exit 1; }
python3 -m venv "$release/.venv"
"$release/.venv/bin/python" -m pip install "$release"
"$release/.venv/bin/python" -m pip check
# Keep code root-owned; application can only write business state in /var/lib.
chmod -R a+rX "$release"
cd "$release"
runuser -u growth -- "$release/.venv/bin/python" -m easel.growth.private_auth --data-dir /var/lib/growth-copilot init
install -m 0644 "$release/deploy/ubuntu24/growth-copilot.service" /etc/systemd/system/growth-copilot.service
install -m 0644 "$release/deploy/ubuntu24/growth-backup.service" /etc/systemd/system/growth-backup.service
install -m 0644 "$release/deploy/ubuntu24/growth-backup.timer" /etc/systemd/system/growth-backup.timer
systemctl daemon-reload
echo 'Prepared only. Existing current release is unchanged. Provision users, edit private app.env, then activate.sh.'
