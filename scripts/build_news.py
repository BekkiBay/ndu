#!/usr/bin/env python3
"""Generates the news pages of the site from content/news.json.

Writes news-<slug>.html for every post, news.html (the listing) and replaces
the block between the news:carousel markers in index.html with the latest
posts. The page shell (head, header, menu, footer, scripts) is taken from
contact.html on every run, so header and footer changes reach the news pages
without a separate template.

The same pages are produced for every language of the site: Uzbek in the
repository root, Russian in ru/ and English in en/. A language is built when
its own shell donor (<lang>/contact.html, written by scripts/build_i18n.py)
exists, so this script must run after build_i18n.py. Post texts come from the
per-language fields of content/news.json (title_ru, body_en …) and fall back
to the Uzbek original while a translation is missing.

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
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import i18n  # noqa: E402
import build_i18n  # noqa: E402

SLUG_RE = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
SLUG_MAX = 80
CAROUSEL_START = '<!-- news:carousel -->'
CAROUSEL_END = '<!-- /news:carousel -->'
CAROUSEL_LIMIT = 6
CONTENT_MARK = '<section id="sp-page-title"'
FOOTER_MARK = '<!-- ====== FOOTER'
DONOR = 'contact.html'
LIST_HERO = 'images/nsu/news/campus.jpg'
SEAL = 'images/nsu/nsu-seal-navy.png'

LANGS = i18n.LANGS

MONTHS_UZ = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
             'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr']
MONTHS_RU = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
             'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
MONTHS_EN = ['January', 'February', 'March', 'April', 'May', 'June',
             'July', 'August', 'September', 'October', 'November', 'December']

#: Подписи страниц новостей на каждом языке. Всё, что генератор пишет
#: сам, а не берёт из content/news.json.
LABELS = {
    'uz': {
        'months': MONTHS_UZ,
        'date': lambda d, m: f'{d.day}-{m}, {d.year}',
        'home': 'Bosh sahifa',
        'news': 'Yangiliklar',
        'tag': 'YANGILIKLAR',
        'views': 'Ko‘rishlar:',
        'list_title': 'Yangiliklar va e’lonlar',
        'list_sub': 'Universitet hayotidan so‘nggi xabarlar, tadbirlar va e’lonlar.',
        'cta_title': 'Savolingiz yoki taklifingiz bormi?',
        'cta_text': 'Universitet jamoasi siz bilan bogʻlanishdan mamnun. '
                    'Biz bilan toʻgʻridan-toʻgʻri aloqaga chiqing.',
        'cta_contact': 'Bogʻlanish',
        'cta_apply': 'Hujjat topshirish',
    },
    'ru': {
        'months': MONTHS_RU,
        'date': lambda d, m: f'{d.day} {m} {d.year}',
        'home': 'Главная',
        'news': 'Новости',
        'tag': 'НОВОСТИ',
        'views': 'Просмотры:',
        'list_title': 'Новости и объявления',
        'list_sub': 'Последние новости, события и объявления из жизни университета.',
        'cta_title': 'Есть вопрос или предложение?',
        'cta_text': 'Команда университета будет рада связаться с вами. '
                    'Свяжитесь с нами напрямую.',
        'cta_contact': 'Связаться',
        'cta_apply': 'Подать документы',
    },
    'en': {
        'months': MONTHS_EN,
        'date': lambda d, m: f'{d.day} {m} {d.year}',
        'home': 'Home',
        'news': 'News',
        'tag': 'NEWS',
        'views': 'Views:',
        'list_title': 'News and announcements',
        'list_sub': 'The latest news, events and announcements from university life.',
        'cta_title': 'Have a question or a suggestion?',
        'cta_text': 'The university team will be glad to hear from you. '
                    'Get in touch with us directly.',
        'cta_contact': 'Contact us',
        'cta_apply': 'Apply now',
    },
}


class BuildError(Exception):
    """A problem in the input data or the page markup; reported without a traceback."""


def esc(text):
    return html.escape(text or '', quote=True)


def asset(path, lang):
    """Путь к общему файлу со страницы языка ``lang``."""
    return build_i18n.asset_url(lang, path)


def field(post, name, lang):
    """Значение поля поста на языке ``lang`` с откатом на узбекский."""
    if lang != 'uz':
        value = post.get(f'{name}_{lang}')
        if isinstance(value, str) and value.strip():
            return value
    return post.get(name) or ''


def parse_date(iso):
    if iso is None:
        return None
    try:
        return dt.date.fromisoformat(iso)
    except (TypeError, ValueError):
        raise BuildError(f'bad date {iso!r}: expected YYYY-MM-DD or null')


def format_date(iso, lang='uz'):
    d = parse_date(iso)
    if d is None:
        return ''
    labels = LABELS[lang]
    return labels['date'](d, labels['months'][d.month - 1])


def format_date_uz(iso):
    return format_date(iso, 'uz')


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

    def __init__(self, head, tail, lang='uz'):
        self.head, self.tail, self.lang = head, tail, lang

    @classmethod
    def from_donor(cls, page_html, where=DONOR, lang='uz'):
        start = find_once(page_html, CONTENT_MARK, where)
        footer = find_once(page_html, FOOTER_MARK, where)
        if footer < start:
            raise BuildError(f'{where}: footer marker precedes the content marker')
        head = page_html[:start]
        head = re.sub(r'(class="menu__(?:link|btn)) is-active"', r'\1"', head)
        head = sub_once(r'class="menu__link" href="news\.html"',
                        'class="menu__link is-active" href="news.html"', head, where)
        return cls(head, page_html[footer:], lang)

    def render(self, title, description, og_image, content, before_body_end='', page=None):
        full = f'{title} — NavDU'
        head = self.head
        head = sub_once(r'<meta name="og:title" content="[^"]*">',
                        lambda m: f'<meta name="og:title" content="{esc(full)}">', head, 'head')
        head = sub_once(r'<meta name="og:image" content="[^"]*">',
                        lambda m: f'<meta name="og:image" content="{esc(og_image)}">', head, 'head')
        head = sub_once(r'<meta name="description" content="[^"]*">',
                        lambda m: f'<meta name="description" content="{esc(description)}">', head, 'head')
        head = sub_once(r'<title>[^<]*</title>', lambda m: f'<title>{esc(full)}</title>', head, 'head')
        if page:
            head = retarget(head, self.lang, page)
        tail = self.tail
        if before_body_end:
            tail = sub_once(r'</body>', lambda m: f'{before_body_end}\n</body>', tail, 'tail')
        return head + content + tail


def retarget(head, lang, page):
    """Наводит переключатель языка и ссылки hreflang на страницу ``page``.

    Оболочка берётся у contact.html, поэтому в ней и переключатель, и
    ``hreflang`` указывают на contact.html — их надо переписать под ту
    страницу, которая сейчас собирается. Если донор без этих блоков
    (так устроены тесты), ничего не делается.
    """
    if build_i18n.LANG_BLOCK.search(head):
        head = build_i18n.LANG_BLOCK.sub(
            lambda _m: build_i18n.lang_switcher(lang, page), head, count=1)
    if build_i18n.ALTERNATE_BLOCK.search(head):
        head = build_i18n.ALTERNATE_BLOCK.sub(
            lambda _m: build_i18n.alternates(page), head, count=1)
    return head


# --------------------------------------------------------------------------- markup

CTA = ('<section id="nsu-cta-sec" class="sppb-section nsu-cta-sec"><div class="sppb-row-container">'
       '<div class="sppb-row"><div class="sppb-row-column"><div class="sppb-column"><div class="sppb-column-addons">'
       '<div class="nsu-cta"><h3>{title}</h3>'
       '<p>{text}</p>'
       '<div class="nsu-cta-btns"><a class="nsu-btn nsu-btn-primary" href="contact.html">{contact}</a>'
       '<a class="nsu-btn nsu-btn-ghost" href="https://qabul.nsu.uz/" target="_blank" rel="noopener">{apply}</a>'
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
(function(){{
  var el=document.querySelector('[data-views]');if(!el)return;
  fetch('{endpoint}',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{slug:el.getAttribute('data-views')}})}})
  .then(function(r){{return r.ok?r.json():Promise.reject(r.status)}})
  .then(function(d){{el.textContent=d.count;el.closest('.nsu-post-views').hidden=false}})
  .catch(function(){{}});
}})();
</script>"""


