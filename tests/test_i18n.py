"""Tests for the multilingual build (scripts/i18n.py, scripts/build_i18n.py).

The Uzbek pages in the repository root are the source of truth; ru/ and en/
are generated from them. Two properties matter and are checked here:

  * with an empty dictionary the rewriter reproduces the page byte for byte —
    the pages are hand-written markup, and the build must never
    reformat it;
  * a page that moved one level deep still resolves every asset, while links
    to sibling pages stay relative.
"""
import importlib.util
import pathlib
import shutil
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_i18n = load('build_i18n')
# build_i18n imports i18n itself; take that very instance, otherwise the tests
# would patch a second copy of the module and the build would not see it.
i18n = build_i18n.i18n

PAGE = '''<!doctype html>
<html lang="uz" dir="ltr">
<head>
\t<meta name="description" content="Universitet haqida">
\t<meta name="og:title" content="Universitet — NavDU">
\t<title>Universitet — NavDU</title>
\t<link href="assets/css/nsu.css?v=1" rel="stylesheet">
</head>
<body>
<div class="lang" id="lang">
          <button class="lang__btn" type="button" aria-haspopup="true" aria-expanded="false">
            <img class="lang__flag" src="assets/flag-uz.svg" alt="">
            <span class="lang__label">O‘zbekcha</span>
          </button>
          <ul class="lang__menu">
            <li><button type="button" class="is-active">O‘zbekcha</button></li>
          </ul>
        </div>
<a href="about.html">Universitet haqida</a>
<a href="https://qabul.nsu.uz">Qabul portali</a>
<a href="#top">Yuqoriga</a>
<img src="images/nsu/seal.png" alt="Universitet muhri">
<div style="background-image:url(images/nsu/hero.jpg)"></div>
<svg class="ico"><use href="#i-x"/></svg>
<select><option value="UZ">Uzbekistan</option></select>
<p>Bilim, ilm, ma’naviyat</p>
<script>var s = "Bilim, ilm, ma’naviyat";</script>
</body>
</html>
'''

TABLE = {
    'Universitet haqida': 'Об университете',
    'Universitet — NavDU': 'Университет — NavDU',
    'Universitet muhri': 'Печать «университета»',
    'Bilim, ilm, ma’naviyat': 'Знание, наука, духовность',
    'Uzbekistan': 'Узбекистан',
}


class RewriteTests(unittest.TestCase):
    def test_empty_table_reproduces_the_page(self):
        self.assertEqual(i18n.apply(PAGE, {}), PAGE)

    def test_every_repository_page_survives_a_round_trip(self):
        for page in sorted(ROOT.glob('*.html')):
            src = page.read_text(encoding='utf-8')
            self.assertEqual(i18n.apply(src, {}), src, page.name)

    def test_text_and_attributes_are_translated(self):
        out = i18n.apply(PAGE, TABLE)
        self.assertIn('<p>Знание, наука, духовность</p>', out)
        self.assertIn('<a href="about.html">Об университете</a>', out)
        self.assertIn('<title>Университет — NavDU</title>', out)
        self.assertIn('<meta name="og:title" content="Университет — NavDU">', out)

    def test_a_quote_in_an_attribute_becomes_an_entity(self):
        out = i18n.apply(PAGE, {'Universitet muhri': 'Печать "университета"'})
        self.assertIn('alt="Печать &quot;университета&quot;"', out)

    def test_script_and_select_are_left_alone(self):
        out = i18n.apply(PAGE, TABLE)
        self.assertIn('var s = "Bilim, ilm, ma’naviyat";', out)
        self.assertIn('<option value="UZ">Uzbekistan</option>', out)

    def test_numbers_and_contacts_are_not_collected(self):
        for text in ('|', '2026', '+998 (79) 223-77-89', 'info@nsu.uz', '  '):
            self.assertFalse(i18n.is_translatable(text), text)
        for text in ('Qabul', 'NavDU raqamlarda'):
            self.assertTrue(i18n.is_translatable(text), text)


