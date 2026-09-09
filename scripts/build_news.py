#!/usr/bin/env python3
"""Generates the news pages of the site from content/news.json.

Writes news-<slug>.html for every post, news.html (the listing) and replaces
the block between the news:carousel markers in index.html with the latest
posts. The page shell (head, header, menu, footer, scripts) is taken from
contact.html on every run, so header and footer changes reach the news pages
without a separate template.

Deterministic: running it twice without changing the inputs changes nothing.
Run from anywhere; paths are resolved relative to the repository root.
"""
import datetime as dt
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

SLUG_RE = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
SLUG_MAX = 80
CAROUSEL_START = '<!-- news:carousel -->'
CAROUSEL_END = '<!-- /news:carousel -->'
CAROUSEL_LIMIT = 6
CONTENT_MARK = '<section id="sp-page-title"'
FOOTER_MARK = '<!-- ====== FOOTER'
DONOR = 'contact.html'
LIST_HERO = 'images/nsu/news/campus.jpg'

MONTHS_UZ = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
             'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr']


class BuildError(Exception):
    """A problem in the input data or the page markup; reported without a traceback."""


def esc(text):
    return html.escape(text or '', quote=True)


def parse_date(iso):
    if iso is None:
        return None
    try:
        return dt.date.fromisoformat(iso)
    except (TypeError, ValueError):
        raise BuildError(f'bad date {iso!r}: expected YYYY-MM-DD or null')


def format_date_uz(iso):
    d = parse_date(iso)
    return '' if d is None else f'{d.day}-{MONTHS_UZ[d.month - 1]}, {d.year}'


def sort_posts(posts):
    dated = [p for p in posts if p.get('date')]
    undated = [p for p in posts if not p.get('date')]
    dated.sort(key=lambda p: (parse_date(p['date']), p.get('updated') or ''), reverse=True)
    return dated + undated


def validate_posts(posts, root):
    seen = set()
    for p in posts:
        slug = p.get('slug')
        if not isinstance(slug, str) or not SLUG_RE.match(slug) or len(slug) > SLUG_MAX:
            raise BuildError(f'bad slug {slug!r}: expected [a-z0-9-], max {SLUG_MAX} chars')
        if slug in seen:
            raise BuildError(f'duplicate slug {slug!r}')
        seen.add(slug)
        if not (p.get('title') or '').strip():
            raise BuildError(f'{slug}: empty title')
        parse_date(p.get('date'))
        cover = p.get('cover') or ''
        if not cover or not (root / cover).is_file():
            raise BuildError(f'{slug}: cover file {cover!r} does not exist')
        for img in p.get('gallery') or []:
            if not (root / img).is_file():
                raise BuildError(f'{slug}: gallery file {img!r} does not exist')


# --------------------------------------------------------------------------- shell

def find_once(haystack, needle, where):
    first = haystack.find(needle)
    if first < 0:
        raise BuildError(f'{where}: marker {needle!r} not found')
    if haystack.find(needle, first + len(needle)) >= 0:
        raise BuildError(f'{where}: marker {needle!r} found more than once')
    return first


def sub_once(pattern, repl, text, where):
    out, n = re.subn(pattern, repl, text, count=1)
    if n != 1:
        raise BuildError(f'{where}: pattern {pattern!r} not found')
    return out


class Shell:
    """Everything of a site page except its content: head + header, and footer."""

    def __init__(self, head, tail):
        self.head, self.tail = head, tail

    @classmethod
    def from_donor(cls, page_html, where=DONOR):
        start = find_once(page_html, CONTENT_MARK, where)
        footer = find_once(page_html, FOOTER_MARK, where)
        if footer < start:
            raise BuildError(f'{where}: footer marker precedes the content marker')
        head = page_html[:start]
        head = re.sub(r'(class="menu__(?:link|btn)) is-active"', r'\1"', head)
        head = sub_once(r'class="menu__link" href="news\.html"',
                        'class="menu__link is-active" href="news.html"', head, where)
        return cls(head, page_html[footer:])

    def render(self, title, description, og_image, content, before_body_end=''):
        full = f'{title} — NavDU'
        head = self.head
        head = sub_once(r'<meta name="og:title" content="[^"]*">',
                        lambda m: f'<meta name="og:title" content="{esc(full)}">', head, 'head')
        head = sub_once(r'<meta name="og:image" content="[^"]*">',
                        lambda m: f'<meta name="og:image" content="{esc(og_image)}">', head, 'head')
        head = sub_once(r'<meta name="description" content="[^"]*">',
                        lambda m: f'<meta name="description" content="{esc(description)}">', head, 'head')
        head = sub_once(r'<title>[^<]*</title>', lambda m: f'<title>{esc(full)}</title>', head, 'head')
        tail = self.tail
        if before_body_end:
            tail = sub_once(r'</body>', lambda m: f'{before_body_end}\n</body>', tail, 'tail')
        return head + content + tail