def cta(lang):
    labels = LABELS[lang]
    return CTA.format(title=esc(labels['cta_title']), text=esc(labels['cta_text']),
                      contact=esc(labels['cta_contact']), apply=esc(labels['cta_apply']))


def hero(cover, crumbs, title, extra=''):
    return (f'<section id="sp-page-title" class="nsu-page-hero has-bg" style="background-image:url({esc(cover)})">'
            f'<div class="container"><div class="container-inner"><div class="nsu-hero-inner">'
            f'<nav class="nsu-crumbs" aria-label="breadcrumb">{crumbs}</nav><h1>{esc(title)}</h1>{extra}'
            f'</div></div></div></section>')


def crumbs(lang, tail=None):
    labels = LABELS[lang]
    line = f'<a href="index.html">{esc(labels["home"])}</a> <span class="sep">/</span> '
    if tail is None:
        return line + f'<a href="news.html">{esc(labels["news"])}</a>'
    return line + f'<span>{esc(tail)}</span>'


def render_post(post, shell, lang='uz'):
    labels = LABELS[lang]
    title = field(post, 'title', lang)
    date = format_date(post.get('date'), lang)
    meta = ''
    if date:
        meta += f'<span class="nsu-post-date">{date}</span>'
    meta += (f'<span class="nsu-post-views" hidden>{esc(labels["views"])} '
             f'<span data-views="{esc(post["slug"])}">…</span></span>')
    cover = asset(post['cover'], lang)
    gallery = ''
    if post.get('gallery'):
        items = ''.join(f'<a href="{esc(asset(src, lang))}" target="_blank" rel="noopener">'
                        f'<img src="{esc(asset(src, lang))}" alt="" loading="lazy"></a>'
                        for src in post['gallery'])
        gallery = f'<div class="nsu-post-gallery">{items}</div>'
    body = relocate_html(field(post, 'body', lang), lang)
    content = (hero(cover, crumbs(lang), title, f'<p class="nsu-post-meta">{meta}</p>')
               + MAIN_OPEN + TEXT_OPEN.format(sid='nsu-sec-0')
               + f'<div class="nsu-post-body">{body}</div>' + gallery
               + TEXT_CLOSE + cta(lang) + MAIN_CLOSE)
    description = field(post, 'excerpt', lang).strip() or title
    views = VIEWS_SCRIPT.format(endpoint=asset('views/hit', lang))
    return shell.render(title, description, cover, content,
                        before_body_end=views, page=f'news-{post["slug"]}.html')