class RelocateTests(unittest.TestCase):
    PAGES = {'about.html', 'index.html'}

    def relocate(self, url):
        return i18n.relocate(url, '../', self.PAGES)

    def test_assets_move_one_level_up(self):
        self.assertEqual(self.relocate('assets/css/nsu.css?v=1'), '../assets/css/nsu.css?v=1')
        self.assertEqual(self.relocate('images/nsu/seal.png'), '../images/nsu/seal.png')
        self.assertEqual(self.relocate('views/hit'), '../views/hit')

    def test_sibling_pages_stay_relative(self):
        self.assertEqual(self.relocate('about.html'), 'about.html')
        self.assertEqual(self.relocate('about.html#map'), 'about.html#map')

    def test_absolute_and_anchor_links_are_untouched(self):
        for url in ('https://qabul.nsu.uz', '//cdn/x.js', '/admin/', '#top',
                    'mailto:info@nsu.uz', 'tel:+998792237789', 'data:image/png;base64,AA'):
            self.assertEqual(self.relocate(url), url)

    def test_inline_style_urls_move_too(self):
        out = i18n.apply(PAGE, {}, depth=1, page_links=self.PAGES)
        self.assertIn('url(../images/nsu/hero.jpg)', out)
        self.assertIn('href="../assets/css/nsu.css?v=1"', out)
        self.assertIn('<a href="about.html">', out)
        self.assertIn('<use href="#i-x"/>', out)


class RenderTests(unittest.TestCase):
    def render(self, lang):
        return build_i18n.render(PAGE, lang, 'about.html', {'about.html'}, TABLE if lang == 'ru' else {})

    def test_html_lang_and_switcher_follow_the_language(self):
        out = self.render('ru')
        self.assertIn('<html lang="ru" dir="ltr">', out)
        self.assertIn('<span class="lang__label">Русский</span>', out)
        self.assertIn('<a class="is-active" href="about.html" hreflang="ru"', out)
        self.assertIn('href="../about.html" hreflang="uz"', out)
        self.assertIn('href="../en/about.html" hreflang="en"', out)
        self.assertIn('src="../assets/flag-ru.svg"', out)

    def test_uzbek_switcher_points_into_the_subfolders(self):
        out = self.render('uz')
        self.assertIn('<html lang="uz" dir="ltr">', out)
        self.assertIn('href="ru/about.html" hreflang="ru"', out)
        self.assertIn('href="en/about.html" hreflang="en"', out)
        self.assertIn('<a class="is-active" href="about.html" hreflang="uz"', out)

    def test_alternate_links_are_absolute_and_not_duplicated(self):
        out = self.render('ru')
        self.assertIn('<link rel="alternate" hreflang="ru" href="https://ndu.uz/ru/about.html">', out)
        self.assertIn('hreflang="x-default" href="https://ndu.uz/about.html">', out)
        self.assertEqual(out.count(build_i18n.HREFLANG_MARK), 1)
        # Rendering an already rendered page replaces the block instead of adding one.
        again = build_i18n.render(out, 'ru', 'about.html', {'about.html'}, TABLE)
        self.assertEqual(again.count(build_i18n.HREFLANG_MARK), 1)
        self.assertEqual(again, out)

    def test_a_page_without_a_switcher_is_an_error(self):
        with self.assertRaises(build_i18n.BuildError):
            build_i18n.render(PAGE.replace('<div class="lang" id="lang">', '<div>'),
                              'ru', 'about.html', set(), {})


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.orig_root = i18n.ROOT, i18n.I18N_DIR
        i18n.ROOT = self.root
        i18n.I18N_DIR = self.root / 'content' / 'i18n'
        (self.root / 'about.html').write_text(PAGE, encoding='utf-8')
        i18n.I18N_DIR.mkdir(parents=True)
        (i18n.I18N_DIR / 'ru.json').write_text('{"Universitet haqida": "Об университете"}',
                                               encoding='utf-8')

    def tearDown(self):
        i18n.ROOT, i18n.I18N_DIR = self.orig_root
        shutil.rmtree(self.root)

    def test_build_writes_both_languages_and_is_idempotent(self):
        first = build_i18n.build(quiet=True)
        self.assertEqual(first['ru'], 1)
        self.assertIn('Об университете', (self.root / 'ru/about.html').read_text(encoding='utf-8'))
        # Without a dictionary the English page keeps the Uzbek text.
        self.assertIn('Universitet haqida', (self.root / 'en/about.html').read_text(encoding='utf-8'))
        second = build_i18n.build(quiet=True)
        self.assertEqual(second, {'uz': 0, 'ru': 0, 'en': 0})

    def test_a_page_dropped_from_the_source_disappears_from_the_translations(self):
        build_i18n.build(quiet=True)
        (self.root / 'ru/gone.html').write_text('x', encoding='utf-8')
        build_i18n.build(quiet=True)
        self.assertFalse((self.root / 'ru/gone.html').exists())

    def test_generated_news_pages_are_left_to_build_news(self):
        build_i18n.build(quiet=True)
        (self.root / 'ru/news-x.html').write_text('x', encoding='utf-8')
        build_i18n.build(quiet=True)
        self.assertTrue((self.root / 'ru/news-x.html').exists())


if __name__ == '__main__':
    unittest.main()
