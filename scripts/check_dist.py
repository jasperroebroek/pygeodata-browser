"""Check built distributions before publishing: the prebuilt frontend must be in, its source must not.

Usage: python scripts/check_dist.py dist/
"""

import sys
import tarfile
import zipfile
from pathlib import Path


def check(names: list[str], prefix: str, label: str) -> list[str]:
    errors = []
    if f'{prefix}static/app/index.html' not in names:
        errors.append(f'{label}: missing {prefix}static/app/index.html (was `npm run build` run?)')
    if not any(n.startswith(f'{prefix}static/app/assets/') and n.endswith('.js') for n in names):
        errors.append(f'{label}: no built JS under {prefix}static/app/assets/')
    if f'{prefix}templates/bounds_map.html' not in names:
        errors.append(f'{label}: missing {prefix}templates/bounds_map.html')
    for forbidden in ('node_modules/', 'app/src/', 'static/js/', 'static/css/'):
        hits = [n for n in names if forbidden in n]
        if hits:
            errors.append(f'{label}: should not ship {forbidden} ({hits[0]})')
    return errors


def main(dist: Path) -> int:
    wheels = sorted(dist.glob('*.whl'))
    sdists = sorted(dist.glob('*.tar.gz'))
    if not wheels or not sdists:
        print(f'expected a wheel and an sdist in {dist}')
        return 1
    errors = []
    for wheel in wheels:
        with zipfile.ZipFile(wheel) as zf:
            errors += check(zf.namelist(), 'pygeodata_browser/', wheel.name)
    for sdist in sdists:
        with tarfile.open(sdist) as tf:
            # sdist members are '<name>-<version>/api/...'
            names = ['/'.join(n.split('/')[1:]) for n in tf.getnames()]
        errors += check(names, 'api/', sdist.name)
    for e in errors:
        print(e)
    if not errors:
        print(f'ok: {", ".join(p.name for p in wheels + sdists)}')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else 'dist')))
