"""Tests for the news admin backend (deploy/api/api.py).

No network: GitHub is replaced by an in-memory fake that keeps the same
contract as the real client (head/read_news/list_dir/commit/latest_run). The
publish path is exercised against the real scripts/build_news.py on a minimal
site in a temporary directory, so a change that breaks instant publishing
fails here rather than on the server.
"""
import base64
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
spec = importlib.util.spec_from_file_location('api', ROOT / 'deploy' / 'api' / 'api.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)

PASSWORD = 'correct horse battery'
USER = 'admin'

PIXEL = base64.b64decode(
    b'/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////'
    b'////////////////////////////////////////////////////2wBDAf//////////'
    b'////////////////////////////////////////////////////////////////////'
    b'/////8AAEQgAAQABAwEiAAIRAQMRAf/EABUAAQEAAAAAAAAAAAAAAAAAAAAI/8QAFBAB'
    b'AAAAAAAAAAAAAAAAAAAAAP/EABQBAQAAAAAAAAAAAAAAAAAAAAD/xAAUEQEAAAAAAAAA'
    b'AAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=')
PIXEL_B64 = base64.b64encode(PIXEL).decode()

DONOR = '''<!DOCTYPE html><html><head>
\t<meta name="og:title" content="Bogʻlanish — NavDU">
\t<meta name="og:image" content="images/nsu/nsu-seal-navy.png">
\t<meta name="description" content="Biz bilan bogʻlanish.">
\t<title>Bogʻlanish — NavDU</title>
</head><body class="nsu-inner">
<a class="menu__link is-active" href="contact.html">Bogʻlanish</a>
<a class="menu__link" href="news.html">Yangiliklar</a>
<a class="mm__link" href="news.html">Yangiliklar</a>
\t\t\t\t<section id="sp-page-title" class="nsu-page-hero">OLD</section><section id="sp-main-body">OLD</section><!-- ====== FOOTER ====== -->
<footer>F</footer>
</body>
</html>
'''

INDEX = '<!DOCTYPE html><html><body><!-- news:carousel -->old<!-- /news:carousel --></body></html>\n'


def make_site(root):
    """A site skeleton just complete enough for scripts/build_news.py to run."""
    root.mkdir(parents=True, exist_ok=True)
    (root / 'contact.html').write_text(DONOR, encoding='utf-8')
    (root / 'index.html').write_text(INDEX, encoding='utf-8')
    images = root / 'images' / 'nsu' / 'news'
    images.mkdir(parents=True, exist_ok=True)
    (images / 'campus.jpg').write_bytes(PIXEL)
    return root


class FakeGitHub:
    """In-memory stand-in for api.GitHub with the same method contract."""

    def __init__(self, news=None):
        self.files = {}                       # repo path -> bytes
        self.news = news or {'posts': []}
        self.commits = []                     # (subject, [paths written], [paths deleted])
        self.sha = 'a' * 40
        self.fail_ref_once = False
        self.run = None

    def head(self):
        return self.sha, 't' * 40

    def read_news(self, commit_sha):
        return json.loads(json.dumps(self.news))

    def list_dir(self, path):
        prefix = path.rstrip('/') + '/'
        return sorted(p for p in self.files if p.startswith(prefix))

    def latest_run(self):
        return self.run

    def commit(self, message, mutate, files):
        for attempt in range(2):
            nxt = mutate(json.loads(json.dumps(self.news)))
            subject = message(nxt) if callable(message) else message
            if self.fail_ref_once and attempt == 0:
                self.fail_ref_once = False
                continue
            written, deleted = [], []
            for f in files:
                if f.get('delete'):
                    self.files.pop(f['path'], None)
                    deleted.append(f['path'])
                else:
                    self.files[f['path']] = base64.b64decode(f['base64'])
                    written.append(f['path'])
            self.news = nxt
            self.sha = f'{len(self.commits) + 1:040d}'
            self.commits.append((subject, written, deleted))
            return self.sha, nxt
        raise api.ApiError(409, 'branch moved')


class PasswordTests(unittest.TestCase):
    def test_roundtrip(self):
        encoded = api.hash_password(PASSWORD, n=2 ** 8)
        self.assertTrue(api.verify_password(PASSWORD, encoded))

    def test_wrong_password_rejected(self):
        encoded = api.hash_password(PASSWORD, n=2 ** 8)
        self.assertFalse(api.verify_password(PASSWORD + 'x', encoded))

    def test_salt_differs_every_time(self):
        self.assertNotEqual(api.hash_password(PASSWORD, n=2 ** 8),
                            api.hash_password(PASSWORD, n=2 ** 8))

    def test_garbage_hash_is_false_not_an_error(self):
        for bad in ('', 'plain', 'scrypt$x$y', 'bcrypt$1$1$1$aa$bb', 'scrypt$256$8$1$!!$!!'):
            self.assertFalse(api.verify_password(PASSWORD, bad), bad)


class RecordTests(unittest.TestCase):
    def payload(self, **over):
        base = {'title': 'Sarlavha', 'date': '2026-09-10', 'excerpt': 'Anons',
                'cover': 'images/nsu/news/test/20260910-000000-cover.jpg',
                'body': '<p>Matn</p>', 'gallery': []}
        base.update(over)
        return base

    def test_clean_post_keeps_fields(self):
        record = api.clean_post('test', self.payload(), None)
        self.assertEqual(record['slug'], 'test')
        self.assertEqual(record['title'], 'Sarlavha')
        self.assertEqual(record['date'], '2026-09-10')
        self.assertTrue(record['updated'].endswith('Z'))

    def test_empty_date_becomes_null(self):
        self.assertIsNone(api.clean_post('test', self.payload(date=''), None)['date'])

    def test_bad_slug_rejected(self):
        for slug in ('Test', 'te st', 'te_st', '-test', 'a' * 81):
            with self.assertRaises(api.ApiError, msg=slug):
                api.clean_post(slug, self.payload(), None)

    def test_missing_title_rejected(self):
        with self.assertRaises(api.ApiError):
            api.clean_post('test', self.payload(title='   '), None)

    def test_bad_date_rejected(self):
        with self.assertRaises(api.ApiError):
            api.clean_post('test', self.payload(date='10.09.2026'), None)

    def test_cover_falls_back_to_the_existing_one(self):
        existing = {'cover': 'images/nsu/news/test/old-cover.jpg'}
        record = api.clean_post('test', self.payload(cover=None), existing)
        self.assertEqual(record['cover'], 'images/nsu/news/test/old-cover.jpg')

    def test_missing_cover_rejected_for_a_new_post(self):
        with self.assertRaises(api.ApiError):
            api.clean_post('test', self.payload(cover=None), None)


class FileTests(unittest.TestCase):
    def test_upload_inside_the_post_folder_is_accepted(self):
        files = api.clean_files('test', [
            {'path': 'images/nsu/news/test/20260910-000000-cover.jpg', 'base64': PIXEL_B64}])
        self.assertEqual(len(files), 1)

    def test_paths_outside_the_post_folder_are_rejected(self):
        for path in ('images/nsu/news/other/x.jpg', 'index.html', 'images/nsu/news/test/../../x.jpg',
                     '/etc/passwd', 'images/nsu/news/test/sub/dir/x.jpg'):
            with self.assertRaises(api.ApiError, msg=path):
                api.clean_files('test', [{'path': path, 'base64': PIXEL_B64}])

    def test_broken_base64_is_rejected(self):
        with self.assertRaises(api.ApiError):
            api.clean_files('test', [{'path': 'images/nsu/news/test/x.jpg', 'base64': 'not base64!'}])

    def test_client_cannot_ask_for_a_deletion(self):
        # A delete entry has no base64, so it is refused like any broken upload:
        # deletions are the server's decision alone.
        with self.assertRaises(api.ApiError):
            api.clean_files('test', [{'path': 'images/nsu/news/test/x.jpg', 'delete': True}])

    def test_referenced_images_covers_body_and_gallery(self):
        prefix = 'images/nsu/news/test/'
        post = {'cover': prefix + 'cover.jpg',
                'gallery': [prefix + 'g01.jpg', 'images/nsu/other.jpg'],
                'body': f'<p>a</p><img src="{prefix}01.jpg"><img src="https://x/y.jpg">'}
        self.assertEqual(api.referenced_images(post, prefix),
                         {prefix + 'cover.jpg', prefix + 'g01.jpg', prefix + '01.jpg'})

    def test_stale_images_keeps_referenced_and_uploading(self):
        prefix = 'images/nsu/news/test/'
        record = {'cover': prefix + 'new-cover.jpg', 'gallery': [], 'body': ''}
        in_repo = [prefix + 'old-cover.jpg', prefix + 'old-01.jpg', prefix + 'new-cover.jpg']
        self.assertEqual(api.stale_images(record, [prefix + 'new-cover.jpg'], in_repo, prefix),
                         [prefix + 'old-01.jpg', prefix + 'old-cover.jpg'])


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.site = make_site(self.tmp / 'site')
        self.publisher = api.Publisher(self.site, str(ROOT / 'scripts' / 'build_news.py'))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_publish_writes_the_post_page(self):
        cover = 'images/nsu/news/hello/cover.jpg'
        self.publisher.write_images([{'path': cover, 'base64': PIXEL_B64}])
        news = {'posts': [{'slug': 'hello', 'title': 'Salom', 'date': '2026-09-10',
                           'excerpt': 'A', 'cover': cover, 'body': '<p>B</p>', 'gallery': [],
                           'updated': '2026-09-10T00:00:00Z'}]}
        self.assertIsNone(self.publisher.publish(news))
        page = self.site / 'news-hello.html'
        self.assertTrue(page.is_file())
        self.assertIn('Salom', page.read_text(encoding='utf-8'))
        self.assertIn('news-hello.html', (self.site / 'index.html').read_text(encoding='utf-8'))
        self.assertIn('Salom', (self.site / 'news.html').read_text(encoding='utf-8'))

    def test_publish_removes_the_page_of_a_deleted_post(self):
        cover = 'images/nsu/news/hello/cover.jpg'
        self.publisher.write_images([{'path': cover, 'base64': PIXEL_B64}])
        post = {'slug': 'hello', 'title': 'Salom', 'date': '2026-09-10', 'excerpt': '',
                'cover': cover, 'body': '', 'gallery': [], 'updated': '2026-09-10T00:00:00Z'}
        self.publisher.publish({'posts': [post]})
        self.assertTrue((self.site / 'news-hello.html').is_file())
        self.publisher.remove_dir('images/nsu/news/hello')
        self.publisher.publish({'posts': []})
        self.assertFalse((self.site / 'news-hello.html').is_file())

    def test_publish_reports_instead_of_raising(self):
        # A cover that does not exist makes build_news fail; the caller must be
        # told, not crashed, because the commit already went through.
        news = {'posts': [{'slug': 'hello', 'title': 'Salom', 'date': None, 'excerpt': '',
                           'cover': 'images/nsu/news/hello/missing.jpg', 'body': '',
                           'gallery': [], 'updated': '2026-09-10T00:00:00Z'}]}
        self.assertIsNotNone(self.publisher.publish(news))

    def test_writes_stay_inside_the_document_root(self):
        with self.assertRaises(api.ApiError):
            self.publisher.write_images([{'path': '../escape.jpg', 'base64': PIXEL_B64}])
        self.assertFalse((self.tmp / 'escape.jpg').exists())


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp())
        cls.site = make_site(cls.tmp / 'site')
        api.Handler.log_message = lambda *args: None       # keep the test output clean
        api.log = lambda *args: None
        cls.gh = FakeGitHub()
        store = api.Store(str(cls.tmp / 'api.db'))
        publisher = api.Publisher(cls.site, str(ROOT / 'scripts' / 'build_news.py'))
        api.COOKIE_SECURE = False
        cls.server = api.Server(('127.0.0.1', 0), store, cls.gh, publisher,
                                USER, api.hash_password(PASSWORD, n=2 ** 8))
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server.store.close()
        shutil.rmtree(cls.tmp)

    def setUp(self):
        self.gh.files = {}
        self.gh.news = {'posts': []}
        self.gh.commits = []
        self.cookie = None
        self.server.store.clear_failures('10.0.0.1')

    def call(self, method, path, body=None, *, csrf=True, cookie=True, ip='10.0.0.1'):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header('Content-Type', 'application/json')
        req.add_header('X-Forwarded-For', ip)
        if csrf:
            req.add_header('X-Requested-With', 'ndu-admin')
        if cookie and self.cookie:
            req.add_header('Cookie', self.cookie)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
                set_cookie = resp.headers.get('Set-Cookie')
                if set_cookie:
                    self.cookie = set_cookie.split(';')[0]
                return resp.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raw = e.read()
            return e.code, json.loads(raw) if raw else None

    def login(self):
        status, _ = self.call('POST', '/login', {'username': USER, 'password': PASSWORD})
        self.assertEqual(status, 200)

    def post_body(self, **over):
        base = {'title': 'Salom', 'date': '2026-09-10', 'excerpt': 'Anons',
                'cover': 'images/nsu/news/hello/20260910-000000-cover.jpg',
                'body': '<p>Matn</p>', 'gallery': [],
                'files': [{'path': 'images/nsu/news/hello/20260910-000000-cover.jpg',
                           'base64': PIXEL_B64}]}
        base.update(over)
        return base

    # ------------------------------------------------------------ auth

    def test_health_needs_no_session(self):
        self.assertEqual(self.call('GET', '/health')[0], 200)

    def test_login_then_session(self):
        self.login()
        status, data = self.call('GET', '/session')
        self.assertEqual((status, data), (200, {'user': USER}))

    def test_cookie_is_httponly_and_samesite(self):
        status, _ = self.call('POST', '/login', {'username': USER, 'password': PASSWORD})
        self.assertEqual(status, 200)
        # The header was captured by call(); re-read it from a fresh request.
        req = urllib.request.Request(self.base + '/login', method='POST',
                                     data=json.dumps({'username': USER, 'password': PASSWORD}).encode())
        req.add_header('X-Requested-With', 'ndu-admin')
        req.add_header('X-Forwarded-For', '10.0.0.1')
        with urllib.request.urlopen(req, timeout=15) as resp:
            header = resp.headers.get('Set-Cookie')
        self.assertIn('HttpOnly', header)
        self.assertIn('SameSite=Strict', header)

    def test_wrong_password_rejected(self):
        status, data = self.call('POST', '/login', {'username': USER, 'password': 'nope'})
        self.assertEqual(status, 401)
        self.assertIn('Неверный', data['error'])

    def test_wrong_user_rejected(self):
        self.assertEqual(self.call('POST', '/login', {'username': 'root', 'password': PASSWORD})[0], 401)

    def test_endpoints_need_a_session(self):
        for method, path in (('GET', '/news'), ('GET', '/deploy'), ('GET', '/session'),
                             ('PUT', '/posts/hello'), ('DELETE', '/posts/hello')):
            status, _ = self.call(method, path, {} if method in ('PUT',) else None)
            self.assertEqual(status, 401, f'{method} {path}')

    def test_logout_drops_the_session(self):
        self.login()
        self.assertEqual(self.call('POST', '/logout')[0], 200)
        self.assertEqual(self.call('GET', '/session', cookie=False)[0], 401)

    def test_mutations_need_the_csrf_header(self):
        self.login()
        self.assertEqual(self.call('PUT', '/posts/hello', self.post_body(), csrf=False)[0], 403)
        self.assertEqual(self.call('DELETE', '/posts/hello', csrf=False)[0], 403)
        self.assertEqual(self.call('POST', '/login', {'username': USER, 'password': PASSWORD},
                                   csrf=False)[0], 403)

    def test_login_throttled_after_repeated_failures(self):
        for _ in range(api.LOGIN_MAX_FAILURES):
            self.call('POST', '/login', {'username': USER, 'password': 'nope'}, ip='10.9.9.9')
        status, data = self.call('POST', '/login', {'username': USER, 'password': PASSWORD},
                                 ip='10.9.9.9')
        self.assertEqual(status, 429)
        self.assertIn('попыток', data['error'])
        self.server.store.clear_failures('10.9.9.9')

    def test_successful_login_clears_the_throttle(self):
        for _ in range(3):
            self.call('POST', '/login', {'username': USER, 'password': 'nope'}, ip='10.8.8.8')
        self.assertEqual(self.call('POST', '/login', {'username': USER, 'password': PASSWORD},
                                   ip='10.8.8.8')[0], 200)
        self.assertFalse(self.server.store.login_blocked('10.8.8.8'))

    # ------------------------------------------------------------ posts

    def test_create_post_commits_and_publishes(self):
        self.login()
        status, data = self.call('PUT', '/posts/hello', self.post_body())
        self.assertEqual(status, 200, data)
        self.assertIsNone(data['warning'])
        self.assertEqual([p['slug'] for p in data['news']['posts']], ['hello'])
        subject, written, _ = self.gh.commits[-1]
        self.assertEqual(subject, 'news: add «Salom»')
        self.assertEqual(written, ['images/nsu/news/hello/20260910-000000-cover.jpg'])
        page = self.site / 'news-hello.html'
        self.assertTrue(page.is_file())
        self.assertIn('Salom', page.read_text(encoding='utf-8'))
        self.assertTrue((self.site / 'images' / 'nsu' / 'news' / 'hello'
                         / '20260910-000000-cover.jpg').is_file())

    def test_update_post_says_update_and_drops_the_old_cover(self):
        self.login()
        self.call('PUT', '/posts/hello', self.post_body())
        new_cover = 'images/nsu/news/hello/20260911-000000-cover.jpg'
        status, data = self.call('PUT', '/posts/hello', self.post_body(
            title='Yangilandi', cover=new_cover,
            files=[{'path': new_cover, 'base64': PIXEL_B64}]))
        self.assertEqual(status, 200, data)
        subject, written, deleted = self.gh.commits[-1]
        self.assertEqual(subject, 'news: update «Yangilandi»')
        self.assertEqual(written, [new_cover])
        self.assertEqual(deleted, ['images/nsu/news/hello/20260910-000000-cover.jpg'])
        self.assertFalse((self.site / 'images/nsu/news/hello/20260910-000000-cover.jpg').exists())
        self.assertIn('Yangilandi', (self.site / 'news-hello.html').read_text(encoding='utf-8'))

    def test_update_keeps_images_the_body_still_uses(self):
        self.login()
        inline = 'images/nsu/news/hello/20260910-000000-01.jpg'
        self.call('PUT', '/posts/hello', self.post_body(
            body=f'<p>A</p><img src="{inline}">',
            files=[{'path': 'images/nsu/news/hello/20260910-000000-cover.jpg', 'base64': PIXEL_B64},
                   {'path': inline, 'base64': PIXEL_B64}]))
        status, _ = self.call('PUT', '/posts/hello', self.post_body(
            body=f'<p>B</p><img src="{inline}">', files=[]))
        self.assertEqual(status, 200)
        _, _, deleted = self.gh.commits[-1]
        self.assertEqual(deleted, [])

    def test_delete_post_removes_page_and_images(self):
        self.login()
        self.call('PUT', '/posts/hello', self.post_body())
        status, data = self.call('DELETE', '/posts/hello')
        self.assertEqual(status, 200, data)
        self.assertEqual(data['news']['posts'], [])
        subject, _, deleted = self.gh.commits[-1]
        self.assertEqual(subject, 'news: delete «Salom»')
        self.assertEqual(deleted, ['images/nsu/news/hello/20260910-000000-cover.jpg'])
        self.assertFalse((self.site / 'news-hello.html').exists())
        self.assertFalse((self.site / 'images' / 'nsu' / 'news' / 'hello').exists())

    def test_delete_unknown_post_is_404(self):
        self.login()
        self.assertEqual(self.call('DELETE', '/posts/nothing')[0], 404)

    def test_invalid_record_is_rejected_before_any_commit(self):
        self.login()
        status, data = self.call('PUT', '/posts/hello', self.post_body(title=''))
        self.assertEqual(status, 400)
        self.assertIn('заголовок', data['error'])
        self.assertEqual(self.gh.commits, [])

    def test_image_path_outside_the_post_folder_is_rejected(self):
        self.login()
        status, _ = self.call('PUT', '/posts/hello', self.post_body(
            files=[{'path': 'index.html', 'base64': PIXEL_B64}]))
        self.assertEqual(status, 400)
        self.assertEqual(self.gh.commits, [])

    def test_news_returns_what_the_repository_holds(self):
        self.login()
        self.call('PUT', '/posts/hello', self.post_body())
        status, data = self.call('GET', '/news')
        self.assertEqual(status, 200)
        self.assertEqual([p['slug'] for p in data['posts']], ['hello'])

    def test_deploy_status_is_passed_through(self):
        self.login()
        self.gh.run = {'status': 'completed', 'conclusion': 'success',
                       'updated_at': '2026-09-10T12:00:00Z', 'html_url': 'https://x',
                       'secret': 'must not leak'}
        status, data = self.call('GET', '/deploy')
        self.assertEqual(status, 200)
        self.assertEqual(data['run']['conclusion'], 'success')
        self.assertNotIn('secret', data['run'])

    def test_unknown_route_is_404(self):
        self.login()
        self.assertEqual(self.call('GET', '/nope')[0], 404)

    def test_health_reports_configured(self):
        status, data = self.call('GET', '/health')
        self.assertEqual((status, data), (200, {'status': 'ok', 'configured': True}))


class UnconfiguredTests(unittest.TestCase):
    """A server without api.env must stay up and say so, not crash-loop."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp())
        api.Handler.log_message = lambda *args: None
        store = api.Store(str(cls.tmp / 'api.db'))
        publisher = api.Publisher(make_site(cls.tmp / 'site'), str(ROOT / 'scripts' / 'build_news.py'))
        cls.server = api.Server(('127.0.0.1', 0), store, FakeGitHub(), publisher, '', '',
                                configured=False)
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server.store.close()
        shutil.rmtree(cls.tmp)

    def get(self, path):
        req = urllib.request.Request(self.base + path)
        req.add_header('X-Requested-With', 'ndu-admin')
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_health_still_answers(self):
        status, data = self.get('/health')
        self.assertEqual(status, 200)
        self.assertFalse(data['configured'])

    def test_everything_else_says_not_configured(self):
        status, data = self.get('/session')
        self.assertEqual(status, 503)
        self.assertIn('не настроена', data['error'])


if __name__ == '__main__':
    unittest.main()
