import importlib.util
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('build_publications', ROOT / 'scripts' / 'build_publications.py')
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)


def person(family, given, role, **over):
    base = {'family': family, 'given': given, 'role': role, 'affiliation': 'NavDU'}
    base.update(over)
    return base


def work(**over):
    base = {
        'slug': 'test-tuplam', 'type': 'proceedings', 'language': 'uz',
        'title': 'Sinov to‘plami', 'subtitle': 'Xalqaro ilmiy konferensiya materiallari',
        'date': '2025-04-10', 'year': 2025, 'place': 'Navoiy', 'publisher': 'Navoiy davlat universiteti',
        'people': [person('Safarova', 'Nigora', 'chief_editor'), person('Karimov', 'Elyor', 'reviewer')],
        'keywords': ['falsafa'], 'abstract': 'Annotatsiya matni.', 'languages': ['uz', 'ru'],
        'pages': 120, 'pdf': 'files/publications/test-tuplam.pdf',
        'cover': 'images/nsu/publications/test-tuplam-cover.jpg',
        'toc': [{'title': 'BIRINCHI MAQOLA', 'byline': 'Aliyev A.', 'page': 5},
                {'title': 'IKKINCHI MAQOLA', 'byline': 'Valiyev V.', 'page': 9}],
    }
    base.update(over)
    return base


def article(**over):
    base = work(slug='test-maqola', type='article', subtitle=None, date='2025-10-13', toc=[],
                people=[person('Davlatov', 'Abror', 'author')],
                source={'title': 'American Journal of Alternative Education', 'volume': '2', 'issue': '10',
                        'pages': '60–62', 'doi': '10.1234/ajae.1306'},
                pdf='files/publications/test-maqola.pdf', cover='images/nsu/publications/test-maqola-cover.jpg')
    base.update(over)
    return base


DONOR = '''<!DOCTYPE html><html><head>
\t<meta name="og:title" content="Bogʻlanish — NavDU">
\t<meta name="og:image" content="images/nsu/nsu-seal-navy.png">
\t<meta name="description" content="Biz bilan bogʻlanish.">
\t<title>Bogʻlanish — NavDU</title>
</head><body class="nsu-inner">
<div class="menu__item"><button class="menu__btn" type="button">Ilmiy faoliyat</button><div class="dd"><div class="dd__panel"><a class="dd__link" href="research.html">Ilmiy faoliyat</a><a class="dd__link" href="publications.html">Ilmiy nashrlar</a></div></div></div>
<a class="menu__link is-active" href="contact.html">Bogʻlanish</a>
\t\t\t\t<section id="sp-page-title" class="nsu-page-hero">OLD CONTENT</section><section id="sp-main-body">OLD</section><!-- ====== FOOTER (из Макета 2) ====== -->
<footer>F</footer>
</body>
</html>
'''


class CitationTests(unittest.TestCase):
    def test_gost_for_edited_proceedings(self):
        text = bp.cite_gost(work())
        self.assertEqual(
            text,
            'Sinov to‘plami : Xalqaro ilmiy konferensiya materiallari (Navoiy, 10.04.2025) / '
            'mas’ul muharrir N. Safarova. — Navoiy : Navoiy davlat universiteti, 2025. — 120 b.')

    def test_reviewers_are_not_editors(self):
        self.assertNotIn('Karimov', bp.cite_gost(work()))
        self.assertNotIn('Karimov', bp.cite_apa(work()))

    def test_apa_for_edited_proceedings(self):
        self.assertEqual(
            bp.cite_apa(work()),
            'Safarova, N. (Ed.). (2025). <i>Sinov to‘plami: Xalqaro ilmiy konferensiya materiallari</i>. '
            'Navoiy davlat universiteti. https://ndu.uz/publication-test-tuplam.html')

    def test_apa_for_an_article_links_the_doi(self):
        self.assertEqual(
            bp.cite_apa(article()),
            'Davlatov, A. (2025). Sinov to‘plami. <i>American Journal of Alternative Education</i>, '
            '<i>2</i>(10), 60–62. https://doi.org/10.1234/ajae.1306')

    def test_gost_for_an_article(self):
        self.assertEqual(
            bp.cite_gost(article()),
            'Davlatov A. Sinov to‘plami / A. Davlatov // American Journal of Alternative Education. '
            '— 2025. — T. 2, № 10. — B. 60–62.')

    def test_mla_shortens_three_authors(self):
        people = [person('A', 'Ann', 'author'), person('B', 'Bob', 'author'), person('C', 'Cid', 'author')]
        self.assertTrue(bp.cite_mla(article(people=people)).startswith('A, Ann, et al. “Sinov to‘plami.”'))

    def test_apa_joins_two_authors_with_an_ampersand(self):
        people = [person('Aliyev', 'Anvar Bek', 'author'), person('Valiyeva', 'Vasila', 'author')]
        self.assertTrue(bp.cite_apa(article(people=people)).startswith('Aliyev, A. B., &amp; Valiyeva, V. (2025).'))

    def test_bibtex_kinds(self):
        self.assertIn('@proceedings{safarova2025test,', bp.cite_bibtex(work()))
        self.assertIn('editor = {Safarova, Nigora}', bp.cite_bibtex(work()))
        out = bp.cite_bibtex(article())
        self.assertIn('@article{', out)
        self.assertIn('author = {Davlatov, Abror}', out)
        self.assertIn('pages = {60--62}', out)

    def test_citations_are_escaped(self):
        self.assertIn('&lt;b&gt;', bp.cite_apa(work(title='<b>x')))


