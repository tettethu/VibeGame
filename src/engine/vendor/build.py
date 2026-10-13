"""Rebuild the pinned browser timer bundle. Requires Node.js only for rebuilding."""

import hashlib
import json
import logging
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGES = ['@sinonjs/fake-timers@15.4.0', '@sinonjs/commons@3.0.1', 'type-detect@4.0.8', 'esbuild@0.28.0']


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    build = ROOT / '.cache/runtime-timers-build'
    vendor = ROOT / 'src/engine/vendor'
    build.mkdir(parents=True, exist_ok=True)
    vendor.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'npm_config_cache': str(ROOT / '.cache/npm')}

    def run(args: list[str]) -> None:
        logging.info('Run in %s: %s', build, args)
        subprocess.run(args, cwd=build, env=env, check=True)

    run(['npm', 'install', '--prefix', str(build), '--save-exact', '--no-audit', '--no-fund', *PACKAGES])
    logging.info('Write bundle entry: %s', build / 'entry.cjs')
    (build / 'entry.cjs').write_text("module.exports = require('@sinonjs/fake-timers');\n")
    run([str(build / 'node_modules/.bin/esbuild'), 'entry.cjs', '--bundle', '--platform=browser', '--format=iife', '--global-name=VibeGameTimers', '--legal-comments=inline', '--external:util', f'--outfile={vendor}/fake-timers.js'])
    licenses = []
    for name in ['@sinonjs/fake-timers', '@sinonjs/commons', 'type-detect']:
        package = build / 'node_modules' / name
        logging.info('Read package metadata and license: %s', package)
        info = json.loads((package / 'package.json').read_text())
        licenses.append(f"{name} {info['version']}\n\n" + (package / 'LICENSE').read_text())
    (vendor / 'fake-timers.LICENSE.txt').write_text('\n\n'.join(licenses))
    logging.info('Bundle SHA256: %s', hashlib.sha256((vendor / 'fake-timers.js').read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
