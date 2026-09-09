# Админка новостей — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Посты новостей живут в `content/news.json`, страницы генерируются `scripts/build_news.py` в CI, админка `admin/` правит JSON и картинки через GitHub API, счётчик просмотров — контейнер `ndu-counter` на Hermes.

**Architecture:** Статический сайт остаётся статическим. Источник правды — git. Сборка детерминирована и запускается в каждой задаче CI после checkout. Счётчик — единственный серверный процесс, он ничего не знает о постах и просто считает `(slug, посетитель, сутки)`.

**Tech Stack:** Python 3 stdlib (сборка, счётчик, тесты `unittest`), ванильный JS + Quill 2.0.3 (админка), nginx + docker compose (деплой), GitHub Actions.

Спека: `docs/superpowers/specs/2026-09-09-news-admin-design.md`.

---

## Структура файлов

| Файл | Ответственность |
|---|---|
| `content/news.json` | Источник правды по постам |
| `scripts/import_legacy_news.py` | Одноразовый импорт 11 существующих постов в JSON |
| `scripts/build_news.py` | Генерация `news-*.html`, `news.html`, блока карусели в `index.html` |
| `tests/test_build_news.py` | Тесты сборки на синтетическом доноре |
| `deploy/counter/counter.py` | HTTP-сервис счётчика (stdlib + SQLite) |
| `tests/test_counter.py` | Тесты счётчика через реальный HTTP на свободном порту |
| `deploy/docker-compose.yml`, `deploy/nginx-site.conf`, `deploy/README.md` | Контейнер счётчика, проксирование `/views/`, документация |
| `.github/workflows/ci.yml`, `deploy.yml` | Тесты → штампы → сборка → проверки → деплой; точечное удаление `news-*.html` |
| `assets/css/nsu.css` | Стили `nsu-post-meta`, `nsu-post-views`, `nsu-post-body`, `nsu-post-gallery` |
| `admin/index.html`, `admin/admin.css` | Разметка и стили админки |
| `admin/admin.js` | UI: экраны, форма, превью, статус деплоя |
| `admin/github.js` | Клиент GitHub API: чтение JSON, один коммит через Git Data API, статус Actions |
| `admin/images.js` | Сжатие картинок через canvas, base64 |
| `admin/slug.js` | `slugify(title)` с транслитерацией кириллицы |
| `admin/vendor/quill.js`, `admin/vendor/quill.snow.css` | Quill 2.0.3 |
| `README.md` | Раздел «Новости и админка» |

Общие константы, которые обязаны совпадать в Python и JS:

- `SLUG_RE = ^[a-z0-9]+(-[a-z0-9]+)*$`, длина ≤ 80;
- пути картинок `images/nsu/news/<slug>/cover.jpg`, `NN.jpg`, `gNN.jpg`;
- маркеры `<!-- news:carousel -->` / `<!-- /news:carousel -->`.

---

### Task 1: Импорт существующих постов в `content/news.json`

**Files:**
- Create: `scripts/import_legacy_news.py`
- Create: `content/news.json`

- [ ] **Step 1: Написать скрипт импорта**

```python
#!/usr/bin/env python3
"""One-off import of the eleven hand-generated news pages into content/news.json.

Kept in the repository as the record of where the initial data came from.
Reads news.html (card order and excerpts) and every news-*.html (title, cover,
body). Dates are left null: nsuz.uz never published them and we do not invent
them. Run once from the repository root; safe to re-run before the old pages
are removed from git.
"""
import datetime as dt
import glob
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
```

- [ ] **Step 2: Запустить и проверить**

Run: `python3 scripts/import_legacy_news.py && python3 -c "import json;d=json.load(open('content/news.json'));print(len(d['posts']));print([p['slug'] for p in d['posts']][:3])"`
Expected: `imported 11 posts`, затем `11` и первые slug'и `gallery-campus-life`, `gallery-graduation-2026`, `resource-center-upgrade`. Тела постов начинаются с `<p>`; у постов-галерей тело — одна строка `<p>Kampus hayoti</p>` и т. п.

- [ ] **Step 3: Commit**

```bash
git add scripts/import_legacy_news.py content/news.json
git commit -m "feat(news): import the existing eleven posts into content/news.json"
```

---

### Task 2: `build_news.py` — константы, дата, сортировка, валидация

**Files:**
- Create: `scripts/build_news.py`
- Create: `tests/__init__.py` (пустой)
- Create: `tests/test_build_news.py`

Публичный интерфейс модуля (используется тестами и `main()`):

```python
SLUG_RE: re.Pattern            # ^[a-z0-9]+(-[a-z0-9]+)*$
CAROUSEL_START = '<!-- news:carousel -->'
CAROUSEL_END = '<!-- /news:carousel -->'
CAROUSEL_LIMIT = 6
class BuildError(Exception)
def format_date_uz(iso: str | None) -> str          # '2026-09-07' -> '7-sentabr, 2026', None -> ''
def sort_posts(posts: list[dict]) -> list[dict]     # dated desc (tie: updated desc), then undated in input order
def validate_posts(posts: list[dict], root: Path) -> None   # raises BuildError
class Shell: from_donor(html) ; render(title, description, og_image, content, before_body_end='')
def render_post(post: dict, shell: Shell) -> str
def render_list(posts: list[dict], shell: Shell) -> str
def patch_carousel(index_html: str, posts: list[dict]) -> str
def build(root: Path) -> dict   # {'written': [...], 'deleted': [...], 'unchanged': [...]}
def main(argv=None) -> int
```

- [ ] **Step 1: Тесты даты, сортировки, валидации**

```python
# tests/test_build_news.py
import importlib.util
import json
import os
import pathlib
import shutil
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_news', ROOT / 'scripts' / 'build_news.py')
bn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bn)


def post(**over):
    base = {'slug': 'test-post', 'title': 'Test', 'date': '2026-09-07', 'excerpt': '',
            'cover': 'images/nsu/news/test-post/cover.jpg', 'body': '<p>Body</p>',
            'gallery': [], 'updated': '2026-09-09T10:00:00Z'}
    base.update(over)
    return base


class DateTests(unittest.TestCase):
    def test_uzbek_format(self):
        self.assertEqual(bn.format_date_uz('2026-09-07'), '7-sentabr, 2026')
        self.assertEqual(bn.format_date_uz('2026-01-01'), '1-yanvar, 2026')
        self.assertEqual(bn.format_date_uz('2026-12-31'), '31-dekabr, 2026')

    def test_none_is_empty(self):
        self.assertEqual(bn.format_date_uz(None), '')

    def test_bad_date_raises(self):
        with self.assertRaises(bn.BuildError):
            bn.format_date_uz('07.09.2026')


class SortTests(unittest.TestCase):
    def test_dated_desc_then_undated_in_order(self):
        posts = [post(slug='u1', date=None), post(slug='old', date='2026-01-01'),
                 post(slug='u2', date=None), post(slug='new', date='2026-09-01')]
        self.assertEqual([p['slug'] for p in bn.sort_posts(posts)], ['new', 'old', 'u1', 'u2'])

    def test_same_date_uses_updated_desc(self):
        posts = [post(slug='a', updated='2026-09-09T08:00:00Z'),
                 post(slug='b', updated='2026-09-09T09:00:00Z')]
        self.assertEqual([p['slug'] for p in bn.sort_posts(posts)], ['b', 'a'])


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        (self.root / 'images/nsu/news/test-post').mkdir(parents=True)
        (self.root / 'images/nsu/news/test-post/cover.jpg').write_bytes(b'jpg')

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_ok(self):
        bn.validate_posts([post()], self.root)

    def test_duplicate_slug(self):
        with self.assertRaisesRegex(bn.BuildError, 'duplicate slug'):
            bn.validate_posts([post(), post()], self.root)

    def test_bad_slug(self):
        for bad in ['Test', 'a--b', '-a', 'a-', 'ё', 'x' * 81]:
            with self.assertRaisesRegex(bn.BuildError, 'slug'):
                bn.validate_posts([post(slug=bad)], self.root)

    def test_missing_cover(self):
        with self.assertRaisesRegex(bn.BuildError, 'cover'):
            bn.validate_posts([post(cover='images/nsu/news/test-post/nope.jpg')], self.root)

    def test_missing_gallery_file(self):
        with self.assertRaisesRegex(bn.BuildError, 'gallery'):
            bn.validate_posts([post(gallery=['images/nsu/news/test-post/g01.jpg'])], self.root)

    def test_missing_title(self):
        with self.assertRaisesRegex(bn.BuildError, 'title'):
            bn.validate_posts([post(title='  ')], self.root)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Запустить, убедиться, что падает**

Run: `python3 -m unittest tests.test_build_news -v 2>&1 | tail -3`
Expected: ошибка загрузки модуля (`FileNotFoundError` / `AttributeError`), тесты не проходят.

- [ ] **Step 3: Реализовать константы, дату, сортировку, валидацию**

```python
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
```

- [ ] **Step 4: Запустить тесты**

Run: `python3 -m unittest tests.test_build_news -v 2>&1 | tail -3`
Expected: `OK`, все тесты Date/Sort/Validate зелёные.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_news.py tests/__init__.py tests/test_build_news.py
git commit -m "feat(news): build_news.py skeleton with date formatting, ordering and validation"
```

