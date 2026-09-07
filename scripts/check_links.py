#!/usr/bin/env python3
"""Fails the build if any page links to a missing page or asset."""
import glob
import os
import re
import sys
import urllib.parse

SKIP = ("http://", "https://", "mailto:", "tel:", "#", "//", "data:")
ASSET = re.compile(
    r'(?:src|href)="((?!http|mailto|tel|#|//|data:)[^"]+\.'
    r'(?:css|js|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|eot|otf|pdf|mp4|webm))"'
)
PAGE = re.compile(r'href="([^"#?]+\.html)"')

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(root)

pages = sorted(glob.glob("*.html"))
if not pages:
    sys.exit("no html pages found")

known = set(pages)
missing_pages, missing_assets = {}, {}

for page in pages:
    html = open(page, encoding="utf-8").read()
    for target in set(PAGE.findall(html)):
        if target not in known:
            missing_pages.setdefault(target, []).append(page)
    for ref in set(ASSET.findall(html)):
        path = urllib.parse.unquote(ref.split("?")[0])
        if not os.path.isfile(path):
            missing_assets.setdefault(path, []).append(page)

print(f"pages checked: {len(pages)}")
print(f"broken page links: {len(missing_pages)}")
print(f"broken asset refs: {len(missing_assets)}")

for kind, bad in (("page", missing_pages), ("asset", missing_assets)):
    for target, sources in sorted(bad.items())[:20]:
        print(f"  missing {kind}: {target}  <- {', '.join(sources[:3])}")

if missing_pages or missing_assets:
    sys.exit(1)
print("OK")
