#!/usr/bin/env python3
"""Stamps every local CSS/JS reference in the pages with ?v=<content hash>.

Without this a browser that cached a stylesheet keeps using it until the
cache expires, so a deploy ships new HTML against old CSS. The hash is
derived from the file contents, so re-running this changes nothing unless
the asset itself changed.
"""
import glob
import hashlib
import os
import re
import sys
import urllib.parse

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(root)

REF = re.compile(r'(?P<attr>(?:href|src)=")(?P<path>(?!http|//|data:)[^"?#]+\.(?:css|js))(?P<query>\?[^"#]*)?(?P<rest>[^"]*)"')

digests = {}


def digest(path):
    if path not in digests:
        with open(path, 'rb') as fh:
            digests[path] = hashlib.md5(fh.read()).hexdigest()[:10]
    return digests[path]


def stamp(match):
    path = urllib.parse.unquote(match.group('path'))
    if not os.path.isfile(path):
        return match.group(0)
    return f"{match.group('attr')}{match.group('path')}?v={digest(path)}{match.group('rest')}\""


changed = 0
pages = sorted(glob.glob('*.html'))
for page in pages:
    html = open(page, encoding='utf-8').read()
    stamped = REF.sub(stamp, html)
    if stamped != html:
        open(page, 'w', encoding='utf-8').write(stamped)
        changed += 1

print(f'pages: {len(pages)}, restamped: {changed}, assets hashed: {len(digests)}')
if not pages:
    sys.exit('no pages found')
