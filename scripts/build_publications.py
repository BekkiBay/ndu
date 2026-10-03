#!/usr/bin/env python3
"""Generates the scientific publications pages from content/publications.json.

Writes publications.html (the catalogue: search, filter by type and year) and
publication-<slug>.html for every work: a page in the manner of an open
journal system — people with their roles and affiliations, keywords, abstract,
table of contents with links into the PDF, references, a sidebar with the PDF,
the bibliographic data and ready-made citations (GOST, APA, MLA, BibTeX), and
Google Scholar ``citation_*`` meta tags in the head.

The page shell is cut from contact.html exactly like the news pages
(scripts/build_news.py), so header and footer changes reach these pages too.
The same pages are produced for every language whose shell donor exists
(<lang>/contact.html, written by scripts/build_i18n.py), so this script runs
after build_i18n.py. Interface texts live in LABELS below; per-language fields
of a work (title_ru, abstract_en …) fall back to the Uzbek ones. Citations are
built once per work, in the work's own language, as bibliographic practice
requires.

Deterministic: running it twice without changing the inputs changes nothing.
"""
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import build_i18n  # noqa: E402
import build_news as news  # noqa: E402
import i18n  # noqa: E402

BuildError = news.BuildError
esc = news.esc

LIST_PAGE = 'publications.html'
PAGE_PREFIX = 'publication-'
LIST_HERO = 'images/nsu/news/lab.jpg'
CSS = 'assets/css/publications.css'
JS = 'assets/js/publications.js'
SITE = build_i18n.SITE

TYPES = ('article', 'thesis', 'proceedings', 'monograph', 'textbook', 'other')
ROLES = ('author', 'chief_editor', 'scientific_editor', 'editor', 'technical_editor', 'reviewer', 'committee')
#: Роли, которые в библиографической записи стоят на месте автора.
EDITOR_ROLES = ('chief_editor', 'scientific_editor', 'editor')

#: Страницы раздела «Ilmiy faoliyat» для блока ссылок внизу каталога.
#: Подписи переводятся словарём content/i18n — они уже есть на этих страницах.
RESEARCH_PAGES = (
    ('research.html', 'Ilmiy faoliyat'),
    ('research-council.html', 'Ilmiy kengash'),
    ('research-doctorate.html', 'Doktorantura bo‘limi'),
    ('research-projects.html', 'Ilmiy-tadqiqot loyihalari'),
    ('research-conferences.html', 'Ilmiy konferensiyalar'),
    ('research-journals.html', 'Ilmiy jurnallar'),
    ('research-abstracts.html', 'Avtoreferatlar'),
    ('research-innovation.html', 'Innovatsiya va tijoratlashtirish'),
    ('research-talented-students.html', 'Iqtidorli talabalar'),
)


