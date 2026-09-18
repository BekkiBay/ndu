#!/usr/bin/env python3
"""Общие примитивы многоязычности сайта.

Узбекская версия страниц лежит в корне репозитория и остаётся источником
правды. Русская и английская версии собираются из неё скриптом
``build_i18n.py``: текст подменяется по словарю ``content/i18n/*.json``,
относительные ссылки на общие файлы (assets, images, media …) получают
префикс ``../``, потому что страницы переезжают на уровень вглубь.

Модуль намеренно не использует полноценный HTML-парсер с обратной
сериализацией: страницы свёрстаны вручную, и любая пересборка DOM меняет
разметку. Вместо этого исходный файл режется на токены регулярным
выражением, а заменяются только найденные отрезки — всё остальное
переносится в результат байт в байт.
"""
import html
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
I18N_DIR = ROOT / 'content' / 'i18n'

#: Языки сайта. Узбекский — исходный, лежит в корне (без каталога).
LANGS = ('uz', 'ru', 'en')
LANG_DIR = {'uz': '', 'ru': 'ru', 'en': 'en'}
HTML_LANG = {'uz': 'uz', 'ru': 'ru', 'en': 'en'}
LANG_NAME = {'uz': 'O‘zbekcha', 'ru': 'Русский', 'en': 'English'}
LANG_FLAG = {'uz': 'flag-uz.svg', 'ru': 'flag-ru.svg', 'en': 'flag-en.svg'}

TOKEN = re.compile(
    r'(?P<opaque><(?P<ot>script|style)\b[^>]*>.*?</(?P=ot)\s*>)'
    r'|(?P<comment><!--.*?-->)'
    r'|(?P<decl><![^>]*>)'
    r'|(?P<tag><\s*(?P<close>/?)\s*(?P<name>[a-zA-Z][-a-zA-Z0-9:]*)'
    r'(?P<attrs>(?:"[^"]*"|\'[^\']*\'|[^>"\'])*)>)',
    re.S)

ATTR = re.compile(
    r'(?P<name>[-a-zA-Z0-9:_@.]+)\s*=\s*(?P<q>["\'])(?P<val>.*?)(?P=q)', re.S)

#: Внутри этих элементов текст не переводится: иконочные спрайты и
#: выпадающий список стран формы (значения — коды ISO, их переводить незачем).
SKIP_TEXT_IN = {'svg', 'select'}

#: Атрибуты с человекочитаемым текстом.
TEXT_ATTRS = {'alt', 'title', 'placeholder', 'aria-label'}

#: <meta name="..."> с переводимым content.
META_NAMES = {'description', 'keywords', 'og:title', 'og:description', 'og:image:alt'}

#: Атрибуты со ссылками, которые надо переписать при переносе в подкаталог.
URL_ATTRS = {'href', 'src', 'poster', 'action', 'data-src', 'data-bg'}

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
        'meta', 'param', 'source', 'track', 'wbr'}

ABSOLUTE = re.compile(r'^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//|/|#|\?)')

LETTER = re.compile(r'[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳ]')
ONLY_TECH = re.compile(r'^(?:[\w.+-]+@[\w.-]+|\+?[\d\s()+-]+)$')


def is_translatable(text):
    """Нужно ли слать строку переводчику.

    Отсеиваются разделители, числа, телефоны и адреса почты: их перевод
    совпал бы с оригиналом и только раздувал бы словарь.
    """
    text = text.strip()
    if not text or not LETTER.search(text):
        return False
    if ONLY_TECH.match(text):
        return False
    return True


def tokenize(src):
    """Режет документ на токены ``(kind, start, end, match)``.

    ``kind`` — ``text``, ``tag`` или ``other`` (комментарии, doctype,
    содержимое script и style целиком).
    """
    pos = 0
    for m in TOKEN.finditer(src):
        if m.start() > pos:
            yield ('text', pos, m.start(), None)
        yield (('tag' if m.group('tag') else 'other'), m.start(), m.end(), m)
        pos = m.end()
    if pos < len(src):
        yield ('text', pos, len(src), None)


def iter_strings(src):
    """Перечисляет переводимые куски страницы.

    Возвращает ``(start, end, text, kind)``, где ``kind`` — ``text`` для
    текстового узла и имя атрибута для значения атрибута. Отрезки идут по
    возрастанию позиции и не пересекаются.
    """
    stack = []
    for kind, a, b, m in tokenize(src):
        if kind == 'text':
            if any(t in SKIP_TEXT_IN for t in stack):
                continue
            raw = src[a:b]
            stripped = raw.strip()
            if not stripped:
                continue
            off = a + (len(raw) - len(raw.lstrip()))
            yield (off, off + len(stripped), stripped, 'text')
        elif kind == 'tag':
            name = m.group('name').lower()
            if m.group('close'):
                if name in stack:
                    while stack and stack.pop() != name:
                        pass
                continue
            attrs = dict(_attrs(m))
            for am in ATTR.finditer(m.group('attrs') or ''):
                aname = am.group('name').lower()
                if not _attr_translatable(name, aname, attrs):
                    continue
                val = am.group('val').strip()
                if not val:
                    continue
                base = m.start('attrs')
                yield (base + am.start('val'), base + am.end('val'), val, aname)
            if name not in VOID and not (m.group('attrs') or '').rstrip().endswith('/'):
                stack.append(name)