def relocate_html(body, lang):
    """Переписывает относительные ссылки в теле поста для подкаталога языка."""
    if lang == 'uz' or not body:
        return body
    pages = {'index.html', 'news.html', 'contact.html'}
    return i18n.apply(body, {}, depth=1, page_links=pages)


def card(post, lang):
    tag = format_date(post.get('date'), lang) or LABELS[lang]['tag']
    title = field(post, 'title', lang)
    excerpt = field(post, 'excerpt', lang).strip()
    p = f'<p>{esc(excerpt)}</p>' if excerpt else ''
    cover = asset(post['cover'], lang)
    return (f'<div class="col-md-6 col-lg-4"><a class="nsu-news-card" href="news-{post["slug"]}.html">'
            f'<div class="nsu-news-img"><img src="{esc(cover)}" alt="{esc(title)}" loading="lazy"></div>'
            f'<div class="nsu-news-body"><span class="nsu-news-tag">{tag}</span><h4>{esc(title)}</h4>{p}</div>'
            f'</a></div>')


def render_list(posts, shell, lang='uz'):
    labels = LABELS[lang]
    title = labels['list_title']
    sub = labels['list_sub']
    grid = ''.join(card(p, lang) for p in sort_posts(posts))
    content = (hero(asset(LIST_HERO, lang), crumbs(lang, labels['tag']), title,
                    f'<p class="nsu-hero-sub">{esc(sub)}</p>')
               + MAIN_OPEN + TEXT_OPEN.format(sid='nsu-news-list')
               + f'<div class="row nsu-news-grid">{grid}</div>'
               + TEXT_CLOSE + cta(lang) + MAIN_CLOSE)
    return shell.render(title, sub, asset(SEAL, lang), content, page='news.html')


