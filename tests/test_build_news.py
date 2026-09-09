import importlib.util
import json
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

    def test_backslashes_in_title_survive(self):
        out = bn.Shell.from_donor(DONOR).render(r'A \1 & B', 'D', 'i.jpg', '')
        self.assertIn(r'<title>A \1 &amp; B — NavDU</title>', out)

    def test_before_body_end(self):
        out = bn.Shell.from_donor(DONOR).render('T', 'D', 'i.jpg', '', before_body_end='<script>X</script>')
        self.assertIn('<script>X</script>\n</body>', out)

    def test_missing_marker(self):
        with self.assertRaisesRegex(bn.BuildError, 'sp-page-title'):
            bn.Shell.from_donor(DONOR.replace('id="sp-page-title"', 'id="x"'))

    def test_duplicate_marker(self):
        with self.assertRaisesRegex(bn.BuildError, 'FOOTER'):
            bn.Shell.from_donor(DONOR + '<!-- ====== FOOTER')


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


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        (self.root / 'content').mkdir()
        (self.root / 'images/nsu/news/a').mkdir(parents=True)
        (self.root / 'images/nsu/news/a/cover.jpg').write_bytes(b'x')
        (self.root / 'images/nsu/news/campus.jpg').write_bytes(b'x')
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


if __name__ == '__main__':
    unittest.main()