def _attrs(m):
    for am in ATTR.finditer(m.group('attrs') or ''):
        yield am.group('name').lower(), am.group('val')


def _attr_translatable(tag, attr, attrs):
    if tag == 'meta':
        key = (attrs.get('name') or attrs.get('property') or '').lower()
        return attr == 'content' and key in META_NAMES
    if tag == 'option':
        return False
    return attr in TEXT_ATTRS


def page_strings(src):
    """Все переводимые строки страницы, включая содержимое ``<title>``."""
    seen = []
    for start, end, text, kind in iter_strings(src):
        if is_translatable(text):
            seen.append((start, end, text, kind))
    return seen


def apply(src, table, depth=0, page_links=()):
    """Собирает страницу на другом языке.

    ``table`` — словарь ``{исходная строка: перевод}``; отсутствующие ключи
    остаются на узбекском. ``depth`` — на сколько уровней страница уходит
    вглубь (1 для ``ru/`` и ``en/``), ``page_links`` — имена файлов страниц,
    которые существуют и в переводе: такие ссылки остаются относительными.
    """
    edits = []
    for start, end, text, kind in page_strings(src):
        translated = table.get(text)
        if translated and translated != text:
            if kind != 'text':
                # Значение атрибута в двойных кавычках: свою кавычку перевод
                # обязан отдать сущностью, иначе он закроет атрибут.
                translated = translated.replace('"', '&quot;')
            edits.append((start, end, translated))
    if depth:
        edits.extend(_url_edits(src, depth, set(page_links)))
    edits.sort(key=lambda e: e[0])

    out = []
    pos = 0
    for start, end, value in edits:
        if start < pos:          # пересечение — перевод важнее ссылки
            continue
        out.append(src[pos:start])
        out.append(value)
        pos = end
    out.append(src[pos:])
    return ''.join(out)


def _url_edits(src, depth, page_links):
    prefix = '../' * depth
    for kind, a, b, m in tokenize(src):
        if kind == 'tag':
            base = m.start('attrs')
            for am in ATTR.finditer(m.group('attrs') or ''):
                name = am.group('name').lower()
                val = am.group('val')
                if name == 'style':
                    new = _rewrite_css_urls(val, prefix, page_links)
                    if new != val:
                        yield (base + am.start('val'), base + am.end('val'), new)
                    continue
                if name == 'srcset':
                    new = _rewrite_srcset(val, prefix, page_links)
                    if new != val:
                        yield (base + am.start('val'), base + am.end('val'), new)
                    continue
                if name not in URL_ATTRS:
                    continue
                new = relocate(val, prefix, page_links)
                if new != val:
                    yield (base + am.start('val'), base + am.end('val'), new)
        elif kind == 'other' and m and m.group('opaque') and m.group('ot') == 'style':
            block = src[a:b]
            new = _rewrite_css_urls(block, prefix, page_links)
            if new != block:
                yield (a, b, new)


CSS_URL = re.compile(r'url\(\s*(?P<q>["\']?)(?P<val>[^"\')]*)(?P=q)\s*\)')


def _rewrite_css_urls(text, prefix, page_links):
    def sub(m):
        new = relocate(m.group('val'), prefix, page_links)
        return f'url({m.group("q")}{new}{m.group("q")})'
    return CSS_URL.sub(sub, text)


def _rewrite_srcset(value, prefix, page_links):
    parts = []
    for item in value.split(','):
        head = item.strip().split(None, 1)
        if not head:
            continue
        url = relocate(head[0], prefix, page_links)
        parts.append(url if len(head) == 1 else f'{url} {head[1]}')
    return ', '.join(parts)


def relocate(url, prefix, page_links):
    """Переписывает относительную ссылку для страницы в подкаталоге."""
    url = url.strip()
    if not url or ABSOLUTE.match(url) or url.startswith('..'):
        return url
    path, sep, tail = url.partition('#')
    path, qsep, query = path.partition('?')
    if path in page_links:
        return url
    if not path:
        return url
    return f'{prefix}{path}{qsep}{query}{sep}{tail}'


def load_table(lang):
    """Словарь ``{узбекская строка: перевод}`` для языка."""
    import json
    if lang == 'uz':
        return {}
    path = I18N_DIR / f'{lang}.json'
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def esc(text):
    return html.escape(text or '', quote=True)