---

### Task 3: Оболочка страницы из донора

**Files:**
- Modify: `scripts/build_news.py`
- Modify: `tests/test_build_news.py`

- [ ] **Step 1: Тесты оболочки**

Добавить в тесты фабрику синтетического донора и класс тестов:

```python
DONOR = '''<!DOCTYPE html><html><head>
\t<meta name="og:title" content="Bogʻlanish — NavDU">
\t<meta name="og:image" content="images/nsu/nsu-seal-navy.png">
\t<meta name="description" content="Biz bilan bogʻlanish.">
\t<title>Bogʻlanish — NavDU</title>
</head><body class="nsu-inner">
<a class="is-active" data-label="O‘zbekcha">UZ</a>
<a class="menu__link is-active" href="contact.html">Bogʻlanish</a>
<a class="menu__link" href="news.html">Yangiliklar</a>
<a class="mm__link" href="news.html">Yangiliklar</a>
\t\t\t\t<section id="sp-page-title" class="nsu-page-hero">OLD CONTENT</section><section id="sp-main-body">OLD</section><!-- ====== FOOTER (из Макета 2) ====== -->
<footer>F</footer>
<script src="assets/js/header.js"></script>
</body>
</html>
'''


class ShellTests(unittest.TestCase):
    def test_render_replaces_head_and_content(self):
        shell = bn.Shell.from_donor(DONOR)
        out = shell.render('T & Co', 'D "q"', 'images/c.jpg', '<section id="sp-page-title">NEW</section>')
        self.assertIn('<title>T &amp; Co — NavDU</title>', out)
        self.assertIn('<meta name="og:title" content="T &amp; Co — NavDU">', out)
        self.assertIn('<meta name="og:image" content="images/c.jpg">', out)
        self.assertIn('<meta name="description" content="D &quot;q&quot;">', out)
        self.assertIn('\t\t\t\t<section id="sp-page-title">NEW</section><!-- ====== FOOTER', out)
        self.assertNotIn('OLD', out)
        self.assertIn('<footer>F</footer>', out)

    def test_menu_active_moves_to_news(self):
        out = bn.Shell.from_donor(DONOR).render('T', 'D', 'i.jpg', '')
        self.assertIn('<a class="menu__link" href="contact.html">', out)
        self.assertIn('<a class="menu__link is-active" href="news.html">', out)
        self.assertIn('<a class="is-active" data-label="O‘zbekcha">', out)

    def test_before_body_end(self):
        out = bn.Shell.from_donor(DONOR).render('T', 'D', 'i.jpg', '', before_body_end='<script>X</script>')
        self.assertIn('<script>X</script>\n</body>', out)

    def test_missing_marker(self):
        with self.assertRaisesRegex(bn.BuildError, 'sp-page-title'):
            bn.Shell.from_donor(DONOR.replace('id="sp-page-title"', 'id="x"'))

    def test_duplicate_marker(self):
        with self.assertRaisesRegex(bn.BuildError, 'FOOTER'):
            bn.Shell.from_donor(DONOR + '<!-- ====== FOOTER')
```

- [ ] **Step 2: Запустить, убедиться, что падает**

Run: `python3 -m unittest tests.test_build_news.ShellTests -v 2>&1 | tail -3`
Expected: `AttributeError: module 'build_news' has no attribute 'Shell'`.

- [ ] **Step 3: Реализовать `Shell`**

```python
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
    """Everything of a site page except its content: head + header + footer."""

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
```

`lambda m:` в заменах нужен, чтобы `\` и `&` в заголовках не трактовались как ссылки на группы.

- [ ] **Step 4: Запустить тесты**

Run: `python3 -m unittest tests.test_build_news -v 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_news.py tests/test_build_news.py
git commit -m "feat(news): derive the page shell from contact.html"
```

---

### Task 4: Рендер страницы поста, списка и карусели

**Files:**
- Modify: `scripts/build_news.py`
- Modify: `tests/test_build_news.py`

- [ ] **Step 1: Тесты рендера**

```python
class RenderTests(unittest.TestCase):
    def setUp(self):
        self.shell = bn.Shell.from_donor(DONOR)

    def test_post_page(self):
        p = post(title='A & B', excerpt='Ex', gallery=['images/nsu/news/test-post/g01.jpg'])
        out = bn.render_post(p, self.shell)
        self.assertIn('<title>A &amp; B — NavDU</title>', out)
        self.assertIn('background-image:url(images/nsu/news/test-post/cover.jpg)', out)
        self.assertIn('<h1>A &amp; B</h1>', out)
        self.assertIn('<a href="news.html">Yangiliklar</a>', out)
        self.assertIn('7-sentabr, 2026', out)
        self.assertIn('<span class="nsu-post-views" hidden>', out)
        self.assertIn('data-views="test-post"', out)
        self.assertIn('<div class="nsu-post-body"><p>Body</p></div>', out)
        self.assertIn('<div class="nsu-post-gallery">', out)
        self.assertIn('href="images/nsu/news/test-post/g01.jpg"', out)
        self.assertIn("fetch('views/hit'", out)
        self.assertIn('<meta name="description" content="Ex">', out)
        self.assertIn('<meta name="og:image" content="images/nsu/news/test-post/cover.jpg">', out)
        self.assertIn('Savolingiz yoki taklifingiz bormi?', out)

    def test_post_without_date_and_gallery(self):
        out = bn.render_post(post(date=None, excerpt=''), self.shell)
        self.assertNotIn('nsu-post-date', out)
        self.assertNotIn('nsu-post-gallery', out)
        self.assertIn('<meta name="description" content="Test">', out)

    def test_list_order_tag_and_excerpt(self):
        posts = [post(slug='old', title='Old', date='2026-01-01', excerpt='E1'),
                 post(slug='new', title='New', date='2026-09-01', excerpt=''),
                 post(slug='und', title='Und', date=None)]
        out = bn.render_list(posts, self.shell)
        self.assertLess(out.index('news-new.html'), out.index('news-old.html'))
        self.assertLess(out.index('news-old.html'), out.index('news-und.html'))
        self.assertIn('<span class="nsu-news-tag">1-sentabr, 2026</span><h4>New</h4></div>', out)
        self.assertIn('<span class="nsu-news-tag">YANGILIKLAR</span><h4>Und</h4>', out)
        self.assertIn('<h4>Old</h4><p>E1</p>', out)
        self.assertIn('<title>Yangiliklar va e’lonlar — NavDU</title>', out)

    def test_carousel_replaces_only_marked_block(self):
        index = 'BEFORE<!-- news:carousel -->old stuff<!-- /news:carousel -->AFTER'
        posts = [post(slug=f'p{i}', title=f'P{i}', date=f'2026-01-{i + 1:02d}') for i in range(8)]
        out = bn.patch_carousel(index, posts)
        self.assertTrue(out.startswith('BEFORE<!-- news:carousel -->'))
        self.assertTrue(out.endswith('<!-- /news:carousel -->AFTER'))
        self.assertNotIn('old stuff', out)
        self.assertEqual(out.count('role="article"'), 6)
        self.assertLess(out.index('news-p7.html'), out.index('news-p2.html'))
        self.assertNotIn('news-p1.html', out)

    def test_carousel_marker_missing(self):
        with self.assertRaisesRegex(bn.BuildError, 'news:carousel'):
            bn.patch_carousel('no markers', [post()])
