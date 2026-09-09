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
        counter.Handler.log_message = lambda *args: None   # keep the test output clean
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
        req.add_header('User-Agent', ua)
        if xff:
            req.add_header('X-Forwarded-For', xff)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read()
                return resp.status, dict(resp.headers), json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            with e:
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
        self.assertEqual(self.call('GET', '/count/Bad')[0], 400)
        self.assertEqual(self.call('GET', '/counts')[2]['read-me'], 1)
        status, headers, body = self.call('GET', '/health')
        self.assertEqual((status, body), (200, {'status': 'ok'}))

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

    def test_purge_drops_old_seen_rows(self):
        store = self.server.store
        store.hit('purge-me', 'visitor-a', '2000-01-01')
        self.assertEqual(store.count('purge-me'), 1)
        store.purge()
        # the old "seen" row is gone, so the same visitor counts again under that day
        self.assertEqual(store.hit('purge-me', 'visitor-a', '2000-01-01'), 2)


if __name__ == '__main__':
    unittest.main()