def carousel_item(post, lang='uz'):
    href = f'news-{post["slug"]}.html'
    title = field(post, 'title', lang)
    cover = asset(post['cover'], lang)
    return (f'<div role="article" class="sppb-articles-carousel-column "><div class="sppb-articles-carousel-img">'
            f'<a href="{href}" class="sppb-articles-carousel-img-link" itemprop="url">'
            f'<img src="{esc(cover)}" alt="{esc(title)}" loading="lazy" /></a></div>'
            f'<div class="sppb-articles-carousel-content sppb-text-left">'
            f'<a href="{href}" class="sppb-articles-carousel-link" itemprop="url">{esc(title)}</a>'
            f'<span class="sppb-articles-carousel-meta-category"><a href="news.html" itemprop="genre">'
            f'{esc(LABELS[lang]["tag"])}</a></span>'
            f'</div></div>')


def patch_carousel(index_html, posts, lang='uz'):
    start = find_once(index_html, CAROUSEL_START, 'index.html')
    end = find_once(index_html, CAROUSEL_END, 'index.html')
    if end < start:
        raise BuildError('index.html: news:carousel end marker precedes the start marker')
    items = ''.join(carousel_item(p, lang) for p in sort_posts(posts)[:CAROUSEL_LIMIT])
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


def languages(root):
    """Языки, для которых в дереве есть оболочка: узбекский плюс готовые переводы."""
    found = ['uz']
    for lang in LANGS:
        folder = i18n.LANG_DIR.get(lang)
        if folder and (root / folder / DONOR).is_file():
            found.append(lang)
    return found


def build(root=ROOT):
    root = pathlib.Path(root)
    posts = load_posts(root)
    validate_posts(posts, root)
    result = {'written': [], 'deleted': [], 'unchanged': []}

    def emit(name, text):
        (result['written'] if write_if_changed(root / name, text) else result['unchanged']).append(name)

    for lang in languages(root):
        folder = i18n.LANG_DIR.get(lang) or ''
        base = f'{folder}/' if folder else ''
        donor = (root / base / DONOR).read_text(encoding='utf-8')
        shell = Shell.from_donor(donor, where=f'{base}{DONOR}', lang=lang)
        wanted = set()
        for p in posts:
            name = f'{base}news-{p["slug"]}.html'
            wanted.add(name)
            emit(name, render_post(p, shell, lang))
        emit(f'{base}news.html', render_list(posts, shell, lang))
        index_path = root / base / 'index.html'
        emit(f'{base}index.html',
             patch_carousel(index_path.read_text(encoding='utf-8'), posts, lang))
        for stale in sorted((root / base if base else root).glob('news-*.html')):
            if f'{base}{stale.name}' not in wanted:
                stale.unlink()
                result['deleted'].append(f'{base}{stale.name}')
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
