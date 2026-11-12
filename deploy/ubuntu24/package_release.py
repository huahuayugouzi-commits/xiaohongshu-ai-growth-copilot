"""Build a runtime-only archive from tracked source + built frontend. No git history/data."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]


def allowed(name):
    p = Path(name)
    if any(x.startswith('.') for x in p.parts) or any(x in {'node_modules','__pycache__','data','outputs','profiles'} for x in p.parts):
        return False
    if p.suffix.lower() in {'.db','.sqlite','.sqlite3','.key','.pem','.log'}:
        return False
    return (name in {'pyproject.toml','README.md','LICENSE','NOTICE','web/production.py','web/__init__.py'}
            or name.startswith('easel/') and p.suffix == '.py'
            or name.startswith('skills/growth/') and p.suffix in {'.md','.json'}
            or name.startswith('deploy/ubuntu24/') and p.suffix in {'.py','.sh','.service','.timer','.example','.md'}
            or name == 'docs/deployment-ubuntu24.md')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('output',type=Path)
    args = parser.parse_args()
    tracked = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    files = {name: ROOT/name for name in tracked if allowed(name)}
    for required in ('LICENSE','pyproject.toml','web/production.py','easel/growth/private_auth.py'):
        if required not in files: raise SystemExit('Stage reviewed release sources first; missing '+required)
    dist = ROOT/'web/frontend/dist'
    if not (dist/'index.html').is_file(): raise SystemExit('Build frontend first')
    for path in dist.rglob('*'):
        if path.is_file():
            if path.suffix not in {'.html','.js','.css','.woff2','.png','.svg','.jpg','.webp'}:
                raise SystemExit('Unexpected built asset type; inspect before packaging')
            files[path.relative_to(ROOT).as_posix()] = path
    manifest = {}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as stream, tarfile.open(fileobj=stream,mode='w:gz') as tar:
        for name,path in sorted(files.items()):
            if path.is_symlink(): raise SystemExit('Symlinks are not allowed in the release')
            data = path.read_bytes()
            if name.startswith('deploy/ubuntu24/'):
                data = data.replace(b'\r\n', b'\n')
            manifest[name] = hashlib.sha256(data).hexdigest()
            info = tarfile.TarInfo(name); info.size=len(data); info.mode=0o755 if name.endswith('.sh') else 0o644
            tar.addfile(info,io.BytesIO(data))
        data=json.dumps(manifest,indent=2).encode()
        info=tarfile.TarInfo('release-manifest.json'); info.size=len(data); info.mode=0o644
        tar.addfile(info,io.BytesIO(data))
    print(f'Packaged {len(files)} runtime files. No database, .env, profiles, outputs or Git history.')


if __name__ == '__main__': main()