```

- [ ] **Step 2: Запустить, убедиться, что падает**

Run: `python3 -m unittest tests.test_build_news.RenderTests -v 2>&1 | tail -3`
Expected: `AttributeError ... render_post`.

- [ ] **Step 3: Реализовать рендер**

Разметка внутренних обёрток скопирована с нынешних страниц (SP Page Builder), чтобы работали существующие стили.

```python
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
```

- [ ] **Step 4: Запустить тесты**

Run: `python3 -m unittest tests.test_build_news -v 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_news.py tests/test_build_news.py
git commit -m "feat(news): render post pages, the listing and the home carousel"
```

---

### Task 5: `build()` и `main()`, маркеры в `index.html`, переход на генерацию

**Files:**
- Modify: `scripts/build_news.py`
- Modify: `tests/test_build_news.py`
- Modify: `index.html` (маркеры вокруг карусели)
- Modify: `.gitignore`
- Delete from git: `news.html`, `news-*.html` (12 файлов)

- [ ] **Step 1: Тесты `build()`**

```python
class BuildTests(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        (self.root / 'content').mkdir()
        (self.root / 'images/nsu/news/a').mkdir(parents=True)
        (self.root / 'images/nsu/news/a/cover.jpg').write_bytes(b'x')
        (self.root / 'images/nsu/news').joinpath('campus.jpg').write_bytes(b'x')
        (self.root / 'contact.html').write_text(DONOR, encoding='utf-8')
        (self.root / 'index.html').write_text(
            'X<!-- news:carousel -->old<!-- /news:carousel -->Y', encoding='utf-8')
        self.write_posts([post(slug='a', cover='images/nsu/news/a/cover.jpg')])

    def tearDown(self):
        shutil.rmtree(self.root)

    def write_posts(self, posts):
        (self.root / 'content/news.json').write_text(
            json.dumps({'posts': posts}, ensure_ascii=False), encoding='utf-8')

    def test_writes_pages_and_patches_index(self):
        result = bn.build(self.root)
        self.assertEqual(sorted(result['written']), ['index.html', 'news-a.html', 'news.html'])
        self.assertIn('data-views="a"', (self.root / 'news-a.html').read_text(encoding='utf-8'))
        index = (self.root / 'index.html').read_text(encoding='utf-8')
        self.assertTrue(index.startswith('X<!-- news:carousel --><div role="article"'))
        self.assertTrue(index.endswith('<!-- /news:carousel -->Y'))

    def test_second_run_changes_nothing(self):
        bn.build(self.root)
        before = {p.name: p.read_bytes() for p in self.root.glob('*.html')}
        result = bn.build(self.root)
        self.assertEqual(result['written'], [])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.glob('*.html')})

    def test_stale_post_page_is_deleted(self):
        (self.root / 'news-gone.html').write_text('stale', encoding='utf-8')
        result = bn.build(self.root)
        self.assertEqual(result['deleted'], ['news-gone.html'])
        self.assertFalse((self.root / 'news-gone.html').exists())

    def test_invalid_data_is_a_build_error(self):
        self.write_posts([post(slug='a', cover='missing.jpg')])
        with self.assertRaises(bn.BuildError):
            bn.build(self.root)

    def test_main_reports_error_without_traceback(self):
        self.write_posts([post(slug='Bad Slug', cover='images/nsu/news/a/cover.jpg')])
        with self.assertRaises(SystemExit) as cm:
            bn.main(['--root', str(self.root)])
        self.assertIn('slug', str(cm.exception))
```

- [ ] **Step 2: Запустить, убедиться, что падает**

Run: `python3 -m unittest tests.test_build_news.BuildTests -v 2>&1 | tail -3`
Expected: `AttributeError ... build`.

- [ ] **Step 3: Реализовать `build()` и `main()`**

```python
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
```

- [ ] **Step 4: Запустить тесты**

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 5: Поставить маркеры в `index.html`**

Карусель — строка 605, одиннадцать `<div role="article" class="sppb-articles-carousel-column ">…</div>` подряд внутри `<div class="sppb-articles-carousel …" data-pager="true">`. Вставить `<!-- news:carousel -->` перед первым `<div role="article"` и `<!-- /news:carousel -->` сразу после закрывающего `</div>` одиннадцатого элемента (перед `</div>` контейнера карусели). Сделать скриптом, а не руками:

```python
import re
p = 'index.html'
s = open(p, encoding='utf-8').read()
assert s.count('<!-- news:carousel -->') == 0
first = s.index('<div role="article" class="sppb-articles-carousel-column ">')
# the carousel container closes right after the last column: find the last column start,
# then the end of that column = the next occurrence of the container's closing sequence
last = s.rindex('<div role="article" class="sppb-articles-carousel-column ">')
end = s.index('</div></div></div>', last) + len('</div></div></div>')  # img+content+column wrappers
s = s[:first] + '<!-- news:carousel -->' + s[first:end] + '<!-- /news:carousel -->' + s[end:]
open(p, 'w', encoding='utf-8').write(s)
```

Проверить: `grep -o '<!-- /news:carousel -->.\{0,60\}' index.html` должен показать закрывающий `</div>` контейнера карусели после маркера, а `grep -c 'role="article"' index.html` по-прежнему 11 (структура одной колонки: `<div role=article><div img>…</div><div content>…</div></div>` — три `</div>` подряд закрывают content, column; убедиться визуально, что срез попал между `</div></div>` колонки и `</div>` контейнера; если после `content` идут ещё вложенности, поправить смещение).

- [ ] **Step 6: Собрать реальный сайт и сравнить с нынешними страницами**

Run: `python3 scripts/build_news.py && git status --short | head -20`
Expected: `written: 13` (11 постов + `news.html` + `index.html`). `git diff --stat index.html` — изменена только строка карусели; `git diff news.html | head -40` — отличия только в разметке hero/крошек/дат, шапка и подвал не менялись.

Run: `python3 scripts/check_links.py`
Expected: `OK`, `errors : 0`.

- [ ] **Step 7: Убрать сгенерированные страницы из git**

```bash
git rm --cached -q news.html news-*.html
printf '\n# generated by scripts/build_news.py\nnews.html\nnews-*.html\n' >> .gitignore
git status --short | head
```

Expected: 12 файлов `D`, `.gitignore` и `index.html` `M`, файлы физически на месте.

- [ ] **Step 8: Локальная проверка в браузере**

Run: `python3 -m http.server 8899` (в фоне), открыть `http://localhost:8899/news.html` и `http://localhost:8899/news-new-laboratory-opened.html`. Шапка, меню (активен «Yangiliklar»), подвал на месте; крошки `Bosh sahifa / Yangiliklar`; блок просмотров скрыт (счётчика локально нет). Главная: карусель с 6 карточками.

- [ ] **Step 9: Commit**

```bash
git add scripts/build_news.py tests/test_build_news.py index.html .gitignore
git commit -m "feat(news): generate the news pages from content/news.json

news.html and news-*.html are build output now; scripts/build_news.py
produces them from content/news.json using contact.html as the shell and
rewrites the carousel block on the home page. The old hand-generated pages
leave the repository, their URLs do not change."
```

---

### Task 6: Стили страницы поста

**Files:**
- Modify: `assets/css/nsu.css` (после блока `.nsu-news-body p`, строка ~141)

- [ ] **Step 1: Добавить стили**

```css
/* ---------------------------------------------------------- news post */
.nsu-post-meta{position:relative;z-index:2;margin:14px 0 0;font-size:14px;color:rgba(255,255,255,.8);letter-spacing:.3px}
.nsu-post-meta .nsu-post-date+.nsu-post-views::before{content:"·";margin:0 10px;opacity:.6}
.nsu-post-body{font-size:17px;line-height:1.75;color:var(--nsu-text);max-width:860px}
.nsu-post-body p{margin:0 0 18px}
.nsu-post-body h2,.nsu-post-body h3{color:var(--nsu-primary);font-weight:700;line-height:1.3;margin:32px 0 14px}
.nsu-post-body h2{font-size:26px}
.nsu-post-body h3{font-size:21px}
.nsu-post-body ul,.nsu-post-body ol{margin:0 0 18px 22px;padding:0}
.nsu-post-body li{margin:0 0 6px}
.nsu-post-body blockquote{margin:24px 0;padding:14px 20px;border-left:4px solid var(--nsu-accent);background:var(--nsu-light);color:var(--nsu-muted)}
.nsu-post-body a{color:var(--nsu-primary);text-decoration:underline}
.nsu-post-body img{display:block;max-width:100%;height:auto;border-radius:4px;margin:24px 0}
.nsu-post-gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;margin:36px 0 8px}
.nsu-post-gallery a{display:block;aspect-ratio:4/3;overflow:hidden;border-radius:4px;border:1px solid var(--nsu-border)}
.nsu-post-gallery img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .3s}
.nsu-post-gallery a:hover img{transform:scale(1.04)}
```

