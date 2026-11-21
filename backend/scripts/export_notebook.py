"""Create a private, verifiable notebook-transfer ZIP, including existing API config."""
import argparse
from contextlib import closing
from datetime import datetime
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[2]
EXCLUDE_DIRS = {'.tools', 'node_modules', '.venv', '__pycache__', '.pytest_cache',
                'artifacts', 'exports', 'dist-mobile', '.mypy_cache', '.ruff_cache'}


def source_files():
    for folder, directories, files in os.walk(ROOT):
        directories[:] = sorted(name for name in directories if name not in EXCLUDE_DIRS)
        for name in sorted(files):
            path = Path(folder) / name
            if path.is_symlink() or name.endswith(('.log', '.pyc', '.pyo', '.zip', '.sqlite3-wal', '.sqlite3-shm')):
                continue
            if name in ('.DS_Store', 'index.lock'):
                continue
            yield path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT.parent / f'TripBudget-notebook-private-{datetime.now():%Y-%m-%d}.zip')
    args = parser.parse_args()
    target = args.output.resolve()
    if target.exists():
        raise SystemExit('Output already exists; choose another --output filename')
    target.parent.mkdir(parents=True, exist_ok=True)
    included = []
    with tempfile.TemporaryDirectory(prefix='tripbudget-transfer-') as temporary:
        snapshot = Path(temporary) / 'destinations.sqlite3'
        database = ROOT / '.tools/destinations.sqlite3'
        if database.exists():
            with closing(sqlite3.connect(database)) as original, closing(sqlite3.connect(snapshot)) as copied:
                original.backup(copied)
                copied.commit()
                assert copied.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        with ZipFile(target, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
            for path in source_files():
                name = 'TripBudget/' + path.relative_to(ROOT).as_posix()
                archive.write(path, name)
                included.append(name)
            bootstrap = ROOT / '.tools/uv/uv.exe'
            if bootstrap.is_file():
                archive.write(bootstrap, 'TripBudget/.tools/uv/uv.exe')
                included.append('TripBudget/.tools/uv/uv.exe')
            if snapshot.exists():
                archive.write(snapshot, 'TripBudget/.tools/destinations.sqlite3')
                included.append('TripBudget/.tools/destinations.sqlite3')
            manifest = '\n'.join(included) + '\n'
            archive.writestr('TripBudget/TRANSFER_FILES.txt', manifest)
    with ZipFile(target) as archive:
        damaged = archive.testzip()
        if damaged:
            raise RuntimeError(f'ZIP integrity failed: {damaged}')
        names = set(archive.namelist())
        for required in ('backend/.env', 'backend/app/main.py', 'backend/requirements.lock',
                         'frontend/package-lock.json', 'frontend/src/App.jsx', 'frontend/dist/index.html',
                         'setup.ps1', 'start.ps1', 'NOTEBOOK_TRANSFER.md', '.git/HEAD'):
            if 'TripBudget/' + required not in names:
                raise RuntimeError(f'Missing transfer file: {required}')
        assert not any('/node_modules/' in name or '/.venv/' in name for name in names)
    digest = hashlib.sha256()
    with target.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    target.with_suffix('.zip.sha256').write_text(f'{digest.hexdigest()}  {target.name}\n', encoding='ascii')
    print(f'Created: {target}')
    print(f'Size: {target.stat().st_size / 1024 / 1024:.1f} MiB')
    print(f'Archive integrity: OK; files: {len(names)}')
    print('Includes private backend/.env; keep this transfer archive private.')


if __name__ == '__main__':
    main()
