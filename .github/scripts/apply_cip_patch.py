#!/usr/bin/env python3
"""Apply CIP incremental patch file-by-file in strict mode.

Strategy:
  * split the unified diff into per-file chunks
  * for each chunk: try `patch --dry-run --fuzz=0`; if every hunk lands exactly,
    apply it, otherwise skip the WHOLE file (keep the fork version) so that a
    file never ends up half-patched.

Usage: apply_cip_patch.py <patchfile> <target-tree> [--max-skip N]
Exit code 1 when skipped files exceed --max-skip.
"""
import os
import re
import subprocess
import sys
import tempfile

START_RE = re.compile(r'^diff -urN ')


def split_chunks(text):
    chunks = []
    cur = []
    for line in text.splitlines(keepends=True):
        if START_RE.match(line):
            if cur:
                chunks.append(''.join(cur))
            cur = [line]
        else:
            if cur:
                cur.append(line)
    if cur:
        chunks.append(''.join(cur))
    return chunks


def target_path(chunk):
    for line in chunk.splitlines():
        if line.startswith('+++ '):
            p = line[4:].strip()
            if p == '/dev/null':
                continue
            # strip the first path component (diff -urN <dir127> <dir136>)
            parts = p.split('/')
            return '/'.join(parts[1:]) if len(parts) > 1 else p
    return None


def main():
    patchfile, tree = sys.argv[1], sys.argv[2]
    max_skip = 200
    if '--max-skip' in sys.argv:
        max_skip = int(sys.argv[sys.argv.index('--max-skip') + 1])

    text = open(patchfile, encoding='utf-8', errors='surrogateescape').read()
    chunks = split_chunks(text)
    print('chunks: %d' % len(chunks))

    applied, skipped = [], []
    for chunk in chunks:
        path = target_path(chunk)
        if not path:
            continue
        with tempfile.NamedTemporaryFile('w', suffix='.patch', delete=False,
                                         encoding='utf-8',
                                         errors='surrogateescape') as fh:
            fh.write(chunk)
            seg = fh.name
        dry = subprocess.run(
            ['patch', '-p1', '-f', '--fuzz=0', '--dry-run', '-N',
             '--reject-file=-', '-i', seg],
            cwd=tree, capture_output=True, text=True)
        if dry.returncode == 0 and 'FAILED' not in dry.stdout + dry.stderr:
            real = subprocess.run(
                ['patch', '-p1', '-f', '--fuzz=0', '-N',
                 '--no-backup-if-mismatch', '--reject-file=-', '-i', seg],
                cwd=tree, capture_output=True, text=True)
            if real.returncode == 0 and 'FAILED' not in real.stdout + real.stderr:
                applied.append(path)
            else:
                skipped.append(path)
        else:
            skipped.append(path)
        os.unlink(seg)

    print('APPLIED=%d SKIPPED=%d' % (len(applied), len(skipped)))
    print('--- skipped files ---')
    for p in skipped:
        print('  ' + p)
    sys.exit(1 if len(skipped) > max_skip else 0)


if __name__ == '__main__':
    main()