- [ ] **Step 2: Проверить локально и перештамповать**

Открыть страницу поста и `news.html` в браузере на 375 и 1280 px: мета-строка под заголовком читается на тёмном hero, тело без переполнения. Затем: `python3 scripts/stamp_assets.py` (штамп `nsu.css` меняется во всех страницах) и `git status --short | wc -l` — около 96 страниц `M` плюс сгенерированные (их git не видит).

- [ ] **Step 3: Commit**

```bash
git add -A assets/css/nsu.css *.html
git commit -m "feat(news): styles for the post meta line, body, and gallery"
```

---

### Task 7: Сервис счётчика `deploy/counter/counter.py`

**Files:**
- Create: `deploy/counter/counter.py`
- Create: `tests/test_counter.py`

- [ ] **Step 1: Тесты через реальный HTTP**

```python
# tests/test_counter.py
import importlib.util
import json
import pathlib
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('counter', ROOT / 'deploy' / 'counter' / 'counter.py')
counter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(counter)

UA = 'Mozilla/5.0 (test)'


class CounterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp())
        cls.server = counter.make_server('127.0.0.1', 0, cls.tmp / 'views.db')
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp)

    def call(self, method, path, body=None, ua=UA, xff='10.0.0.1'):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header('Content-Type', 'application/json')
        if ua is not None:
            req.add_header('User-Agent', ua)
        if xff:
            req.add_header('X-Forwarded-For', xff)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read()
                return resp.status, dict(resp.headers), json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), None

    def test_hit_counts_once_per_visitor_per_day(self):
        self.assertEqual(self.call('POST', '/hit', {'slug': 'once'})[2], {'slug': 'once', 'count': 1})
        self.assertEqual(self.call('POST', '/hit', {'slug': 'once'})[2]['count'], 1)
        self.assertEqual(self.call('POST', '/hit', {'slug': 'once'}, ua='Other/1.0')[2]['count'], 2)
        self.assertEqual(self.call('POST', '/hit', {'slug': 'once'}, xff='10.0.0.2, 1.1.1.1')[2]['count'], 3)

    def test_bots_do_not_count(self):
        self.call('POST', '/hit', {'slug': 'bots'})
        for ua in ['Googlebot/2.1', 'python-requests/2.0', 'curl/8.0', '']:
            status, _, body = self.call('POST', '/hit', {'slug': 'bots'}, ua=ua)
            self.assertEqual((status, body['count']), (200, 1), ua)

    def test_validation(self):
        self.assertEqual(self.call('POST', '/hit', {'slug': 'Bad Slug'})[0], 400)
        self.assertEqual(self.call('POST', '/hit', {'nope': 1})[0], 400)
        self.assertEqual(self.call('POST', '/hit', {'slug': 'x' * 2000})[0], 413)
        self.assertEqual(self.call('GET', '/nothing')[0], 404)
        self.assertEqual(self.call('POST', '/counts')[0], 405)

    def test_reads(self):
        self.call('POST', '/hit', {'slug': 'read-me'})
        self.assertEqual(self.call('GET', '/count/read-me')[2], {'slug': 'read-me', 'count': 1})
        self.assertEqual(self.call('GET', '/count/never')[2], {'slug': 'never', 'count': 0})
        self.assertEqual(self.call('GET', '/counts')[2]['read-me'], 1)
        status, headers, _ = self.call('GET', '/health')
        self.assertEqual(status, 200)

    def test_headers_and_preflight(self):
        status, headers, _ = self.call('GET', '/counts')
        self.assertEqual(headers['Access-Control-Allow-Origin'], '*')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertTrue(headers['Content-Type'].startswith('application/json'))
        status, headers, _ = self.call('OPTIONS', '/hit')
        self.assertEqual(status, 204)
        self.assertIn('POST', headers['Access-Control-Allow-Methods'])

    def test_persists_across_restart(self):
        self.call('POST', '/hit', {'slug': 'persist'})
        other = counter.make_server('127.0.0.1', 0, self.tmp / 'views.db')
        try:
            self.assertEqual(other.store.count('persist'), 1)
        finally:
            other.server_close()


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Запустить, убедиться, что падает**

Run: `python3 -m unittest tests.test_counter -v 2>&1 | tail -3`
Expected: `FileNotFoundError` на импорте.

- [ ] **Step 3: Реализовать сервис**

```python
#!/usr/bin/env python3
"""View counter for the NDU news pages.

A tiny HTTP service: standard library only, SQLite on disk. nginx mounts it
under /views/ (the prefix is stripped), so the site calls views/hit from the
page and the admin reads views/counts.

    POST /hit          {"slug": "..."} -> {"slug": "...", "count": N}
    GET  /count/<slug>                  -> {"slug": "...", "count": N}
    GET  /counts                        -> {"<slug>": N, ...}
    GET  /health                        -> {"status": "ok"}

One view per (slug, visitor, UTC day); the visitor is a hash of the client IP
and User-Agent, never stored in the clear. Crawlers are recognised by their
User-Agent and get the current value without incrementing it.

Environment: COUNTER_DB (default /data/views.db), COUNTER_PORT (default 8080).
"""
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SLUG_RE = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
SLUG_MAX = 80
BODY_MAX = 1024
BOT_RE = re.compile(r'bot|crawl|spider|slurp|preview|headless|python-requests|curl|wget|fetch|monitor',
                    re.I)
SEEN_TTL_DAYS = 2


