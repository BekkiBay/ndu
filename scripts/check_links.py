#!/usr/bin/env python3
"""Fails the build if a page or stylesheet points at something that is not there.

Checks two things:
  * every internal href/src in the HTML pages resolves to a file in the repo;
  * every url()/@import inside the CSS resolves, relative to the stylesheet.

Legacy icon-font fallbacks (.eot/.svg) are reported as warnings: they are
absent upstream too, and no current browser reaches for them once it has
found the woff2.
"""
import glob
import os
import re
import sys
import urllib.parse

ASSET = re.compile(
    r'(?:src|href)="((?!http|mailto|tel|#|//|data:)[^"]+\.'
    r'(?:css|js|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|eot|otf|pdf|mp4|webm))"'
)
PAGE = re.compile(r'href="([^"#?]+\.html)"')
CSS_REF = re.compile(r'url\(\s*["\']?([^"\')]+)["\']?\s*\)')
CSS_IMPORT = re.compile(r'@import\s+(?:url\(\s*)?["\']([^"\']+)["\']')
LEGACY_FONT = re.compile(r'\.(eot|svg)(\?|#|$)')

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(root)


def resolve(ref, base_dir):
    path = urllib.parse.unquote(ref.split('?')[0].split('#')[0])
    if not path:
        return None
    if path.startswith('/'):
        return os.path.normpath(path.lstrip('/'))
    return os.path.normpath(os.path.join(base_dir, path))


pages = sorted(glob.glob('*.html'))
if not pages:
    sys.exit('no html pages found')

known = set(pages)
errors, warnings = [], []

for page in pages:
    html = open(page, encoding='utf-8').read()
    for target in sorted(set(PAGE.findall(html))):
        if target not in known:
            errors.append(f'{page}: missing page {target}')
    for ref in sorted(set(ASSET.findall(html))):
        target = resolve(ref, '')
        if target and not os.path.isfile(target):
            errors.append(f'{page}: missing asset {ref}')

stylesheets = sorted(glob.glob('**/*.css', recursive=True))
for sheet in stylesheets:
    css = open(sheet, encoding='utf-8', errors='ignore').read()
    base = os.path.dirname(sheet)
    for ref in sorted(set(CSS_REF.findall(css)) | set(CSS_IMPORT.findall(css))):
        if ref.startswith(('data:', 'http', '//')):
            continue
        target = resolve(ref, base)
        if target and not os.path.isfile(target):
            line = f'{sheet}: missing {ref} (-> {target})'
            (warnings if LEGACY_FONT.search(ref) else errors).append(line)

print(f'pages checked      : {len(pages)}')
print(f'stylesheets checked: {len(stylesheets)}')
print(f'warnings           : {len(warnings)}')
print(f'errors             : {len(errors)}')

for line in warnings[:10]:
    print(f'  warn  {line}')
for line in errors[:30]:
    print(f'  ERROR {line}')

if errors:
    sys.exit(1)
print('OK')
