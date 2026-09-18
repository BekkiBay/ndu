#!/usr/bin/env python3
"""Собирает русскую и английскую версии сайта из узбекских страниц.

Узбекские страницы лежат в корне и правятся руками — они источник правды.
Скрипт кладёт рядом каталоги ``ru/`` и ``en/`` с теми же именами файлов:

* текст и переводимые атрибуты заменяются по ``content/i18n/<lang>.json``;
* относительные ссылки на общие файлы получают префикс ``../``, ссылки на
  соседние страницы остаются как есть (в каталоге лежит полный набор);
* ``<html lang>``, переключатель языка и ссылки ``hreflang`` переписываются
  под язык страницы.

Страницы новостей здесь не трогаются: их на всех языках генерирует
``scripts/build_news.py`` из ``content/news.json`` — запускать его надо
после этого скрипта.

Детерминированный: два запуска подряд без правок ничего не меняют.
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import i18n  # noqa: E402

SITE = 'https://ndu.uz'
LANG_BLOCK = re.compile(
    r'<div class="lang" id="lang">.*?</ul>\s*</div>', re.S)
HTML_TAG = re.compile(r'<html\s+lang="[^"]*"')
HREFLANG_MARK = '<!-- i18n:alternate -->'
ALTERNATE_BLOCK = re.compile(
    re.escape(HREFLANG_MARK) + r'.*?' + re.escape('<!-- /i18n:alternate -->'),
    re.S)
TITLE = re.compile(r'<title>.*?</title>', re.S)


class BuildError(Exception):
    """Ошибка входных данных; печатается без трейсбека."""


def source_pages():
    """Узбекские страницы в корне, кроме генерируемых новостных."""
    return sorted(p for p in i18n.ROOT.glob('*.html')
                  if not p.name.startswith('news-') and p.name != 'news.html')


def lang_switcher(lang, page, indent='        '):
    """Разметка переключателя языка для страницы ``page`` на языке ``lang``."""
    pad = indent + '  '
    rows = []
    for other in i18n.LANGS:
        href = page_url(other, page, relative_to=lang)
        active = ' class="is-active"' if other == lang else ''
        flag = asset_url(lang, 'assets/' + i18n.LANG_FLAG[other])
        rows.append(
            f'{pad}  <li><a{active} href="{href}" hreflang="{other}" '
            f'lang="{i18n.HTML_LANG[other]}">'
            f'<img class="lang__flag" src="{flag}" alt="">'
            f'<span>{i18n.LANG_NAME[other]}</span></a></li>')
    menu = '\n'.join(rows)
    flag = asset_url(lang, 'assets/' + i18n.LANG_FLAG[lang])
    return (
        f'<div class="lang" id="lang">\n'
        f'{pad}<button class="lang__btn" type="button" aria-haspopup="true" aria-expanded="false">\n'
        f'{pad}  <img class="lang__flag" src="{flag}" alt="">\n'
        f'{pad}  <span class="lang__label">{i18n.LANG_NAME[lang]}</span>\n'
        f'{pad}  <svg class="ico"><use href="#i-chevron-down"/></svg>\n'
        f'{pad}</button>\n'
        f'{pad}<ul class="lang__menu">\n{menu}\n'
        f'{pad}</ul>\n'
        f'{indent}</div>')


def asset_url(lang, path):
    """Ссылка на общий файл (assets, images …) со страницы языка ``lang``."""
    return path if lang == 'uz' else f'../{path}'


def page_url(lang, page, relative_to='uz'):
    """Ссылка на страницу ``page`` на языке ``lang`` со страницы языка ``relative_to``."""
    if lang == relative_to:
        return page
    up = '' if relative_to == 'uz' else '../'
    folder = i18n.LANG_DIR[lang]
    return f'{up}{folder}/{page}' if folder else f'{up}{page}'


def alternates(page):
    """Блок ``<link rel="alternate" hreflang>`` для всех языков."""
    lines = [HREFLANG_MARK]
    for lang in i18n.LANGS:
        lines.append(f'\t<link rel="alternate" hreflang="{lang}" href="{canonical(lang, page)}">')
    lines.append(f'\t<link rel="alternate" hreflang="x-default" href="{canonical("uz", page)}">')
    lines.append('\t<!-- /i18n:alternate -->')
    return '\n'.join(lines)


def canonical(lang, page):
    """Полный адрес страницы на языке ``lang``; главная — адрес каталога."""
    folder = i18n.LANG_DIR[lang]
    base = f'{SITE}/{folder}/' if folder else f'{SITE}/'
    return base if page == 'index.html' else base + page


def with_alternates(src, page):
    """Ставит (или обновляет) блок hreflang сразу после ``<title>``."""
    block = alternates(page)
    if ALTERNATE_BLOCK.search(src):
        return ALTERNATE_BLOCK.sub(lambda _m: block, src, count=1)
    m = TITLE.search(src)
    if not m:
        raise BuildError('на странице нет <title>')
    return src[:m.end()] + '\n' + block + src[m.end():]


def render(src, lang, page, page_links, table):
    depth = 0 if lang == 'uz' else 1
    out = i18n.apply(src, table, depth=depth, page_links=page_links)
    out = HTML_TAG.sub(f'<html lang="{i18n.HTML_LANG[lang]}"', out, count=1)
    if not LANG_BLOCK.search(out):
        raise BuildError('на странице нет переключателя языка')
    out = LANG_BLOCK.sub(lambda _m: lang_switcher(lang, page), out, count=1)
    return with_alternates(out, page)


def build(langs=('ru', 'en'), quiet=False):
    pages = source_pages()
    if not pages:
        raise BuildError('в корне нет страниц')
    page_links = {p.name for p in i18n.ROOT.glob('*.html')}
    page_links.update({'news.html'})

    # Узбекские страницы тоже проходят через render: переключатель языка и
    # ссылки hreflang должны быть одинаковыми во всех трёх версиях.
    written = {}
    for lang in ('uz',) + tuple(langs):
        table = i18n.load_table(lang)
        folder = i18n.ROOT / i18n.LANG_DIR[lang] if i18n.LANG_DIR[lang] else i18n.ROOT
        folder.mkdir(parents=True, exist_ok=True)
        count = 0
        for page in pages:
            src = page.read_text(encoding='utf-8')
            out = render(src, lang, page.name, page_links, table)
            target = folder / page.name
            if not target.exists() or target.read_text(encoding='utf-8') != out:
                target.write_text(out, encoding='utf-8')
                count += 1
        written[lang] = count
        if lang != 'uz':
            prune(folder, {p.name for p in pages})
    if not quiet:
        for lang in written:
            table = i18n.load_table(lang)
            note = '' if lang == 'uz' else f', словарь {len(table)} строк'
            print(f'{lang}: {len(pages)} страниц, обновлено {written[lang]}{note}')
    return written


def prune(folder, keep):
    """Убирает страницы языка, которых больше нет в узбекской версии."""
    for path in folder.glob('*.html'):
        if path.name in keep:
            continue
        if path.name == 'news.html' or path.name.startswith('news-'):
            continue          # их держит build_news.py
        path.unlink()


def main():
    try:
        build()
    except BuildError as exc:
        sys.exit(f'build_i18n: {exc}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