def plural_ru(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


#: Подписи страниц на каждом языке — всё, что генератор пишет сам.
LABELS = {
    'uz': {
        'home': 'Bosh sahifa',
        'research': 'Ilmiy faoliyat',
        'section': 'Ilmiy nashrlar',
        'list_sub': 'Universitet olimlari va hamkorlarining maqolalari, tezislari, '
                    'konferensiya to‘plamlari va monografiyalari.',
        'intro': 'Bu yerda Navoiy davlat universiteti olimlari va hamkorlarining ilmiy nashrlari jamlangan. '
                 'Har bir nashrning sahifasida annotatsiya, mundarija va iqtibos namunalari bor, '
                 'to‘liq matnni PDF shaklida ochish yoki yuklab olish mumkin.',
        'types': {
            'article': ('Maqola', 'Maqolalar'),
            'thesis': ('Tezis', 'Tezislar'),
            'proceedings': ('Konferensiya to‘plami', 'Konferensiya to‘plamlari'),
            'monograph': ('Monografiya', 'Monografiyalar'),
            'textbook': ('Darslik', 'Darslik va qo‘llanmalar'),
            'other': ('Nashr', 'Boshqa nashrlar'),
        },
        'roles': {
            'author': ('Muallif', 'Mualliflar'),
            'chief_editor': ('Mas’ul muharrir', 'Mas’ul muharrirlar'),
            'scientific_editor': ('Ilmiy muharrir', 'Ilmiy muharrirlar'),
            'editor': ('Muharrir', 'Muharrirlar'),
            'technical_editor': ('Texnik muharrir', 'Texnik muharrirlar'),
            'reviewer': ('Taqrizchi', 'Taqrizchilar'),
            'committee': ('Tashkiliy qo‘mita a’zosi', 'Tashkiliy qo‘mita'),
        },
        'langs': {'uz': 'o‘zbek', 'ru': 'rus', 'en': 'ingliz', 'kk': 'qozoq', 'tg': 'tojik', 'tr': 'turk'},
        'keywords': 'Kalit so‘zlar',
        'abstract': 'Annotatsiya',
        'toc': 'Mundarija',
        'toc_count': lambda n: f'{n} ta material',
        'toc_search': 'Mundarijadan qidirish: muallif yoki mavzu',
        'toc_empty': 'Mos material topilmadi.',
        'show_all': lambda n: f'Barchasini ko‘rsatish ({n})',
        'show_less': 'Yig‘ish',
        'refs': 'Foydalanilgan adabiyotlar',
        'open_pdf': 'PDF’ni ochish',
        'download': 'Yuklab olish',
        'page_abbr': 'b.',
        'page_title': 'PDF’da shu sahifani ochish',
        'event': 'Konferensiya',
        'published': 'Nashr sanasi',
        'year': 'Nashr yili',
        'publisher': 'Nashriyot',
        'type': 'Turi',
        'pages': 'Hajmi',
        'pages_n': lambda n: f'{n} bet',
        'languages': 'Tillari',
        'source': 'Manba',
        'volume': lambda v, i: ', '.join(x for x in (f'{v}-jild' if v else '', f'{i}-son' if i else '') if x),
        'range': 'Sahifalar',
        'doi': 'DOI',
        'copyright': 'Mualliflik huquqi',
        'license': 'Litsenziya',
        'original': 'Asl nomi',
        'cite': 'Iqtibos keltirish',
        'copy': 'Nusxa olish',
        'copied': 'Nusxa olindi',
        'search': 'Sarlavha, muallif, kalit so‘z yoki maqola mavzusi…',
        'search_label': 'Nashrlar bo‘yicha qidirish',
        'all': 'Barchasi',
        'all_years': 'Barcha yillar',
        'count': lambda n: f'{n} ta nashr',
        'empty': 'So‘rov bo‘yicha nashr topilmadi.',
        'hits': 'To‘plam ichida topildi:',
        'hits_more': 'Yana {n} ta material — barchasini ko‘rish',
        'more': 'Batafsil',
        'materials': lambda n: f'{n} ta material',
        'others': 'Boshqa nashrlar',
        'related': 'ILMIY FAOLIYAT',
    },
    'ru': {
        'home': 'Главная',
        'research': 'Наука',
        'section': 'Научные публикации',
        'list_sub': 'Статьи, тезисы, сборники конференций и монографии учёных университета и его партнёров.',
        'intro': 'Здесь собраны научные публикации учёных Навоийского государственного университета и его '
                 'партнёров. На странице каждой публикации — аннотация, содержание и готовые варианты '
                 'цитирования; полный текст можно открыть или скачать в PDF.',
        'types': {
            'article': ('Статья', 'Статьи'),
            'thesis': ('Тезисы', 'Тезисы'),
            'proceedings': ('Сборник конференции', 'Сборники конференций'),
            'monograph': ('Монография', 'Монографии'),
            'textbook': ('Учебник', 'Учебники и пособия'),
            'other': ('Издание', 'Другие издания'),
        },
        'roles': {
            'author': ('Автор', 'Авторы'),
            'chief_editor': ('Ответственный редактор', 'Ответственные редакторы'),
            'scientific_editor': ('Научный редактор', 'Научные редакторы'),
            'editor': ('Редактор', 'Редакторы'),
            'technical_editor': ('Технический редактор', 'Технические редакторы'),
            'reviewer': ('Рецензент', 'Рецензенты'),
            'committee': ('Член оргкомитета', 'Организационный комитет'),
        },
        'langs': {'uz': 'узбекский', 'ru': 'русский', 'en': 'английский', 'kk': 'казахский',
                  'tg': 'таджикский', 'tr': 'турецкий'},
        'keywords': 'Ключевые слова',
        'abstract': 'Аннотация',
        'toc': 'Содержание',
        'toc_count': lambda n: f'{n} {plural_ru(n, "материал", "материала", "материалов")}',
        'toc_search': 'Поиск по содержанию: автор или тема',
        'toc_empty': 'Подходящих материалов не найдено.',
        'show_all': lambda n: f'Показать все ({n})',
        'show_less': 'Свернуть',
        'refs': 'Список литературы',
        'open_pdf': 'Открыть PDF',
        'download': 'Скачать',
        'page_abbr': 'с.',
        'page_title': 'Открыть эту страницу в PDF',
        'event': 'Конференция',
        'published': 'Дата публикации',
        'year': 'Год издания',
        'publisher': 'Издатель',
        'type': 'Тип',
        'pages': 'Объём',
        'pages_n': lambda n: f'{n} {plural_ru(n, "страница", "страницы", "страниц")}',
        'languages': 'Языки',
        'source': 'Источник',
        'volume': lambda v, i: ', '.join(x for x in (f'т. {v}' if v else '', f'№ {i}' if i else '') if x),
        'range': 'Страницы',
        'doi': 'DOI',
        'copyright': 'Авторские права',
        'license': 'Лицензия',
        'original': 'Оригинальное название',
        'cite': 'Как цитировать',
        'copy': 'Копировать',
        'copied': 'Скопировано',
        'search': 'Название, автор, ключевое слово или тема статьи…',
        'search_label': 'Поиск по публикациям',
        'all': 'Все',
        'all_years': 'Все годы',
        'count': lambda n: f'{n} {plural_ru(n, "публикация", "публикации", "публикаций")}',
        'empty': 'По запросу ничего не найдено.',
        'hits': 'Найдено внутри сборника:',
        'hits_more': 'Ещё {n} — показать все',
        'more': 'Подробнее',
        'materials': lambda n: f'{n} {plural_ru(n, "материал", "материала", "материалов")}',
        'others': 'Другие публикации',
        'related': 'НАУЧНАЯ ДЕЯТЕЛЬНОСТЬ',
    },
    'en': {
        'home': 'Home',
        'research': 'Research',
        'section': 'Publications',
        'list_sub': 'Articles, conference abstracts, proceedings and monographs by the university’s scholars '
                    'and partners.',
        'intro': 'This is the collection of scientific publications by scholars of Navoi State University and its '
                 'partners. Each publication has its own page with the abstract, the table of contents and '
                 'ready-made citations; the full text opens or downloads as a PDF.',
        'types': {
            'article': ('Article', 'Articles'),
            'thesis': ('Conference abstract', 'Conference abstracts'),
            'proceedings': ('Conference proceedings', 'Conference proceedings'),
            'monograph': ('Monograph', 'Monographs'),
            'textbook': ('Textbook', 'Textbooks and manuals'),
            'other': ('Publication', 'Other publications'),
        },
        'roles': {
            'author': ('Author', 'Authors'),
            'chief_editor': ('Editor-in-chief', 'Editors-in-chief'),
            'scientific_editor': ('Scientific editor', 'Scientific editors'),
            'editor': ('Editor', 'Editors'),
            'technical_editor': ('Technical editor', 'Technical editors'),
            'reviewer': ('Reviewer', 'Reviewers'),
            'committee': ('Organising committee member', 'Organising committee'),
        },
        'langs': {'uz': 'Uzbek', 'ru': 'Russian', 'en': 'English', 'kk': 'Kazakh', 'tg': 'Tajik', 'tr': 'Turkish'},
        'keywords': 'Keywords',
        'abstract': 'Abstract',
        'toc': 'Table of contents',
        'toc_count': lambda n: f'{n} item{"s" if n != 1 else ""}',
        'toc_search': 'Search the contents: author or topic',
        'toc_empty': 'Nothing matches.',
        'show_all': lambda n: f'Show all ({n})',
        'show_less': 'Show less',
        'refs': 'References',
        'open_pdf': 'Open PDF',
        'download': 'Download',
        'page_abbr': 'p.',
        'page_title': 'Open this page in the PDF',
        'event': 'Conference',
        'published': 'Published',
        'year': 'Year',
        'publisher': 'Publisher',
        'type': 'Type',
        'pages': 'Length',
        'pages_n': lambda n: f'{n} page{"s" if n != 1 else ""}',
        'languages': 'Languages',
        'source': 'Source',
        'volume': lambda v, i: ', '.join(x for x in (f'vol. {v}' if v else '', f'no. {i}' if i else '') if x),
        'range': 'Pages',
        'doi': 'DOI',
        'copyright': 'Copyright',
        'license': 'License',
        'original': 'Original title',
        'cite': 'How to cite',
        'copy': 'Copy',
        'copied': 'Copied',
        'search': 'Title, author, keyword or paper topic…',
        'search_label': 'Search publications',
        'all': 'All',
        'all_years': 'All years',
        'count': lambda n: f'{n} publication{"s" if n != 1 else ""}',
        'empty': 'Nothing matches your search.',
        'hits': 'Found inside the volume:',
        'hits_more': '{n} more — show all',
        'more': 'Details',
        'materials': lambda n: f'{n} item{"s" if n != 1 else ""}',
        'others': 'Other publications',
        'related': 'RESEARCH',
    },
}

#: Слова библиографической записи ГОСТ на языке самой работы.
GOST_WORDS = {
    'uz': {'chief_editor': 'mas’ul muharrir', 'scientific_editor': 'ilmiy muharrir', 'editor': 'muharrir',
           'pages': 'b.', 'vol': 'T.', 'no': '№', 'pp': 'B.'},
    'ru': {'chief_editor': 'отв. ред.', 'scientific_editor': 'науч. ред.', 'editor': 'ред.',
           'pages': 'с.', 'vol': 'Т.', 'no': '№', 'pp': 'С.'},
    'en': {'chief_editor': 'ed.', 'scientific_editor': 'sci. ed.', 'editor': 'ed.',
           'pages': 'p.', 'vol': 'Vol.', 'no': 'No.', 'pp': 'P.'},
}

ICON_PDF = ('<svg class="pub-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 '
            '2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M9 13h6M9 17h6"/></svg>')
ICON_DOWNLOAD = ('<svg class="pub-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m0 0-5-5m5 5 5-5'
                 'M4 21h16"/></svg>')
ICON_SEARCH = ('<svg class="pub-ico" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/>'
               '<path d="m20 20-3.5-3.5"/></svg>')


# --------------------------------------------------------------------------- data

def field(item, name, lang):
    return news.field(item, name, lang)


def list_field(item, name, lang):
    if lang != 'uz':
        value = item.get(f'{name}_{lang}')
        if isinstance(value, list) and value:
            return value
    return item.get(name) or []


def load(root):
    path = root / 'content' / 'publications.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise BuildError(f'{path} not found')
    except json.JSONDecodeError as e:
        raise BuildError(f'{path}: invalid JSON: {e}')
    items = data.get('publications') if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise BuildError(f'{path}: expected an object with a "publications" list')
    return items


def validate(items, root):
    seen = set()
    for p in items:
        slug = p.get('slug')
        if not isinstance(slug, str) or not news.SLUG_RE.match(slug) or len(slug) > news.SLUG_MAX:
            raise BuildError(f'bad slug {slug!r}: expected [a-z0-9-], max {news.SLUG_MAX} chars')
        if slug in seen:
            raise BuildError(f'duplicate slug {slug!r}')
        seen.add(slug)
        if not (p.get('title') or '').strip():
            raise BuildError(f'{slug}: empty title')
        if p.get('type') not in TYPES:
            raise BuildError(f'{slug}: unknown type {p.get("type")!r}, expected one of {list(TYPES)}')
        if not isinstance(p.get('year'), int):
            raise BuildError(f'{slug}: "year" must be a number')
        news.parse_date(p.get('date'))
        if p.get('date_end') and (not p.get('date') or news.parse_date(p['date_end']) < news.parse_date(p['date'])):
            raise BuildError(f'{slug}: "date_end" needs a "date" and must not precede it')
        for key in ('pdf', 'cover'):
            path = p.get(key) or ''
            if not path or not (root / path).is_file():
                raise BuildError(f'{slug}: {key} file {path!r} does not exist')
        if (p.get('language') or 'uz') not in GOST_WORDS:
            raise BuildError(f'{slug}: unsupported language {p.get("language")!r}')
        for person in p.get('people') or []:
            if person.get('role') not in ROLES:
                raise BuildError(f'{slug}: unknown role {person.get("role")!r}, expected one of {list(ROLES)}')
            if not (person.get('family') or '').strip():
                raise BuildError(f'{slug}: a person without "family"')
        for entry in p.get('toc') or []:
            if 'section' in entry:
                if not (entry.get('section') or '').strip():
                    raise BuildError(f'{slug}: an empty toc section')
                continue
            if not (entry.get('title') or '').strip() or not isinstance(entry.get('page'), int):
                raise BuildError(f'{slug}: a toc entry needs "title" and a numeric "page"')


def sort_items(items):
    return sorted(items, key=lambda p: (p.get('date') or f'{p["year"]}-00-00', p['slug']), reverse=True)


def articles(item):
    """Пункты содержания без заголовков разделов (``{"section": …}``)."""
    return [e for e in item.get('toc') or [] if 'section' not in e]


def event_date(item, lang):
    """Дата конференции; двухдневная в одном месяце — «15–16-may, 2026»."""
    start, end = news.parse_date(item.get('date')), news.parse_date(item.get('date_end'))
    if start is None:
        return ''
    if end is None or end == start:
        return news.format_date(item['date'], lang)
    if (end.year, end.month) == (start.year, start.month):
        return news.format_date(item['date_end'], lang).replace(str(end.day), f'{start.day}–{end.day}', 1)
    return f'{news.format_date(item["date"], lang)} – {news.format_date(item["date_end"], lang)}'


# --------------------------------------------------------------------------- names and citations

def full_name(person):
    return ' '.join(x for x in (person.get('given'), person['family']) if x)


def initials(given):
    """«Nigora» → «N.»; уже сокращённое («B. Ye.», «O‘.») остаётся как есть."""
    return ' '.join(part if part.endswith('.') else f'{part[0]}.'
                    for part in re.split(r'[\s-]+', given or '') if part)


def people_by_role(item, roles):
    return [p for p in item.get('people') or [] if p['role'] in roles]


def responsible(item):
    """Авторы работы, а если их нет — её редакторы (для сборников)."""
    authors = people_by_role(item, ('author',))
    if authors:
        return authors, False
    order = {role: i for i, role in enumerate(EDITOR_ROLES)}
    editors = sorted(people_by_role(item, EDITOR_ROLES), key=lambda p: order[p['role']])
    # В записи сборника указывают ответственного редактора, если он есть.
    chief = [p for p in editors if p['role'] == 'chief_editor']
    return (chief or editors), True


def full_title(item, sep=': '):
    sub = item.get('subtitle')
    return f'{item["title"]}{sep}{sub}' if sub else item['title']


def page_url(item):
    return build_i18n.canonical('uz', f'{PAGE_PREFIX}{item["slug"]}.html')


def apa_names(people):
    names = [f'{p["family"]}, {initials(p.get("given"))}'.rstrip(', ') for p in people]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f'{names[0]}, & {names[1]}'
    return ', '.join(names[:-1]) + f', & {names[-1]}'


def mla_names(people):
    first = f'{people[0]["family"]}, {people[0].get("given") or ""}'.rstrip(', ')
    if len(people) == 1:
        return first
    if len(people) == 2:
        return f'{first}, and {full_name(people[1])}'
    return f'{first}, et al.'


def gost_lead(person):
    return f'{person["family"]} {initials(person.get("given"))}'.strip()


def gost_short(person):
    return f'{initials(person.get("given"))} {person["family"]}'.strip()


def source_line(item):
    """Издание, в котором вышла статья или тезисы: журнал / сборник, том, номер, страницы."""
    return item.get('source') or {}


def cite_gost(item):
    words = GOST_WORDS[item.get('language') or 'uz']
    people, edited = responsible(item)
    src = source_line(item)
    kind = item['type']
    if kind in ('article', 'thesis') and src.get('title'):
        lead = f'{gost_lead(people[0])} ' if people and not edited else ''
        resp = ', '.join(gost_short(p) for p in people) if people and not edited else ''
        text = f'{lead}{esc(item["title"])}'
        if resp:
            text += f' / {esc(resp)}'
        text += f' // {esc(src["title"])}. — {item["year"]}.'
        vol = ', '.join(x for x in (f'{words["vol"]} {src["volume"]}' if src.get('volume') else '',
                                    f'{words["no"]} {src["issue"]}' if src.get('issue') else '') if x)
        if vol:
            text += f' — {esc(vol)}.'
        if src.get('pages'):
            text += f' — {words["pp"]} {esc(src["pages"])}.'
        return text
    text = ''
    if people and not edited:
        text = f'{esc(gost_lead(people[0]))} '
    text += esc(item['title'])
    if item.get('subtitle'):
        text += f' : {esc(item["subtitle"])}'
    if item.get('date') and kind == 'proceedings':
        d, end = news.parse_date(item['date']), news.parse_date(item.get('date_end'))
        when = d.strftime('%d.%m.%Y')
        if end and end != d:
            when = (f'{d.day:02d}–{end.strftime("%d.%m.%Y")}' if (end.year, end.month) == (d.year, d.month)
                    else f'{when}–{end.strftime("%d.%m.%Y")}')
        text += f' ({esc(item.get("place") or "")}, {when})'
    if people:
        if edited:
            resp = f'{words[people[0]["role"]]} {", ".join(gost_short(p) for p in people)}'
        else:
            resp = ', '.join(gost_short(p) for p in people)
        text += f' / {esc(resp)}'
    imprint = ' : '.join(x for x in (item.get('place'), item.get('publisher')) if x)
    text += f'. — {esc(imprint)}, {item["year"]}.' if imprint else f'. — {item["year"]}.'
    if item.get('pages'):
        text += f' — {item["pages"]} {words["pages"]}'
    return text


def cite_apa(item):
    people, edited = responsible(item)
    src = source_line(item)
    who = apa_names(people) if people else ''
    if edited and people:
        who += ' (Eds.)' if len(people) > 1 else ' (Ed.)'
    head = f'{esc(who)}{"" if who.endswith(".") else "."} ' if who else ''
    head += f'({item["year"]}). '
    link = f'https://doi.org/{src["doi"]}' if src.get('doi') else page_url(item)
    if item['type'] in ('article', 'thesis') and src.get('title'):
        text = head + f'{esc(item["title"])}. <i>{esc(src["title"])}</i>'
        if src.get('volume'):
            text += f', <i>{esc(src["volume"])}</i>'
            if src.get('issue'):
                text += f'({esc(src["issue"])})'
        if src.get('pages'):
            text += f', {esc(src["pages"])}'
        return text + f'. {esc(link)}'
    text = head + f'<i>{esc(full_title(item))}</i>.'
    if item.get('publisher'):
        text += f' {esc(item["publisher"])}.'
    return text + f' {esc(link)}'


def cite_mla(item):
    people, edited = responsible(item)
    src = source_line(item)
    text = ''
    if people:
        text = esc(mla_names(people))
        if edited:
            text += ', editors' if len(people) > 1 else ', editor'
        text += ' ' if text.endswith('.') else '. '
    if item['type'] in ('article', 'thesis') and src.get('title'):
        text += f'“{esc(item["title"])}.” <i>{esc(src["title"])}</i>'
        if src.get('volume'):
            text += f', vol. {esc(src["volume"])}'
        if src.get('issue'):
            text += f', no. {esc(src["issue"])}'
        text += f', {item["year"]}'
        if src.get('pages'):
            text += f', pp. {esc(src["pages"])}'
        return text + '.'
    text += f'<i>{esc(full_title(item))}</i>.'
    if item.get('publisher'):
        text += f' {esc(item["publisher"])},'
    return text + f' {item["year"]}.'


def bibtex_key(item):
    people, _ = responsible(item)
    base = people[0]['family'] if people else item['slug'].split('-')[0]
    word = item['slug'].split('-')[0]
    return re.sub(r'[^a-z0-9]', '', f'{base}{item["year"]}{word}'.lower())


def bibtex_value(text):
    return str(text).replace('{', '').replace('}', '')


def cite_bibtex(item):
    people, edited = responsible(item)
    src = source_line(item)
    kind = {'article': 'article', 'thesis': 'inproceedings', 'proceedings': 'proceedings'}.get(item['type'], 'book')
    fields = [('title', full_title(item))]
    names = ' and '.join(f'{p["family"]}, {p.get("given") or ""}'.rstrip(', ') for p in people)
    if names:
        fields.append(('editor' if edited else 'author', names))
    if kind == 'article':
        fields += [('journal', src.get('title')), ('volume', src.get('volume')), ('number', src.get('issue')),
                   ('pages', (src.get('pages') or '').replace('–', '--'))]
    elif kind == 'inproceedings':
        fields += [('booktitle', src.get('title')), ('pages', (src.get('pages') or '').replace('–', '--'))]
    fields += [('publisher', item.get('publisher')), ('address', item.get('place')), ('year', item['year']),
               ('doi', src.get('doi')), ('url', page_url(item))]
    body = ',\n'.join(f'  {k} = {{{bibtex_value(v)}}}' for k, v in fields if v)
    return esc(f'@{kind}{{{bibtex_key(item)},\n{body}\n}}')


CITE_FORMATS = (('gost', 'GOST', cite_gost), ('apa', 'APA', cite_apa), ('mla', 'MLA', cite_mla),
                ('bibtex', 'BibTeX', cite_bibtex))


# --------------------------------------------------------------------------- assets

def stamped(path, lang, root):
    """Ссылка на CSS/JS с ``?v=<хеш>`` — так же, как их штампует stamp_assets.py."""
    digest = hashlib.md5((root / path).read_bytes()).hexdigest()[:10]
    return f'{news.asset(path, lang)}?v={digest}'


def file_size(path, lang):
    size = path.stat().st_size
    if size >= 1024 * 1024:
        text = f'{size / 1024 / 1024:.1f} MB'
    else:
        text = f'{max(1, round(size / 1024))} KB'
    return text if lang == 'en' else text.replace('.', ',')


def pdf_href(item, lang, page=None):
    href = news.asset(item['pdf'], lang)
    return f'{href}#page={page}' if page else href


def type_label(item, lang, plural=False):
    return LABELS[lang]['types'][item['type']][1 if plural else 0]


def language_names(item, lang):
    names = LABELS[lang]['langs']
    return ', '.join(names.get(code, code) for code in item.get('languages') or [])


def search_text(value):
    return re.sub(r'\s+', ' ', value).strip().lower()


# --------------------------------------------------------------------------- page parts

def crumbs(lang, tail=None):
    labels = LABELS[lang]
    line = (f'<a href="index.html">{esc(labels["home"])}</a> <span class="sep">/</span> '
            f'<a href="research.html">{esc(labels["research"])}</a> <span class="sep">/</span> ')
    if tail is None:
        return line + f'<span>{esc(labels["section"])}</span>'
    return line + f'<a href="{LIST_PAGE}">{esc(labels["section"])}</a>'


def section(sid, body, extra_class=''):
    cls = f'sppb-section pub-section {extra_class}'.strip()
    return (f'<section id="{sid}" class="{cls}"><div class="sppb-row-container"><div class="sppb-row">'
            f'<div class="sppb-row-column"><div class="sppb-column"><div class="sppb-column-addons">'
            f'{body}</div></div></div></div></div></section>')


def people_block(item, lang):
    labels = LABELS[lang]
    out = ''
    for role in ROLES:
        group = people_by_role(item, (role,))
        if not group:
            continue
        rows = ''
        for person in group:
            aff = field(person, 'affiliation', lang)
            aff = f'<span>{esc(aff)}</span>' if aff else ''
            rows += f'<li><b>{esc(full_name(person))}</b>{aff}</li>'
        title = labels['roles'][role][1 if len(group) > 1 else 0]
        # Длинный список (оргкомитет) занимает всю ширину и идёт в колонки.
        wide = ' pub-people-group--wide' if len(group) > 4 else ''
        out += (f'<div class="pub-people-group{wide}"><h2 class="pub-h">{esc(title)}</h2>'
                f'<ul class="pub-people">{rows}</ul></div>')
    return f'<div class="pub-block pub-block--people">{out}</div>' if out else ''


def toc_block(item, lang):
    labels = LABELS[lang]
    entries = item.get('toc') or []
    if not entries:
        return ''
    rows = ''
    for entry in entries:
        if 'section' in entry:
            rows += f'<li class="pub-toc-section">{esc(entry["section"])}</li>'
            continue
        byline = entry.get('byline') or ''
        haystack = search_text(f'{entry["title"]} {byline}')
        by = f'<span class="pub-toc-by">{esc(byline)}</span>' if byline else ''
        rows += (f'<li data-q="{esc(haystack)}"><a href="{esc(pdf_href(item, lang, entry["page"]))}" '
                 f'target="_blank" rel="noopener" title="{esc(labels["page_title"])}">'
                 f'<span class="pub-toc-title">{esc(entry["title"])}</span>{by}</a>'
                 f'<span class="pub-toc-page">{labels["page_abbr"]} {entry["page"]}</span></li>')
    count = len(articles(item))
    return (f'<div class="pub-block pub-toc" data-pub-toc data-more="{esc(labels["show_all"](count))}" '
            f'data-less="{esc(labels["show_less"])}">'
            f'<div class="pub-toc-head"><h2 class="pub-h">{esc(labels["toc"])}</h2>'
            f'<span class="pub-toc-count">{esc(labels["toc_count"](count))}</span></div>'
            f'<label class="pub-search pub-search--small">{ICON_SEARCH}'
            f'<input type="search" data-pub-toc-q placeholder="{esc(labels["toc_search"])}" '
            f'aria-label="{esc(labels["toc_search"])}"></label>'
            f'<ol class="pub-toc-list">{rows}</ol>'
            f'<p class="pub-empty" data-pub-toc-empty hidden>{esc(labels["toc_empty"])}</p></div>')


def refs_block(item, lang):
    refs = item.get('references') or []
    if not refs:
        return ''
    rows = ''.join(f'<li>{esc(r)}</li>' for r in refs)
    return f'<div class="pub-block"><h2 class="pub-h">{esc(LABELS[lang]["refs"])}</h2><ol class="pub-refs">{rows}</ol></div>'


def meta_rows(item, lang):
    labels = LABELS[lang]
    rows = []
    title = field(item, 'title', lang)
    if title != item['title']:
        rows.append((labels['original'], esc(full_title(item))))
    src = source_line(item)
    if src.get('title'):
        vol = labels['volume'](src.get('volume'), src.get('issue'))
        rows.append((labels['source'], esc(field(src, 'title', lang)) + (f', {esc(vol)}' if vol else '')))
        if src.get('pages'):
            rows.append((labels['range'], esc(src['pages'])))
    if item.get('date'):
        date = event_date(item, lang)
        if item['type'] == 'proceedings':
            place = field(item, 'place', lang)
            rows.append((labels['event'], esc(f'{date}, {place}' if place else date)))
        else:
            rows.append((labels['published'], esc(date)))
    rows.append((labels['year'], str(item['year'])))
    if item.get('publisher'):
        rows.append((labels['publisher'], esc(field(item, 'publisher', lang))))
    rows.append((labels['type'], esc(type_label(item, lang))))
    if item.get('pages'):
        rows.append((labels['pages'], esc(labels['pages_n'](item['pages']))))
    if item.get('languages'):
        rows.append((labels['languages'], esc(language_names(item, lang))))
    if src.get('doi'):
        doi = esc(src['doi'])
        rows.append((labels['doi'], f'<a href="https://doi.org/{doi}" target="_blank" rel="noopener">{doi}</a>'))
    if item.get('license'):
        rows.append((labels['license'], esc(item['license'])))
    if item.get('copyright'):
        rows.append((labels['copyright'], esc(item['copyright'])))
    return ''.join(f'<div><dt>{esc(k)}</dt><dd>{v}</dd></div>' for k, v in rows)


def cite_block(item, lang):
    labels = LABELS[lang]
    tabs, panes = '', ''
    for i, (key, name, fn) in enumerate(CITE_FORMATS):
        selected = 'true' if i == 0 else 'false'
        tabs += (f'<button type="button" role="tab" id="pub-cite-tab-{key}" aria-controls="pub-cite-{key}" '
                 f'aria-selected="{selected}" data-pub-cite-tab="{key}">{name}</button>')
        hidden = '' if i == 0 else ' hidden'
        tag = 'pre' if key == 'bibtex' else 'p'
        panes += (f'<{tag} class="pub-cite-text" role="tabpanel" id="pub-cite-{key}" '
                  f'aria-labelledby="pub-cite-tab-{key}"{hidden}>{fn(item)}</{tag}>')
    return (f'<div class="pub-cite" data-pub-cite><h2 class="pub-h">{esc(labels["cite"])}</h2>'
            f'<div class="pub-cite-tabs" role="tablist">{tabs}</div>{panes}'
            f'<button type="button" class="pub-copy" data-pub-copy data-done="{esc(labels["copied"])}">'
            f'{esc(labels["copy"])}</button></div>')


def item_card(item, lang):
    """Строка каталога (и блока «Другие публикации»)."""
    labels = LABELS[lang]
    href = f'{PAGE_PREFIX}{item["slug"]}.html'
    title = field(item, 'title', lang)
    subtitle = field(item, 'subtitle', lang)
    sub = f'<p class="pub-item-sub">{esc(subtitle)}</p>' if subtitle else ''
    people, edited = responsible(item)
    who = ''
    if people:
        if edited:
            role = labels['roles'][people[0]['role']][1 if len(people) > 1 else 0]
        else:
            role = labels['roles']['author'][1 if len(people) > 1 else 0]
        who = f'<p class="pub-item-people"><span>{esc(role)}:</span> {esc(", ".join(full_name(p) for p in people))}</p>'
    facts = []
    if item.get('publisher'):
        facts.append(field(item, 'publisher', lang))
    src = source_line(item)
    if src.get('title'):
        facts.append(field(src, 'title', lang))
    if item.get('date') and item['type'] == 'proceedings':
        place = field(item, 'place', lang)
        facts.append(', '.join(x for x in (place, event_date(item, lang)) if x))
    if item.get('pages'):
        facts.append(labels['pages_n'](item['pages']))
    if articles(item):
        facts.append(labels['materials'](len(articles(item))))
    # Пробел между фактами — место переноса строки; точка-разделитель
    # остаётся в конце строки (см. .pub-item-facts в publications.css).
    facts_html = ' '.join(f'<span>{esc(f)}</span>' for f in facts)
    keywords = ' '.join(list_field(item, 'keywords', lang) + (item.get('keywords') or []))
    names = ' '.join(full_name(p) for p in item.get('people') or [])
    haystack = search_text(' '.join([title, item['title'], subtitle, item.get('subtitle') or '', names, keywords,
                                     src.get('title') or '']))
    cover = news.asset(item['cover'], lang)
    return (f'<li class="pub-item" data-pub-item data-slug="{esc(item["slug"])}" data-type="{item["type"]}" '
            f'data-year="{item["year"]}" data-q="{esc(haystack)}">'
            f'<a class="pub-item-cover" href="{href}" tabindex="-1" aria-hidden="true">'
            f'<img src="{esc(cover)}" alt="" loading="lazy"></a>'
            f'<div class="pub-item-body">'
            f'<div class="pub-item-meta"><span class="pub-kind">{esc(type_label(item, lang))}</span>'
            f'<span>{item["year"]}</span></div>'
            f'<h3 class="pub-item-title"><a href="{href}">{esc(title)}</a></h3>{sub}{who}'
            f'<p class="pub-item-facts">{facts_html}</p>'
            f'<div class="pub-hits" data-pub-hits hidden><p>{esc(labels["hits"])}</p><ul></ul></div>'
            f'<div class="pub-item-actions"><a class="pub-btn pub-btn--primary" href="{href}">{esc(labels["more"])}</a>'
            f'<a class="pub-btn" href="{esc(pdf_href(item, lang))}" target="_blank" rel="noopener">{ICON_PDF}PDF</a>'
            f'</div></div></li>')


def related_block(lang):
    table = i18n.load_table(lang) if lang != 'uz' else {}
    cells = ''.join(f'<div class="col-md-6 col-lg-4"><a class="nsu-rel" href="{page}"><span>'
                    f'{esc(table.get(label, label))}</span><i class="fas fa-arrow-right"></i></a></div>'
                    for page, label in RESEARCH_PAGES)
    return (f'<section id="nsu-related" class="sppb-section nsu-related"><div class="sppb-row-container">'
            f'<div class="sppb-row"><div class="sppb-row-column"><div class="sppb-column"><div class="sppb-column-addons">'
            f'<div class="sppb-addon-wrapper addon-root-text-block"><div class="clearfix">'
            f'<div class="sppb-addon sppb-addon-text-block"><h3 class="sppb-addon-title">{esc(LABELS[lang]["related"])}</h3>'
            f'<div class="sppb-addon-content"><div class="row nsu-rel-row">{cells}</div></div></div></div></div>'
            f'</div></div></div></div></div></section>')


# --------------------------------------------------------------------------- head

def scholar_meta(item):
    """Теги Highwire Press (citation_*), по которым Google Scholar индексирует работу."""
    people, _ = responsible(item)
    src = source_line(item)
    tags = [('citation_title', full_title(item))]
    tags += [('citation_author', f'{p["family"]}, {p.get("given") or ""}'.rstrip(', ')) for p in people]
    date = item.get('date')
    tags.append(('citation_publication_date', date.replace('-', '/') if date else str(item['year'])))
    if item.get('publisher'):
        tags.append(('citation_publisher', item['publisher']))
    if item['type'] == 'article' and src.get('title'):
        tags.append(('citation_journal_title', src['title']))
    if item['type'] in ('thesis', 'proceedings'):
        tags.append(('citation_conference_title', src.get('title') or full_title(item)))
    for key, tag in (('volume', 'citation_volume'), ('issue', 'citation_issue'), ('doi', 'citation_doi')):
        if src.get(key):
            tags.append((tag, src[key]))
    pages = (src.get('pages') or '').replace('—', '–').split('–')
    if pages[0]:
        tags.append(('citation_firstpage', pages[0].strip()))
        if len(pages) > 1:
            tags.append(('citation_lastpage', pages[1].strip()))
    tags.append(('citation_language', item.get('language') or 'uz'))
    keywords = item.get('keywords') or []
    if keywords:
        tags.append(('citation_keywords', '; '.join(keywords)))
    tags.append(('citation_abstract_html_url', page_url(item)))
    tags.append(('citation_pdf_url', f'{SITE}/{item["pdf"]}'))
    return ''.join(f'\n\t<meta name="{k}" content="{esc(str(v))}">' for k, v in tags)


def finish(html_text, lang, root, extra_head=''):
    link = f'\n\t<link href="{stamped(CSS, lang, root)}" rel="stylesheet">'
    return news.sub_once(r'</head>', lambda m: f'{link}{extra_head}\n</head>', html_text, 'head')


def script_tag(lang, root):
    return f'<script src="{stamped(JS, lang, root)}" defer></script>'


def mark_research_menu(head):
    """Подсвечивает в меню пункт «Ilmiy faoliyat» (выпадающий, с research.html внутри)."""
    anchor = head.find('class="dd__link" href="research.html"')
    if anchor < 0:
        return head
    btn = head.rfind('class="menu__btn"', 0, anchor)
    if btn < 0:
        return head
    return head[:btn] + 'class="menu__btn is-active"' + head[btn + len('class="menu__btn"'):]


def make_shell(donor, where, lang):
    shell = news.Shell.from_donor(donor, where=where, lang=lang, active=LIST_PAGE)
    shell.head = mark_research_menu(shell.head)
    return shell


# --------------------------------------------------------------------------- pages

def render_item(item, items, shell, lang, root):
    labels = LABELS[lang]
    title = field(item, 'title', lang)
    sub = field(item, 'subtitle', lang)
    hero_extra = f'<p class="nsu-hero-sub">{esc(sub)}</p>' if sub else ''
    hero = (f'<section id="sp-page-title" class="nsu-page-hero pub-hero"><div class="container"><div class="container-inner">'
            f'<div class="nsu-hero-inner"><nav class="nsu-crumbs" aria-label="breadcrumb">{crumbs(lang, title)}</nav>'
            f'<span class="pub-kind pub-kind--hero">{esc(type_label(item, lang))} · {item["year"]}</span>'
            f'<h1>{esc(title)}</h1>{hero_extra}</div></div></div></section>')

    keywords = list_field(item, 'keywords', lang)
    kw = ''
    if keywords:
        tags = ''.join(f'<li>{esc(k)}</li>' for k in keywords)
        kw = f'<div class="pub-block"><h2 class="pub-h">{esc(labels["keywords"])}</h2><ul class="pub-tags">{tags}</ul></div>'
    abstract = field(item, 'abstract', lang).strip()
    ab = ''
    if abstract:
        paras = ''.join(f'<p>{esc(p)}</p>' for p in abstract.split('\n\n') if p.strip())
        ab = f'<div class="pub-block pub-abstract"><h2 class="pub-h">{esc(labels["abstract"])}</h2>{paras}</div>'

    pdf_path = root / item['pdf']
    pdf = esc(pdf_href(item, lang))
    download_name = esc(pathlib.Path(item['pdf']).name)
    side = (f'<aside class="pub-side">'
            f'<a class="pub-cover" href="{pdf}" target="_blank" rel="noopener">'
            f'<img src="{esc(news.asset(item["cover"], lang))}" alt="{esc(title)}"></a>'
            f'<div class="pub-actions">'
            f'<a class="pub-btn pub-btn--primary" href="{pdf}" target="_blank" rel="noopener">{ICON_PDF}{esc(labels["open_pdf"])}</a>'
            f'<a class="pub-btn" href="{pdf}" download="{download_name}">{ICON_DOWNLOAD}{esc(labels["download"])}'
            f'<small>PDF, {esc(file_size(pdf_path, lang))}</small></a></div>'
            f'<dl class="pub-meta">{meta_rows(item, lang)}</dl></aside>')
    main = (f'<div class="pub-main">{people_block(item, lang)}{kw}{ab}'
            f'{toc_block(item, lang)}{refs_block(item, lang)}</div>')
    # Порядок в разметке — обложка с PDF, текст, цитирование: на телефоне
    # кнопки PDF оказываются сверху, а на компьютере сетка ставит боковую
    # колонку справа (см. .pub-layout в publications.css).
    body = section('pub-work', f'<div class="pub-layout">{side}{main}{cite_block(item, lang)}</div>')

    others = [p for p in sort_items(items) if p['slug'] != item['slug']][:4]
    if others:
        cards = ''.join(item_card(p, lang) for p in others)
        body += section('pub-others', f'<h2 class="pub-section-title">{esc(labels["others"])}</h2>'
                                      f'<ol class="pub-list pub-list--compact">{cards}</ol>', 'nsu-alt')

    content = hero + news.MAIN_OPEN + body + news.cta(lang) + news.MAIN_CLOSE
    description = abstract[:300] or title
    page = f'{PAGE_PREFIX}{item["slug"]}.html'
    out = shell.render(title, description, news.asset(item['cover'], lang), content,
                       before_body_end=script_tag(lang, root), page=page)
    return finish(out, lang, root, scholar_meta(item))


def render_list(items, shell, lang, root):
    labels = LABELS[lang]
    items = sort_items(items)
    title = labels['section']
    hero = news.hero(news.asset(LIST_HERO, lang), crumbs(lang), title,
                     f'<p class="nsu-hero-sub">{esc(labels["list_sub"])}</p>')

    present = [t for t in TYPES if any(p['type'] == t for p in items)]
    chips = (f'<button type="button" class="pub-chip is-active" data-pub-type="" aria-pressed="true">'
             f'{esc(labels["all"])}<span>{len(items)}</span></button>')
    for t in present:
        n = sum(1 for p in items if p['type'] == t)
        chips += (f'<button type="button" class="pub-chip" data-pub-type="{t}" aria-pressed="false">'
                  f'{esc(labels["types"][t][1])}<span>{n}</span></button>')
    years = sorted({p['year'] for p in items}, reverse=True)
    options = f'<option value="">{esc(labels["all_years"])}</option>' + ''.join(
        f'<option value="{y}">{y}</option>' for y in years)
    tools = (f'<div class="pub-tools">'
             f'<label class="pub-search">{ICON_SEARCH}<input type="search" data-pub-q '
             f'placeholder="{esc(labels["search"])}" aria-label="{esc(labels["search_label"])}"></label>'
             f'<div class="pub-filters"><div class="pub-chips" role="group">{chips}</div>'
             f'<select class="pub-year" data-pub-year aria-label="{esc(labels["all_years"])}">{options}</select></div>'
             f'</div>')

    # Содержание сборников для поиска «внутри книги»: [заголовок, авторы, страница, ссылка].
    index = {p['slug']: [[e['title'], e.get('byline') or '', e['page'], pdf_href(p, lang, e['page'])]
                         for e in articles(p)]
             for p in items if articles(p)}
    index_json = json.dumps(index, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')

    cards = ''.join(item_card(p, lang) for p in items)
    body = (f'<div class="pub-catalog" data-pub-catalog data-page-abbr="{esc(labels["page_abbr"])}" '
            f'data-count-forms="{esc(count_forms(lang))}" data-hits-more="{esc(labels["hits_more"])}">'
            f'<p class="pub-intro">{esc(labels["intro"])}</p>{tools}'
            f'<p class="pub-count" data-pub-count aria-live="polite">{esc(labels["count"](len(items)))}</p>'
            f'<ol class="pub-list">{cards}</ol>'
            f'<p class="pub-empty" data-pub-empty hidden>{esc(labels["empty"])}</p>'
            f'<script type="application/json" data-pub-index>{index_json}</script></div>')
    content = (hero + news.MAIN_OPEN + section('pub-catalog', body) + related_block(lang)
               + news.cta(lang) + news.MAIN_CLOSE)
    out = shell.render(title, labels['list_sub'], news.asset(LIST_HERO, lang), content,
                       before_body_end=script_tag(lang, root), page=LIST_PAGE)
    return finish(out, lang, root)


def count_forms(lang):
    """Формы слова для счётчика найденного: скрипт подставляет число в ``{n}``."""
    if lang == 'ru':
        return 'публикация|публикации|публикаций'
    if lang == 'en':
        return 'publication|publications|publications'
    return 'ta nashr|ta nashr|ta nashr'


# --------------------------------------------------------------------------- build

def build(root=ROOT):
    root = pathlib.Path(root)
    items = load(root)
    validate(items, root)
    result = {'written': [], 'deleted': [], 'unchanged': []}

    def emit(name, text):
        (result['written'] if news.write_if_changed(root / name, text) else result['unchanged']).append(name)

    for lang in news.languages(root):
        folder = i18n.LANG_DIR.get(lang) or ''
        base = f'{folder}/' if folder else ''
        donor = (root / base / news.DONOR).read_text(encoding='utf-8')
        shell = make_shell(donor, f'{base}{news.DONOR}', lang)
        wanted = set()
        for item in items:
            name = f'{base}{PAGE_PREFIX}{item["slug"]}.html'
            wanted.add(name)
            emit(name, render_item(item, items, shell, lang, root))
        emit(f'{base}{LIST_PAGE}', render_list(items, shell, lang, root))
        for stale in sorted((root / base if base else root).glob(f'{PAGE_PREFIX}*.html')):
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
        raise SystemExit(f'build_publications: {e}')
    print(f"written: {len(result['written'])}, unchanged: {len(result['unchanged'])}, "
          f"deleted: {len(result['deleted'])}")
    for name in result['written']:
        print(f'  + {name}')
    for name in result['deleted']:
        print(f'  - {name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
