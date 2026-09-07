#!/usr/bin/env python3
"""Append a content hash to every local stylesheet and script reference.

    style.css  ->  style.css?v=3f9a1c2e
    main.js    ->  main.js?v=9b0d4e71

Run at deploy time, on the throwaway checkout, right before rsync. The committed
HTML stays clean; only what lands on the server carries the stamps.

Why: a browser only asks the server for a URL it does not already hold in
cache. Changing the URL is the one thing that reaches a browser that has
stopped asking.

Idempotent - an existing ?v= is replaced, not doubled.
"""
import glob
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = re.compile(
    r'((?:href|src)=")((?!https?:|//)[^"?#]+\.(?:css|js))(?:\?v=[0-9a-f]+)?(")'
)


def digest(path):
    with open(path, "rb") as fh:
        return hashlib.sha1(fh.read()).hexdigest()[:8]


def main():
    hashes = {}
    changed = 0
    for page in sorted(glob.glob(os.path.join(ROOT, "*.html"))):
        with open(page, encoding="utf-8") as fh:
            html = fh.read()

        def stamp(m):
            rel = m.group(2)
            full = os.path.join(ROOT, rel)
            if rel not in hashes:
                if not os.path.exists(full):
                    print(f"{os.path.basename(page)}: {rel} does not exist", file=sys.stderr)
                    sys.exit(1)
                hashes[rel] = digest(full)
            return f"{m.group(1)}{rel}?v={hashes[rel]}{m.group(3)}"

        out = REF.sub(stamp, html)
        if out != html:
            with open(page, "w", encoding="utf-8") as fh:
                fh.write(out)
            changed += 1

    for rel, h in sorted(hashes.items()):
        print(f"  {rel}?v={h}")
    print(f"stamped {changed} page(s)")


if __name__ == "__main__":
    main()
