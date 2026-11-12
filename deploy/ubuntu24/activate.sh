#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $EUID -eq 0 ]] || exit 1
release=$(realpath "$(dirname "$0")/../..")
[[ $release =~ ^/opt/growth-copilot/releases/[A-Za-z0-9._-]+$ && -x $release/.venv/bin/python ]] || exit 1
cd "$release"
runuser -u growth -- "$release/.venv/bin/python" -c 'from easel.growth.private_auth import AuthStore; AuthStore("/var/lib/growth-copilot").ready()'
# Online SQLite snapshot before switching. Never overwrite backups.
runuser -u growth -- "$release/.venv/bin/python" -m easel.growth.private_auth --data-dir /var/lib/growth-copilot backup "/var/backups/growth-copilot/pre-release-$(date -u +%Y%m%dT%H%M%S%N).sqlite3"
current=/opt/growth-copilot/current
[[ ! -e $current || -L $current ]] || { echo 'current must be a symlink'; exit 1; }
previous=$(readlink "$current" || true)
ln -s "$release" /opt/growth-copilot/current.next
mv -Tf /opt/growth-copilot/current.next "$current"
systemctl enable growth-copilot growth-backup.timer
systemctl restart growth-copilot
sleep 3
if ! systemctl is-active --quiet growth-copilot; then
    if [[ -n $previous ]]; then ln -s "$previous" /opt/growth-copilot/current.rollback; mv -Tf /opt/growth-copilot/current.rollback "$current"; systemctl restart growth-copilot; fi
    echo 'Startup failed; inspect local service journal privately. Previous release restored if available.'
    exit 1
fi
systemctl start growth-backup.timer
echo 'Application active on loopback only. Validate Caddy and HTTPS before sharing.'