class SectionAndDateTests(unittest.TestCase):
    def test_initials_keep_given_abbreviations(self):
        self.assertEqual(bp.initials('Nigora'), 'N.')
        self.assertEqual(bp.initials('Anvar Bek'), 'A. B.')
        self.assertEqual(bp.initials('B. Ye.'), 'B. Ye.')
        self.assertEqual(bp.initials('O‘. T.'), 'O‘. T.')

    def test_two_day_conference_in_one_month(self):
        item = work(date='2026-05-15', date_end='2026-05-16')
        self.assertEqual(bp.event_date(item, 'uz'), '15–16-may, 2026')
        self.assertEqual(bp.event_date(item, 'ru'), '15–16 мая 2026')
        self.assertEqual(bp.event_date(item, 'en'), '15–16 May 2026')
        self.assertIn('(Navoiy, 15–16.05.2026)', bp.cite_gost(item))

    def test_single_day_and_no_date(self):
        self.assertEqual(bp.event_date(work(), 'uz'), '10-aprel, 2025')
        self.assertEqual(bp.event_date(work(date=None), 'uz'), '')

    def test_sections_are_headings_not_articles(self):
        item = work(toc=[{'section': 'I sho‘ba. Kimyo'}, {'title': 'MAQOLA', 'byline': 'A', 'page': 5},
                         {'section': 'II sho‘ba. Biologiya'}, {'title': 'IKKINCHI', 'byline': 'B', 'page': 9}])
        self.assertEqual(len(bp.articles(item)), 2)
        block = bp.toc_block(item, 'uz')
        self.assertIn('<li class="pub-toc-section">I sho‘ba. Kimyo</li>', block)
        self.assertIn('2 ta material', block)
        self.assertEqual(block.count('data-q='), 2)

    def test_committee_is_listed_but_not_cited(self):
        people = [person('Sobirov', 'Bahodir', 'committee'), person('Ummatova', 'Muxayyo', 'technical_editor')]
        item = work(people=people)
        self.assertIn('Tashkiliy qo‘mita a’zosi', bp.people_block(item, 'uz'))
        self.assertIn('Texnik muharrir', bp.people_block(item, 'uz'))
        self.assertNotIn('Sobirov', bp.cite_gost(item))
        self.assertNotIn('Ummatova', bp.cite_apa(item))

    def test_long_groups_go_full_width(self):
        people = [person(f'F{i}', 'G', 'committee') for i in range(6)]
        self.assertIn('pub-people-group--wide', bp.people_block(work(people=people), 'uz'))


class ScholarMetaTests(unittest.TestCase):
    def test_tags_for_proceedings(self):
        meta = bp.scholar_meta(work())
        self.assertIn('<meta name="citation_author" content="Safarova, Nigora">', meta)
        self.assertIn('<meta name="citation_publication_date" content="2025/04/10">', meta)
        self.assertIn('content="https://ndu.uz/files/publications/test-tuplam.pdf"', meta)
        self.assertNotIn('Karimov', meta)

    def test_tags_for_an_article(self):
        meta = bp.scholar_meta(article())
        self.assertIn('<meta name="citation_journal_title" content="American Journal of Alternative Education">', meta)
        self.assertIn('<meta name="citation_firstpage" content="60">', meta)
        self.assertIn('<meta name="citation_lastpage" content="62">', meta)
        self.assertIn('<meta name="citation_doi" content="10.1234/ajae.1306">', meta)


