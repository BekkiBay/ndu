#!/usr/bin/env python3
"""Собирает список переводимых строк сайта.

Проходит узбекские страницы в корне репозитория и пишет
``content/i18n/uz.json`` — каталог строк с указанием, на каких страницах
они встречаются. Файл нужен только людям и скриптам-помощникам: сборка
страниц берёт переводы из ``ru.json`` и ``en.json``.

    python3 scripts/i18n_extract.py            # обновить каталог
    python3 scripts/i18n_extract.py --missing ru   # чего ещё нет в ru.json
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import i18n  # noqa: E402


def source_pages():
    """Узбекские страницы в корне (новости генерируются отдельно)."""
    return sorted(p for p in i18n.ROOT.glob('*.html')
                  if not p.name.startswith('news-') and p.name != 'news.html')


def collect():
    catalog = {}
    for page in source_pages():
        src = page.read_text(encoding='utf-8')
        for _start, _end, text, kind in i18n.page_strings(src):
            entry = catalog.setdefault(text, {'kind': kind, 'pages': []})
            if page.name not in entry['pages']:
                entry['pages'].append(page.name)
    return catalog


def main(argv):
    catalog = collect()
    if len(argv) > 1 and argv[1] == '--missing':
        lang = argv[2] if len(argv) > 2 else 'ru'
        table = i18n.load_table(lang)
        missing = {k: v for k, v in catalog.items() if k not in table}
        by_page = {}
        for text, meta in missing.items():
            by_page.setdefault(meta['pages'][0], []).append(text)
        for page in sorted(by_page):
            print(f'## {page}')
            for text in by_page[page]:
                print(json.dumps(text, ensure_ascii=False))
        print(f'# {len(missing)} из {len(catalog)} строк без перевода на {lang}',
              file=sys.stderr)
        return 0

    i18n.I18N_DIR.mkdir(parents=True, exist_ok=True)
    out = {text: meta for text, meta in sorted(catalog.items())}
    path = i18n.I18N_DIR / 'uz.json'
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n',
                    encoding='utf-8')
    chars = sum(len(t) for t in out)
    print(f'{path.relative_to(i18n.ROOT)}: {len(out)} строк, {chars} символов')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