# --------------------------------------------------------------------------- markup

CTA = ('<section id="nsu-cta-sec" class="sppb-section nsu-cta-sec"><div class="sppb-row-container">'
       '<div class="sppb-row"><div class="sppb-row-column"><div class="sppb-column"><div class="sppb-column-addons">'
       '<div class="nsu-cta"><h3>Savolingiz yoki taklifingiz bormi?</h3>'
       '<p>Universitet jamoasi siz bilan bogʻlanishdan mamnun. Biz bilan toʻgʻridan-toʻgʻri aloqaga chiqing.</p>'
       '<div class="nsu-cta-btns"><a class="nsu-btn nsu-btn-primary" href="contact.html">Bogʻlanish</a>'
       '<a class="nsu-btn nsu-btn-ghost" href="https://qabul.nsu.uz/" target="_blank" rel="noopener">Hujjat topshirish</a>'
       '</div></div></div></div></div></div></div></section>')

MAIN_OPEN = ('<section id="sp-main-body"><div class="row"><div id="sp-component" class="col-lg-12">'
             '<div class="sp-column"><div id="sp-page-builder" class="sp-page-builder">'
             '<div class="page-content builder-container">')
MAIN_CLOSE = '</div></div></div></div></div></section>'

TEXT_OPEN = ('<section id="{sid}" class="sppb-section "><div class="sppb-row-container"><div class="sppb-row">'
             '<div class="sppb-row-column"><div class="sppb-column"><div class="sppb-column-addons">'
             '<div class="sppb-addon-wrapper addon-root-text-block"><div class="clearfix">'
             '<div class="sppb-addon sppb-addon-text-block"><div class="sppb-addon-content">')
TEXT_CLOSE = '</div></div></div></div></div></div></div></div></div></section>'

VIEWS_SCRIPT = """<script>
(function(){
  var el=document.querySelector('[data-views]');if(!el)return;
  fetch('views/hit',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({slug:el.getAttribute('data-views')})})
  .then(function(r){return r.ok?r.json():Promise.reject(r.status)})
  .then(function(d){el.textContent=d.count;el.closest('.nsu-post-views').hidden=false})
  .catch(function(){});
})();
</script>"""


def hero(cover, crumbs, title, extra=''):
    return (f'<section id="sp-page-title" class="nsu-page-hero has-bg" style="background-image:url({esc(cover)})">'
            f'<div class="container"><div class="container-inner"><div class="nsu-hero-inner">'
            f'<nav class="nsu-crumbs" aria-label="breadcrumb">{crumbs}</nav><h1>{esc(title)}</h1>{extra}'
            f'</div></div></div></section>')


def render_post(post, shell):
    date = format_date_uz(post.get('date'))
    meta = ''
    if date:
        meta += f'<span class="nsu-post-date">{date}</span>'
    meta += (f'<span class="nsu-post-views" hidden>Ko‘rishlar: '
             f'<span data-views="{esc(post["slug"])}">…</span></span>')
    crumbs = ('<a href="index.html">Bosh sahifa</a> <span class="sep">/</span> '
              '<a href="news.html">Yangiliklar</a>')
    gallery = ''
    if post.get('gallery'):
        items = ''.join(f'<a href="{esc(src)}" target="_blank" rel="noopener">'
                        f'<img src="{esc(src)}" alt="" loading="lazy"></a>' for src in post['gallery'])
        gallery = f'<div class="nsu-post-gallery">{items}</div>'
    content = (hero(post['cover'], crumbs, post['title'], f'<p class="nsu-post-meta">{meta}</p>')
               + MAIN_OPEN + TEXT_OPEN.format(sid='nsu-sec-0')
               + f'<div class="nsu-post-body">{post.get("body") or ""}</div>' + gallery
               + TEXT_CLOSE + CTA + MAIN_CLOSE)
    description = (post.get('excerpt') or '').strip() or post['title']
    return shell.render(post['title'], description, post['cover'], content, before_body_end=VIEWS_SCRIPT)


