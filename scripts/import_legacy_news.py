#!/usr/bin/env python3
"""One-off import of the eleven hand-generated news pages into content/news.json.

Kept in the repository as the record of where the initial data came from.
Reads news.html (card order and excerpts) and every news-*.html (title, cover,
body). Dates are left null: nsuz.uz never published them and we do not invent
them. Run once from the repository root; safe to re-run before the old pages
are removed from git.
"""
import datetime as dt
import html
import json
import os
import re
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(root)

CARD = re.compile(
    r'<a class="nsu-news-card" href="news-(?P<slug>[a-z0-9-]+)\.html">.*?'
    r'<h4>(?P<title>.*?)</h4>(?:<p>(?P<excerpt>.*?)</p>)?</div></a>', re.S)
H1 = re.compile(r'<h1>(.*?)</h1>', re.S)
COVER = re.compile(r'id="sp-page-title"[^>]*background-image:url\(([^)]+)\)')
BODY = re.compile(r'<div class="sppb-addon-content">(.*?)</div></div></div></div>', re.S)


def main():
    listing = open('news.html', encoding='utf-8').read()
    cards = list(CARD.finditer(listing))
    if not cards:
        sys.exit('import_legacy_news: no cards found in news.html')
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    posts = []
    for card in cards:
        slug = card['slug']
        page = open(f'news-{slug}.html', encoding='utf-8').read()
        title = html.unescape(H1.search(page).group(1)).strip()
        cover = COVER.search(page).group(1)
        body = BODY.search(page).group(1).strip()
        excerpt = html.unescape(card['excerpt'] or '').strip()
        if not os.path.isfile(cover):
            sys.exit(f'import_legacy_news: cover {cover} of {slug} does not exist')
        posts.append({
            'slug': slug, 'title': title, 'date': None, 'excerpt': excerpt,
            'cover': cover, 'body': body, 'gallery': [], 'updated': now,
        })
    os.makedirs('content', exist_ok=True)
    with open('content/news.json', 'w', encoding='utf-8') as fh:
        json.dump({'posts': posts}, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    print(f'imported {len(posts)} posts -> content/news.json')


if __name__ == '__main__':
    main()