class LabelTests(unittest.TestCase):
    def test_russian_plurals(self):
        count = bp.LABELS['ru']['toc_count']
        self.assertEqual(count(1), '1 материал')
        self.assertEqual(count(3), '3 материала')
        self.assertEqual(count(11), '11 материалов')
        self.assertEqual(count(140), '140 материалов')

    def test_every_language_has_every_label(self):
        keys = set(bp.LABELS['uz'])
        for lang in ('ru', 'en'):
            self.assertEqual(set(bp.LABELS[lang]), keys, lang)
            self.assertEqual(set(bp.LABELS[lang]['types']), set(bp.TYPES))
            self.assertEqual(set(bp.LABELS[lang]['roles']), set(bp.ROLES))


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / 'contact.html').write_text(DONOR, encoding='utf-8')
        for path in (bp.CSS, bp.JS):
            (self.tmp / path).parent.mkdir(parents=True, exist_ok=True)
            (self.tmp / path).write_text('/* x */', encoding='utf-8')
        self.write([work()])

    def write(self, items):
        for item in items:
            for key in ('pdf', 'cover'):
                target = self.tmp / item[key]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'%PDF-1.4 test' if key == 'pdf' else b'jpg')
        (self.tmp / 'content').mkdir(exist_ok=True)
        (self.tmp / 'content' / 'publications.json').write_text(
            json.dumps({'publications': items}, ensure_ascii=False), encoding='utf-8')

    def read(self, name):
        return (self.tmp / name).read_text(encoding='utf-8')

    def test_writes_the_catalogue_and_the_work_page(self):
        result = bp.build(self.tmp)
        self.assertEqual(sorted(result['written']), ['publication-test-tuplam.html', 'publications.html'])
        page = self.read('publication-test-tuplam.html')
        self.assertIn('<title>Sinov to‘plami — NavDU</title>', page)
        self.assertIn('href="files/publications/test-tuplam.pdf#page=9"', page)
        self.assertIn('Mas’ul muharrir', page)
        self.assertIn('Taqrizchi', page)
        self.assertIn('<meta name="citation_title"', page)
        self.assertIn('assets/css/publications.css?v=', page)
        self.assertIn('assets/js/publications.js?v=', page)
        self.assertNotIn('OLD CONTENT', page)
        catalogue = self.read('publications.html')
        self.assertIn('href="publication-test-tuplam.html"', catalogue)
        self.assertIn('"test-tuplam":[["BIRINCHI MAQOLA","Aliyev A.",5,', catalogue)

    def test_research_menu_item_is_highlighted(self):
        bp.build(self.tmp)
        page = self.read('publications.html')
        self.assertIn('<button class="menu__btn is-active" type="button">Ilmiy faoliyat', page)
        self.assertIn('<a class="menu__link" href="contact.html">', page)

    def test_second_run_changes_nothing(self):
        bp.build(self.tmp)
        result = bp.build(self.tmp)
        self.assertEqual(result['written'], [])

    def test_removed_work_loses_its_page(self):
        bp.build(self.tmp)
        self.write([article()])
        result = bp.build(self.tmp)
        self.assertEqual(result['deleted'], ['publication-test-tuplam.html'])
        self.assertTrue((self.tmp / 'publication-test-maqola.html').is_file())

    def test_newest_work_comes_first(self):
        self.write([work(), article()])
        bp.build(self.tmp)
        catalogue = self.read('publications.html')
        self.assertLess(catalogue.find('data-slug="test-maqola"'), catalogue.find('data-slug="test-tuplam"'))

    def test_translated_pages_point_one_level_up(self):
        (self.tmp / 'ru').mkdir()
        (self.tmp / 'ru' / 'contact.html').write_text(DONOR.replace('assets/', '../assets/'), encoding='utf-8')
        self.write([work(title_ru='Тестовый сборник')])
        bp.build(self.tmp)
        page = self.read('ru/publication-test-tuplam.html')
        self.assertIn('<h1>Тестовый сборник</h1>', page)
        self.assertIn('href="../files/publications/test-tuplam.pdf#page=5"', page)
        self.assertIn('../assets/css/publications.css?v=', page)
        self.assertIn('Ответственный редактор', page)
        # Цитата — на языке самой работы, а не страницы.
        self.assertIn('mas’ul muharrir N. Safarova', page)
        self.assertIn('Оригинальное название', page)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        for key in ('pdf', 'cover'):
            target = self.tmp / work()[key]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'x')

    def check(self, item, message):
        with self.assertRaises(bp.BuildError) as ctx:
            bp.validate([item], self.tmp)
        self.assertIn(message, str(ctx.exception))

    def test_valid_work_passes(self):
        bp.validate([work()], self.tmp)

    def test_unknown_type(self):
        self.check(work(type='poem'), 'unknown type')

    def test_missing_pdf(self):
        self.check(work(pdf='files/publications/nope.pdf'), 'pdf file')

    def test_unknown_role(self):
        self.check(work(people=[person('X', 'Y', 'boss')]), 'unknown role')

    def test_bad_slug(self):
        self.check(work(slug='Bad Slug'), 'bad slug')

    def test_duplicate_slug(self):
        with self.assertRaises(bp.BuildError):
            bp.validate([work(), work()], self.tmp)

    def test_date_end_needs_a_date_before_it(self):
        self.check(work(date='2026-05-16', date_end='2026-05-15'), 'date_end')
        self.check(work(date=None, date_end='2026-05-15'), 'date_end')

    def test_empty_section_is_rejected(self):
        self.check(work(toc=[{'section': ' '}]), 'section')

    def test_toc_page_must_be_a_number(self):
        self.check(work(toc=[{'title': 'X', 'page': '5'}]), 'toc entry')


class ContentTests(unittest.TestCase):
    """Настоящие данные сайта проходят проверку."""

    def test_repository_publications_are_valid(self):
        items = bp.load(ROOT)
        bp.validate(items, ROOT)
        self.assertGreaterEqual(len(items), 1)


if __name__ == '__main__':
    unittest.main()
