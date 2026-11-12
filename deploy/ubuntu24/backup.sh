#!/usr/bin/env bash
set -euo pipefail
umask 077
cd /opt/growth-copilot/current
destination="/var/backups/growth-copilot/daily-$(date -u +%Y%m%dT%H%M%S%N).sqlite3"
.venv/bin/python -m easel.growth.private_auth --data-dir /var/lib/growth-copilot backup "$destination"
# Profiles are immutable projections; keep them separately too, never serve this archive.
if [[ -d /var/lib/growth-copilot/profiles ]]; then
    tar -czf "$destination.profiles.tar.gz" -C /var/lib/growth-copilot profiles
fi
echo 'Backup completed. No automatic deletion; monitor disk and copy off server.'