class Store:
    """All SQLite access, serialised by one lock."""

    def __init__(self, path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS views (slug TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS seen (slug TEXT NOT NULL, visitor TEXT NOT NULL, day TEXT NOT NULL,
                                                 PRIMARY KEY (slug, visitor, day));
            ''')
            self.db.commit()
        self.purge()

    def hit(self, slug, visitor, day):
        with self.lock:
            cur = self.db.execute('INSERT OR IGNORE INTO seen (slug, visitor, day) VALUES (?, ?, ?)',
                                  (slug, visitor, day))
            if cur.rowcount == 1:
                self.db.execute('INSERT INTO views (slug, count) VALUES (?, 1) '
                                'ON CONFLICT(slug) DO UPDATE SET count = count + 1', (slug,))
            self.db.commit()
            return self._count(slug)

    def count(self, slug):
        with self.lock:
            return self._count(slug)

    def _count(self, slug):
        row = self.db.execute('SELECT count FROM views WHERE slug = ?', (slug,)).fetchone()
        return row[0] if row else 0

    def counts(self):
        with self.lock:
            return dict(self.db.execute('SELECT slug, count FROM views ORDER BY slug'))

    def purge(self):
        cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=SEEN_TTL_DAYS)).date().isoformat()
        with self.lock:
            self.db.execute('DELETE FROM seen WHERE day < ?', (cutoff,))
            self.db.commit()


def visitor_id(ip, user_agent):
    return hashlib.sha256(f'{ip}|{user_agent}'.encode('utf-8', 'replace')).hexdigest()[:32]


class Handler(BaseHTTPRequestHandler):
    server_version = 'ndu-counter/1'

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.cors()
        self.end_headers()
        self.wfile.write(body)

    def cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store')

    def client_ip(self):
        forwarded = self.headers.get('X-Forwarded-For', '')
        return forwarded.split(',')[0].strip() or self.client_address[0]

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        store = self.server.store
        if self.path == '/health':
            return self.send_json(200, {'status': 'ok'})
        if self.path == '/counts':
            return self.send_json(200, store.counts())
        if self.path.startswith('/count/'):
            slug = self.path[len('/count/'):]
            if not SLUG_RE.match(slug) or len(slug) > SLUG_MAX:
                return self.send_json(400, {'error': 'bad slug'})
            return self.send_json(200, {'slug': slug, 'count': store.count(slug)})
        self.send_json(404, {'error': 'not found'})

    def do_POST(self):
        if self.path != '/hit':
            return self.send_json(405 if self.path in ('/counts', '/health') else 404, {'error': 'not found'})
        length = int(self.headers.get('Content-Length') or 0)
        if length > BODY_MAX:
            return self.send_json(413, {'error': 'body too large'})
        try:
            data = json.loads(self.rfile.read(length) or b'{}')
        except ValueError:
            return self.send_json(400, {'error': 'bad json'})
        slug = data.get('slug') if isinstance(data, dict) else None
        if not isinstance(slug, str) or not SLUG_RE.match(slug) or len(slug) > SLUG_MAX:
            return self.send_json(400, {'error': 'bad slug'})
        ua = self.headers.get('User-Agent', '')
        store = self.server.store
        if not ua or BOT_RE.search(ua):
            return self.send_json(200, {'slug': slug, 'count': store.count(slug)})
        day = dt.datetime.now(dt.timezone.utc).date().isoformat()
        count = store.hit(slug, visitor_id(self.client_ip(), ua), day)
        self.send_json(200, {'slug': slug, 'count': count})

    def log_message(self, fmt, *args):
        sys.stdout.write('%s %s %s\n' % (self.log_date_time_string(), self.client_ip(), fmt % args))
        sys.stdout.flush()


def make_server(host, port, db_path):
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.store = Store(db_path)
    return server


def purge_forever(store, interval=3600):
    while True:
        time.sleep(interval)
        store.purge()


def main():
    db_path = os.environ.get('COUNTER_DB', '/data/views.db')
    port = int(os.environ.get('COUNTER_PORT', '8080'))
    server = make_server('0.0.0.0', port, db_path)
    threading.Thread(target=purge_forever, args=(server.store,), daemon=True).start()
    print(f'ndu-counter listening on :{port}, db {db_path}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Запустить тесты**

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -3`
Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add deploy/counter/counter.py tests/test_counter.py
git commit -m "feat(views): stdlib+SQLite view counter service with tests"
```

---

### Task 8: Контейнер счётчика и проксирование в nginx

**Files:**
- Modify: `deploy/docker-compose.yml`
- Modify: `deploy/nginx-site.conf`
- Modify: `deploy/README.md`

- [ ] **Step 1: compose**

Добавить в `services` после `web`, а `web` дополнить `depends_on`:

```yaml
services:
  web:
    # ... как было ...
    depends_on:
      - counter

  counter:
    # View counter for the news pages (deploy/counter/counter.py).
    # Reachable only from the web container as http://counter:8080/;
    # nginx publishes it under /views/. No host port on purpose.
    image: python:3.12-alpine
    container_name: ndu-counter
    restart: unless-stopped
    command: ["python", "-u", "/app/counter.py"]
    environment:
      COUNTER_DB: /data/views.db
    volumes:
      - ./counter/counter.py:/app/counter.py:ro
      - ndu-counter-data:/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=3).status==200 else 1)"]
      interval: 30s
      timeout: 5s
      retries: 3

volumes:
  ndu-counter-data:
```

- [ ] **Step 2: nginx**

Перед `location / {` в `deploy/nginx-site.conf`:

```nginx
    # View counter (deploy/counter/counter.py). Same origin as the pages, so
    # no CORS or mixed-content issues; the /views/ prefix is stripped.
    location /views/ {
        proxy_pass         http://counter:8080/;
        proxy_set_header   X-Forwarded-For $remote_addr;
        proxy_set_header   Host $host;
        proxy_read_timeout 10s;
    }
```

- [ ] **Step 3: Проверить синтаксис, если есть docker**

Run: `cd deploy && docker compose config -q && cd ..`
Expected: без вывода. Если docker локально нет — пропустить, проверит CI (`nginx -t` в деплое).

- [ ] **Step 4: `deploy/README.md`**

Добавить раздел «Счётчик просмотров»: контейнер `ndu-counter`, том `ndu-counter-data` (`docker volume inspect ndu-counter-data` → путь; бэкап — `docker cp ndu-counter:/data/views.db ./views.db`), логи `docker logs -f ndu-counter`, проверка `curl http://127.0.0.1:8083/views/health`. В раздел «Правило: ничего на сервере не удаляем» дописать единственное исключение: второй rsync с `--delete`, ограниченный маской `news-*.html`, убирает страницы удалённых постов.

- [ ] **Step 5: Commit**

```bash
git add deploy/
git commit -m "feat(views): ndu-counter container and /views/ proxy in the ndu-static stack"
```

---

### Task 9: CI/CD

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/deploy.yml`

- [ ] **Step 1: `ci.yml` — новый порядок шагов**

Заменить шаги задачи `validate` на:

```yaml
    steps:
      - uses: actions/checkout@v4

      - name: Unit tests (news build, view counter)
        run: python3 -m unittest discover -s tests -v

      - name: Asset cache stamps are current
        # Runs on the pristine checkout, before the build touches index.html.
        run: |
          python3 scripts/stamp_assets.py
          if ! git diff --quiet; then
            echo "::error::CSS/JS ?v= stamps are stale - run scripts/stamp_assets.py and commit."
            git --no-pager diff --stat
            exit 1
          fi

      - name: Build news pages
        run: |
          python3 scripts/build_news.py
          python3 scripts/stamp_assets.py

      - name: Every internal link and asset resolves
        run: python3 scripts/check_links.py

      - name: Site inventory
        run: |
          echo "html pages: $(ls *.html | wc -l)"
          du -sh .
```

- [ ] **Step 2: `deploy.yml` — сборка в `deploy` и `pages`, точечное удаление, каталог `deploy/`, health счётчика**

В задаче `deploy` сразу после `actions/checkout@v4`:

```yaml
      - name: Build news pages
        run: |
          python3 scripts/build_news.py
          python3 scripts/stamp_assets.py
```

Шаг `Upload site`: к `--exclude` добавить `content`, `tests`, `docs`; после основного rsync добавить:

```bash
          # The only deletion the deploy ever performs: pages of posts that
          # were removed from content/news.json. The filter limits --delete
          # to news-*.html; nothing else on the server is touched.
          rsync -av --delete --include='news-*.html' --exclude='*' \
            -e "ssh -i ~/.ssh/deploy_key -p ${PORT:-22}" \
            ./ "${USER:-root}@$HOST:$DEST/"
```

Шаг `Sync container config and reconcile`: вместо трёх файлов синхронизировать каталог:

```bash
          rsync -avz --inplace -e "ssh -i ~/.ssh/deploy_key -p ${PORT:-22}" \
            deploy/ "${USER:-root}@$HOST:/opt/ndu-static/"
```

(без `--delete`; `deploy/README.md` тоже уедет на сервер, это нормально.)

Шаг `Verify site responds`: после проверки главной добавить:

```bash
          code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "${{ vars.SITE_URL }}/views/health")
          echo "GET ${{ vars.SITE_URL }}/views/health -> $code"
          [ "$code" = "200" ] || { echo "::error::view counter did not return 200"; exit 1; }
```

В задаче `pages` после `actions/checkout@v4` — тот же шаг `Build news pages`.

- [ ] **Step 3: Проверить YAML**

Run: `ruby -ryaml -e 'YAML.load_file(".github/workflows/ci.yml"); YAML.load_file(".github/workflows/deploy.yml"); puts "yaml ok"'`
Expected: `yaml ok`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/
git commit -m "ci: run unit tests, build the news pages in every job, deploy the counter"
```

---

### Task 10: Админка — вендор Quill, разметка, вспомогательные модули

**Files:**
- Create: `admin/vendor/quill.js`, `admin/vendor/quill.snow.css`
- Create: `admin/index.html`, `admin/admin.css`
- Create: `admin/slug.js`, `admin/images.js`, `admin/github.js`

- [ ] **Step 1: Вендорить Quill 2.0.3**

```bash
mkdir -p admin/vendor
curl -sSL -o admin/vendor/quill.js https://cdn.jsdelivr.net/npm/quill@2.0.3/dist/quill.js
curl -sSL -o admin/vendor/quill.snow.css https://cdn.jsdelivr.net/npm/quill@2.0.3/dist/quill.snow.css
head -c 120 admin/vendor/quill.js; echo; wc -c admin/vendor/quill.js admin/vendor/quill.snow.css
```

Expected: заголовок `/*! Quill Editor v2.0.3 …`, ~209 КБ и ~25 КБ.

- [ ] **Step 2: `admin/slug.js`**

```javascript
// slugify(title) -> URL slug matching SLUG_RE in scripts/build_news.py.
// Uzbek Latin apostrophes are dropped (oʻquv -> oquv); Cyrillic is transliterated
// so a Russian or Uzbek-Cyrillic title still yields a usable slug.
const APOSTROPHES = /[ʻʼ’‘'`´ʹ]/g;
const CYR = {
  а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'yo', ж: 'j', з: 'z', и: 'i', й: 'y', к: 'k',
  л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u', ф: 'f', х: 'x', ц: 'ts',
  ч: 'ch', ш: 'sh', щ: 'sh', ъ: '', ы: 'i', ь: '', э: 'e', ю: 'yu', я: 'ya',
  ў: 'o', қ: 'q', ғ: 'g', ҳ: 'h',
};
export const SLUG_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;
export const SLUG_MAX = 80;

export function slugify(title) {
  let s = (title || '').toLowerCase().replace(APOSTROPHES, '');
  s = s.replace(/[а-яёўқғҳ]/g, (ch) => CYR[ch] ?? '');
  s = s.normalize('NFKD').replace(/[̀-ͯ]/g, '');
  s = s.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  if (s.length > SLUG_MAX) s = s.slice(0, SLUG_MAX).replace(/-+$/g, '');
  return s;
}

export function isValidSlug(s) {
  return typeof s === 'string' && s.length <= SLUG_MAX && SLUG_RE.test(s);
}
```

Проверка в консоли браузера после подключения: `slugify("2026-2027 oʻquv yili ochildi")` → `2026-2027-oquv-yili-ochildi`; `slugify("Talabalar sport festivali bo'lib o'tdi")` → `talabalar-sport-festivali-bolib-otdi`; `slugify("Новая лаборатория")` → `novaya-laboratoriya`.

- [ ] **Step 3: `admin/images.js`**

```javascript
// Client-side image preparation: resize to MAX_SIDE, encode as JPEG, base64 for the GitHub API.
export const MAX_SIDE = 1600;
export const QUALITY = 0.82;

export async function prepareImage(file) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const w = Math.round(bitmap.width * scale);
  const h = Math.round(bitmap.height * scale);
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#fff';           // flatten transparency (PNG) onto white
  ctx.fillRect(0, 0, w, h);
  ctx.drawImage(bitmap, 0, 0, w, h);
  bitmap.close?.();
  const blob = await new Promise((res) => canvas.toBlob(res, 'image/jpeg', QUALITY));
  return { blob, width: w, height: h, url: URL.createObjectURL(blob) };
}

export function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
```

- [ ] **Step 4: `admin/github.js`**

```javascript
// Thin GitHub REST client + "one commit per action" through the Git Data API.
export const OWNER = 'BekkiBay';
export const REPO = 'ndu';
export const NEWS_PATH = 'content/news.json';
const API = 'https://api.github.com';

export class GitHubError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

export class GitHub {
  constructor(token, branch = 'main') { this.token = token; this.branch = branch; }

  async api(method, path, body) {
    const resp = await fetch(API + path, {
      method,
      headers: {
        Authorization: `Bearer ${this.token}`,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (resp.status === 204) return null;
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new GitHubError(resp.status, data.message || `GitHub ${resp.status}`);
    return data;
  }

  repo() { return this.api('GET', `/repos/${OWNER}/${REPO}`); }

  // Latest commit on the branch and the news.json it contains.
  async head() {
    const ref = await this.api('GET', `/repos/${OWNER}/${REPO}/git/ref/heads/${this.branch}`);
    const commit = await this.api('GET', `/repos/${OWNER}/${REPO}/git/commits/${ref.object.sha}`);
    return { commitSha: ref.object.sha, treeSha: commit.tree.sha };
  }

  async readNews(commitSha) {
    const file = await this.api('GET', `/repos/${OWNER}/${REPO}/contents/${NEWS_PATH}?ref=${commitSha}`);
    const text = new TextDecoder().decode(Uint8Array.from(atob(file.content.replace(/\n/g, '')), (c) => c.charCodeAt(0)));
    return JSON.parse(text);
  }

  // files: [{path, content (utf-8 string) | base64 (string) | delete: true}]
  async commit(message, mutate, files) {
    for (let attempt = 0; attempt < 2; attempt++) {
      const { commitSha, treeSha } = await this.head();
      const news = await this.readNews(commitSha);
      const next = mutate(structuredClone(news));           // caller applies the change to the fresh JSON
      const tree = [{
        path: NEWS_PATH, mode: '100644', type: 'blob',
        content: JSON.stringify(next, null, 2) + '\n',
      }];
      for (const f of files) {
        if (f.delete) { tree.push({ path: f.path, mode: '100644', type: 'blob', sha: null }); continue; }
        const blob = await this.api('POST', `/repos/${OWNER}/${REPO}/git/blobs`, { content: f.base64, encoding: 'base64' });
        tree.push({ path: f.path, mode: '100644', type: 'blob', sha: blob.sha });
      }
      const newTree = await this.api('POST', `/repos/${OWNER}/${REPO}/git/trees`, { base_tree: treeSha, tree });
      const newCommit = await this.api('POST', `/repos/${OWNER}/${REPO}/git/commits`,
        { message, tree: newTree.sha, parents: [commitSha] });
      try {
        await this.api('PATCH', `/repos/${OWNER}/${REPO}/git/refs/heads/${this.branch}`, { sha: newCommit.sha, force: false });
        return { sha: newCommit.sha, news: next };
      } catch (e) {
        if (attempt === 0 && (e.status === 409 || e.status === 422)) continue;   // branch moved: retry once from the new head
        throw e;
      }
    }
  }

  // Files under a directory of the repo (to delete a post's image folder); [] when it does not exist.
  async listDir(path) {
    try {
      const items = await this.api('GET', `/repos/${OWNER}/${REPO}/contents/${path}?ref=${this.branch}`);
      return Array.isArray(items) ? items.map((i) => i.path) : [];
    } catch (e) {
      if (e.status === 404) return [];
      throw e;
    }
  }

  latestRun() {
    return this.api('GET', `/repos/${OWNER}/${REPO}/actions/runs?branch=${this.branch}&per_page=1`)
      .then((d) => d.workflow_runs?.[0] || null);
  }
}
```

Замечание про удаление файлов: Git Data API принимает `sha: null` в записи дерева — файл удаляется из `base_tree`. Если удаляемого файла нет, GitHub отвечает 422 — поэтому список на удаление всегда строится из `listDir()` и фактического содержимого поста, а не из догадок.

- [ ] **Step 5: `admin/index.html` и `admin/admin.css`**

Разметка — три экрана в одном документе, переключаются атрибутом `hidden`:

```html
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>NavDU · Yangiliklar — админка</title>
<link rel="icon" href="../images/nsu/nsu-seal-navy.png" type="image/png">
<link rel="stylesheet" href="vendor/quill.snow.css">
<link rel="stylesheet" href="admin.css">
</head>
<body>
<header class="top">
  <a class="brand" href="../news.html" target="_blank" rel="noopener">NavDU · Yangiliklar</a>
  <div class="deploy" id="deploy" hidden></div>
  <button class="link" id="logout" hidden>Выйти</button>
</header>

<main>
  <section id="screen-login" class="card narrow">
    <h1>Вход</h1>
    <p>Нужен GitHub fine-grained token с доступом только к репозиторию <code>BekkiBay/ndu</code>:
       Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token.
       Repository access: <b>Only select repositories → BekkiBay/ndu</b>.
       Permissions: <b>Contents — Read and write</b>, <b>Actions — Read-only</b>.</p>
    <form id="login-form">
      <label>Токен <input type="password" id="token" autocomplete="off" required></label>
      <button type="submit" class="primary">Войти</button>
      <p class="error" id="login-error" hidden></p>
    </form>
    <p class="muted">Токен хранится только в этом браузере (localStorage) и отправляется только на api.github.com.</p>
  </section>

  <section id="screen-list" hidden>
    <div class="bar">
      <h1>Посты <span class="muted" id="count"></span></h1>
      <button class="primary" id="new-post">+ Новый пост</button>
    </div>
    <p class="notice" id="notice" hidden></p>
    <table class="posts">
      <thead><tr><th></th><th>Заголовок</th><th>Дата</th><th>Просмотры</th><th></th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </section>

  <section id="screen-edit" hidden>
    <div class="bar">
      <h1 id="edit-title">Новый пост</h1>
      <button class="link" id="back">← К списку</button>
    </div>
    <div class="editor">
      <form id="post-form" novalidate>
        <label>Заголовок <input id="f-title" required maxlength="200"></label>
        <div class="row2">
          <label>Дата <input type="date" id="f-date"></label>
          <label>Slug <input id="f-slug" pattern="[a-z0-9]+(-[a-z0-9]+)*" maxlength="80" spellcheck="false">
            <small class="muted">news-<span id="slug-preview">…</span>.html</small></label>
        </div>
        <label>Анонс <textarea id="f-excerpt" rows="3" maxlength="300"></textarea>
          <small class="muted"><span id="excerpt-len">0</span>/300</small></label>
        <div class="field">
          <span class="label">Обложка</span>
          <div class="cover"><img id="cover-preview" alt="" hidden>
            <label class="button">Выбрать файл <input type="file" id="f-cover" accept="image/*" hidden></label></div>
        </div>
        <div class="field">
          <span class="label">Текст</span>
          <div id="quill"></div>
        </div>
        <div class="field">
          <span class="label">Галерея</span>
          <div class="gallery" id="gallery"></div>
          <label class="button">Добавить фото <input type="file" id="f-gallery" accept="image/*" multiple hidden></label>
        </div>
        <p class="error" id="form-error" hidden></p>
        <div class="actions">
          <button type="submit" class="primary" id="save">Опубликовать</button>
          <button type="button" class="link" id="cancel">Отмена</button>
          <button type="button" class="danger" id="delete" hidden>Удалить пост</button>
        </div>
      </form>
      <aside class="preview">
        <div class="preview-hero" id="p-hero"><span class="preview-date" id="p-date"></span><h2 id="p-title"></h2></div>
        <div class="preview-body nsu-post-body" id="p-body"></div>
        <div class="preview-gallery" id="p-gallery"></div>
      </aside>
    </div>
  </section>
</main>

<script src="vendor/quill.js"></script>
<script type="module" src="admin.js"></script>
</body>
</html>
```

`admin.css` — компактный, в палитре сайта (`#0b459f`, `#071e33`, `#e4e9f2`, `#5a6b7d`), системный шрифт; сетка `.editor{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,420px);gap:28px}` с переходом в одну колонку до 1000 px; таблица постов с миниатюрами 64×40; `.preview-hero` тёмный с обложкой фоном; стили `.nsu-post-body` для превью повторяют Task 6 (скопировать те же правила, они короткие). Кнопки `.primary` (синяя), `.danger` (красная), `.link` (без фона).

- [ ] **Step 6: Commit**

```bash
git add admin/
git commit -m "feat(admin): admin shell, GitHub client, image and slug helpers, vendored Quill 2.0.3"
```

---

### Task 11: Админка — `admin.js` (экраны, форма, сохранение, статус деплоя)

**Files:**
- Create: `admin/admin.js`

- [ ] **Step 1: Написать `admin.js`**

Структура модуля (все функции на верхнем уровне, состояние в одном объекте):

```javascript
import { GitHub, GitHubError } from './github.js';
import { prepareImage, blobToBase64 } from './images.js';
import { slugify, isValidSlug } from './slug.js';

const SITE_ROOT = new URL('..', location.href);          // http://host:8083/  or  https://…/ndu/
const TOKEN_KEY = 'ndu.admin.token';
const BRANCH = localStorage.getItem('ndu.admin.branch') || 'main';   // dev override only
const $ = (id) => document.getElementById(id);

const state = {
  gh: null,           // GitHub client
  news: null,         // {posts:[...]} as last read from the repo
  views: {},          // slug -> count
  editing: null,      // slug of the post being edited, or null for a new one
  slugTouched: false, // user edited the slug by hand
  cover: null,        // {blob, url} pending cover, or null
  gallery: [],        // [{path?, blob?, url}] current order
  inlineBlobs: new Map(), // blob: url -> {blob} for images inserted into the body
  quill: null,
  runTimer: null,
};
```

Поведение по функциям:

- `boot()`: если токен в `localStorage` — `login(token)`, иначе показать экран входа. `login()` создаёт `GitHub`, вызывает `repo()`; при ошибке — текст под полем (401 → «Токен не принят», 403/404 → «Нет доступа к BekkiBay/ndu»). Успех → сохранить токен, `loadList()`.
- `loadList()`: `head()` + `readNews()` → `state.news`; параллельно `fetch(new URL('views/counts', SITE_ROOT))` (ошибку глотать → `{}`); `renderList()`; `pollRun()`.
- `sortPosts(posts)` — та же сортировка, что в Python: датированные по дате desc, при равенстве `updated` desc, затем недатированные в исходном порядке.
- `renderList()`: строки таблицы: `<img src="${SITE_ROOT}${cover}">`, заголовок ссылкой на `${SITE_ROOT}news-${slug}.html` (новая вкладка), дата `formatDate()` (`d.m.yyyy`), просмотры `state.views[slug] ?? '—'`, кнопки «Изменить», «Удалить». «Удалить» → `confirm(\`Удалить пост «${title}»? Страница и её фото исчезнут с сайта после деплоя.\`)` → `deletePost(slug)`.
- `openEditor(slug|null)`: сбросить `state`, заполнить поля; для существующего поста: `state.editing = slug`, slug readonly, обложка `SITE_ROOT + cover`, галерея из путей, тело в Quill через `quill.clipboard.dangerouslyPasteHTML(absolutizeImages(body))` — где `absolutizeImages` заменяет `src="images/` на `src="${SITE_ROOT}images/`; показать кнопку «Удалить пост». Для нового: дата = сегодня (`toISOString().slice(0,10)` в локальном времени через `new Date(Date.now() - tz)`), slug пустой, `slugTouched = false`.
- Quill: `new Quill('#quill', {theme:'snow', modules:{toolbar:{container:[[{header:[2,3,false]}],['bold','italic','underline'],['link','blockquote'],[{list:'ordered'},{list:'bullet'}],['image'],['clean']], handlers:{image: pickInlineImage}}}})`. `pickInlineImage()` — скрытый `<input type=file accept=image/*>`, `prepareImage()`, `quill.insertEmbed(range.index, 'image', url)`, `state.inlineBlobs.set(url, {blob})`.
- Живое превью: на `text-change` Quill и `input` полей — `renderPreview()` копирует заголовок, дату, `quill.root.innerHTML` в `#p-body`, обложку фоном в `#p-hero`, галерею.
- Slug: на `input` заголовка, если `!slugTouched && !editing` → `f-slug.value = slugify(title)`; на `input` slug → `slugTouched = true`; `#slug-preview` обновляется всегда.
- Обложка: `change` → `prepareImage()` → `state.cover = {blob,url}`, превью.
- Галерея: `change` (multiple) → для каждого файла `prepareImage()` → push `{blob,url}`; `renderGallery()` рисует миниатюры с кнопками `↑ ↓ ×`.
- `validate()`: заголовок непустой; slug валиден и (для нового) не занят другим постом; обложка есть (`state.cover` или существующий `cover`); дата пустая или валидная. Ошибка → `#form-error`, фокус на поле.
- `collectFiles(slug, existing)` → `{files, body, cover, gallery}`:
  - `dir = images/nsu/news/${slug}/`; `taken` = множество имён, уже занятых в `existing` (cover, inline, gallery) — чтобы не перезаписывать;
  - обложка: если `state.cover` → путь `${dir}cover.jpg`, если такое имя занято старой обложкой — `cover-2.jpg`, `cover-3.jpg`…; старая обложка внутри `dir` → в `files` с `delete:true`;
  - тело: `html = quill.root.innerHTML` → `<img src="blob:…">` заменяются на `${dir}NN.jpg` (следующие свободные номера), файлы в `files` с base64; `src="${SITE_ROOT}images/…"` → `src="images/…"`; картинки старого тела внутри `dir`, которых больше нет в новом теле, → `delete:true`;
  - галерея: элементы с `blob` → `${dir}gNN.jpg`; старые пути внутри `dir`, отсутствующие в новом списке, → `delete:true`;
  - пустые абзацы `<p><br></p>` в конце тела отрезаются.
- `savePost()`: блокировать кнопку, `validate()`, `collectFiles()`, затем `gh.commit(message, mutate, files)`, где `mutate(news)` находит пост по slug и заменяет/добавляет `{slug,title,date|null,excerpt,cover,body,gallery,updated: new Date().toISOString()}`; сообщение `news: add «title»` или `news: update «title»`. После успеха: `state.news = result.news`, вернуться к списку с `notice` «Сохранено. Сайт обновится через 1–2 минуты после завершения деплоя.» и запустить `pollRun()`. Ошибка → `#form-error` с текстом (`GitHubError.message`), кнопка разблокируется, данные формы остаются.
- `deletePost(slug)`: `files = (await gh.listDir(\`images/nsu/news/${slug}\`)).map(p => ({path:p, delete:true}))`; `mutate` удаляет пост из массива; сообщение `news: delete «title»`.
- `pollRun()`: `gh.latestRun()` → в `#deploy`: `⏳ Деплой выполняется` / `✅ Деплой успешен` / `❌ Деплой упал` + `<a href=html_url target=_blank>подробности</a>` + время `updated_at` в локали; если `status !== 'completed'` — повторить через 20 с (`state.runTimer`), иначе один повтор через 60 с (на случай, если новый прогон ещё не появился).
- Любая `GitHubError` со статусом 401 → `logout()` (удалить токен, экран входа, текст «Токен отозван или истёк»).
- `logout` кнопка — то же самое.

Все пути в JSON — относительные от корня сайта (`images/…`), никаких `SITE_ROOT` внутри сохраняемых данных. Проверить это отдельно при ручном тесте.

- [ ] **Step 2: Локальная проверка без коммитов**

Run: `python3 scripts/build_news.py && python3 -m http.server 8899` → открыть `http://localhost:8899/admin/`. Без токена — экран входа. Ввести тестовый токен (см. Step 3): список из 11 постов, просмотры «—» (счётчика локально нет), статус последнего деплоя виден.

- [ ] **Step 3: Ручной сквозной тест на тестовой ветке**

Чтобы не трогать `main`: `git push origin main:test-admin`, в консоли админки `localStorage.setItem('ndu.admin.branch','test-admin'); location.reload()`. Токен для теста — `gh auth token` (OAuth-токен gh, у него есть права на репозиторий). Чек-лист:

1. Создать пост с датой, анонсом, обложкой (PNG > 1600 px), двумя фото в тексте, тремя фото в галерее → один коммит в `test-admin`; в дереве коммита `content/news.json` + `images/nsu/news/<slug>/cover.jpg, 01.jpg, 02.jpg, g01.jpg, g02.jpg, g03.jpg`; в JSON пути относительные, `blob:` и `http` отсутствуют.
2. Открыть пост на редактирование: заголовок, дата, slug (readonly), анонс, обложка, тело с картинками, галерея — всё на месте. Поменять текст, удалить одну картинку из текста, одну из галереи, переставить оставшиеся, заменить обложку → один коммит: удалённые файлы исчезли из дерева, новая обложка `cover-2.jpg`, старая удалена, порядок галереи в JSON новый.
3. Удалить пост → коммит без поста и без папки `images/nsu/news/<slug>/`.
4. Отредактировать импортированный пост (общая обложка `images/nsu/news/lab.jpg`): сменить обложку → старый общий файл **не** удалён.
5. Ввести заведомо плохой токен → сообщение; отозвать токен во время сессии → возврат на экран входа.
6. `git fetch && git checkout test-admin && python3 scripts/build_news.py && python3 scripts/check_links.py` → `OK`; страницы поста выглядят правильно. Вернуться на `main`, удалить ветку: `git push origin --delete test-admin`, `localStorage.removeItem('ndu.admin.branch')`.

- [ ] **Step 4: Commit**

```bash
git add admin/admin.js
git commit -m "feat(admin): post list, editor with Quill and image handling, one-commit publish"
```

---

### Task 12: Документация

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-09-09-news-admin-design.md` (зафиксировать отклонения: `slugify` живёт только в JS; крошки без заголовка)

- [ ] **Step 1: README**

- Таблица разделов: строка «Новости» → `news.html + посты из content/news.json (генерируются)`.
- Раздел «Запуск»: перед `http.server` добавить `python3 scripts/build_news.py`.
- Новый раздел «Новости и админка»: где данные (`content/news.json`, `images/nsu/news/<slug>/`), что генерируется, адрес админки `http://185.217.199.92:8083/admin/` (после домена — тот же путь), как получить токен (3 строки), что происходит после «Опубликовать» (коммит → CI → 1–2 мин), где счётчик (`/views/`, `deploy/counter/`).
- Раздел «Как пересобрать»: новости больше не собираются внешними скриптами; `scripts/build_news.py` в репозитории; `contact.html` — донор оболочки (если менять оболочку, менять её на всех страницах, включая донора).
- Раздел «Деплой»: одна фраза про тесты (`python3 -m unittest discover -s tests`) и про точечное удаление `news-*.html`.

- [ ] **Step 2: Commit**

```bash
git add README.md docs/
git commit -m "docs: news data, build, admin panel and view counter"
```

---

### Task 13: Пуш, деплой, проверка на сервере

- [ ] **Step 1: Финальные проверки локально**

```bash
python3 -m unittest discover -s tests && python3 scripts/build_news.py && python3 scripts/stamp_assets.py && python3 scripts/check_links.py && git status --short
```

Expected: `OK`, `written: 0` (или только перештампованные), `OK`, рабочее дерево чистое.

- [ ] **Step 2: Пуш и наблюдение за CI**

```bash
git push origin main
gh run watch --exit-status $(gh run list -L1 --json databaseId -q '.[0].databaseId')
```

Expected: задачи `check`, `deploy`, `pages` зелёные. Если `deploy` упал на `compose up` — смотреть лог шага: типичные причины — образ `python:3.12-alpine` не скачался (повторить запуск) или `nginx -t` не принял конфиг.

- [ ] **Step 3: Проверить сайт**

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://185.217.199.92:8083/news.html
curl -s http://185.217.199.92:8083/views/health
curl -s -X POST -H 'Content-Type: application/json' -H 'User-Agent: Mozilla/5.0 check' \
     -d '{"slug":"new-laboratory-opened"}' http://185.217.199.92:8083/views/hit
curl -s http://185.217.199.92:8083/views/counts
curl -s -o /dev/null -w '%{http_code}\n' http://185.217.199.92:8083/admin/
```

Expected: `200`, `{"status": "ok"}`, `{"slug": "new-laboratory-opened", "count": 1}`, JSON со счётчиками, `200`. В браузере открыть пост — под заголовком появилась строка «Ko‘rishlar: N». Открыть `http://185.217.199.92:8083/admin/`, войти со своим fine-grained token, увидеть список с просмотрами.

- [ ] **Step 4: Сохранить в память проекта**

Обновить `ndu-repo.md` в памяти: новости генерируются из `content/news.json`, админка `/admin/`, счётчик `ndu-counter`, донор оболочки `contact.html`, единственное удаление на сервере — `news-*.html`.

---

## Self-review

- **Spec coverage.** Данные (T1, T2), сборка и оболочка (T3–T5), стили (T6), счётчик (T7–T8), CI/CD включая точечное удаление и health (T9), админка со всеми экранами и правилом удаления файлов (T10–T11), документация (T12), деплой и ручные шаги владельца (T13). Отклонения от спеки: `slugify` только в JS (Python его не использует), крошки на странице поста без заголовка — фиксируются в спеке в T12.
- **Placeholders.** Код есть для всех модулей, кроме `admin.css` (описан правилами) и `admin.js` (описан по функциям с сигнатурами состояния); оба пишутся в своих задачах по этим описаниям.
- **Type consistency.** `Shell.render(title, description, og_image, content, before_body_end)`; `build(root)` → `{'written','deleted','unchanged'}`; `GitHub.commit(message, mutate, files)` где `files: [{path, base64} | {path, delete:true}]`; `prepareImage()` → `{blob,width,height,url}`; `make_server(host, port, db_path)` с атрибутом `store`. Названия совпадают между задачами.