def card(post):
    tag = format_date_uz(post.get('date')) or 'YANGILIKLAR'
    excerpt = (post.get('excerpt') or '').strip()
    p = f'<p>{esc(excerpt)}</p>' if excerpt else ''
    return (f'<div class="col-md-6 col-lg-4"><a class="nsu-news-card" href="news-{post["slug"]}.html">'
            f'<div class="nsu-news-img"><img src="{esc(post["cover"])}" alt="{esc(post["title"])}" loading="lazy"></div>'
            f'<div class="nsu-news-body"><span class="nsu-news-tag">{tag}</span><h4>{esc(post["title"])}</h4>{p}</div>'
            f'</a></div>')


def render_list(posts, shell):
    title = 'Yangiliklar va e’lonlar'
    sub = 'Universitet hayotidan so‘nggi xabarlar, tadbirlar va e’lonlar.'
    crumbs = '<a href="index.html">Bosh sahifa</a> <span class="sep">/</span> <span>YANGILIKLAR</span>'
    grid = ''.join(card(p) for p in sort_posts(posts))
    content = (hero(LIST_HERO, crumbs, title, f'<p class="nsu-hero-sub">{sub}</p>')
               + MAIN_OPEN + TEXT_OPEN.format(sid='nsu-news-list')
               + f'<div class="row nsu-news-grid">{grid}</div>'
               + TEXT_CLOSE + CTA + MAIN_CLOSE)
    return shell.render(title, sub, 'images/nsu/nsu-seal-navy.png', content)


def carousel_item(post):
    href = f'news-{post["slug"]}.html'
    return (f'<div role="article" class="sppb-articles-carousel-column "><div class="sppb-articles-carousel-img">'
            f'<a href="{href}" class="sppb-articles-carousel-img-link" itemprop="url">'
            f'<img src="{esc(post["cover"])}" alt="{esc(post["title"])}" loading="lazy" /></a></div>'
            f'<div class="sppb-articles-carousel-content sppb-text-left">'
            f'<a href="{href}" class="sppb-articles-carousel-link" itemprop="url">{esc(post["title"])}</a>'
            f'<span class="sppb-articles-carousel-meta-category"><a href="news.html" itemprop="genre">YANGILIKLAR</a></span>'
            f'</div></div>')


def patch_carousel(index_html, posts):
    start = find_once(index_html, CAROUSEL_START, 'index.html')
    end = find_once(index_html, CAROUSEL_END, 'index.html')
    if end < start:
        raise BuildError('index.html: news:carousel end marker precedes the start marker')
    items = ''.join(carousel_item(p) for p in sort_posts(posts)[:CAROUSEL_LIMIT])
    return index_html[:start + len(CAROUSEL_START)] + items + index_html[end:]


# --------------------------------------------------------------------------- build

def write_if_changed(path, text):
    data = text.encode('utf-8')
    if path.is_file() and path.read_bytes() == data:
        return False
    path.write_bytes(data)
    return True


def load_posts(root):
    path = root / 'content' / 'news.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise BuildError(f'{path} not found')
    except json.JSONDecodeError as e:
        raise BuildError(f'{path}: invalid JSON: {e}')
    posts = data.get('posts') if isinstance(data, dict) else None
    if not isinstance(posts, list):
        raise BuildError(f'{path}: expected an object with a "posts" list')
    return posts


def build(root=ROOT):
    root = pathlib.Path(root)
    posts = load_posts(root)
    validate_posts(posts, root)
    shell = Shell.from_donor((root / DONOR).read_text(encoding='utf-8'))
    result = {'written': [], 'deleted': [], 'unchanged': []}

    def emit(name, text):
        (result['written'] if write_if_changed(root / name, text) else result['unchanged']).append(name)

    wanted = set()
    for p in posts:
        name = f'news-{p["slug"]}.html'
        wanted.add(name)
        emit(name, render_post(p, shell))
    emit('news.html', render_list(posts, shell))
    index_path = root / 'index.html'
    emit('index.html', patch_carousel(index_path.read_text(encoding='utf-8'), posts))
    for stale in sorted(root.glob('news-*.html')):
        if stale.name not in wanted:
            stale.unlink()
            result['deleted'].append(stale.name)
    return result


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default=str(ROOT), help='repository root (default: parent of scripts/)')
    args = ap.parse_args(argv)
    try:
        result = build(pathlib.Path(args.root))
    except BuildError as e:
        raise SystemExit(f'build_news: {e}')
    print(f"written: {len(result['written'])}, unchanged: {len(result['unchanged'])}, "
          f"deleted: {len(result['deleted'])}")
    for name in result['written']:
        print(f'  + {name}')
    for name in result['deleted']:
        print(f'  - {name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
