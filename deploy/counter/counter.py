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


def valid_slug(slug):
    return isinstance(slug, str) and len(slug) <= SLUG_MAX and bool(SLUG_RE.match(slug))


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

    def close(self):
        self.db.close()


def visitor_id(ip, user_agent):
    return hashlib.sha256(f'{ip}|{user_agent}'.encode('utf-8', 'replace')).hexdigest()[:32]


class Handler(BaseHTTPRequestHandler):
    server_version = 'ndu-counter/1'
    protocol_version = 'HTTP/1.1'

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
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        store = self.server.store
        if self.path == '/health':
            return self.send_json(200, {'status': 'ok'})
        if self.path == '/counts':
            return self.send_json(200, store.counts())
        if self.path.startswith('/count/'):
            slug = self.path[len('/count/'):]
            if not valid_slug(slug):
                return self.send_json(400, {'error': 'bad slug'})
            return self.send_json(200, {'slug': slug, 'count': store.count(slug)})
        self.send_json(404, {'error': 'not found'})

    def do_POST(self):
        length = int(self.headers.get('Content-Length') or 0)
        if length > BODY_MAX:
            return self.send_json(413, {'error': 'body too large'})
        raw = self.rfile.read(length) if length else b''
        if self.path != '/hit':
            return self.send_json(405 if self.path in ('/counts', '/health') else 404,
                                  {'error': 'not found'})
        try:
            data = json.loads(raw or b'{}')
        except ValueError:
            return self.send_json(400, {'error': 'bad json'})
        slug = data.get('slug') if isinstance(data, dict) else None
        if not valid_slug(slug):
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


class CounterServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, db_path):
        super().__init__(address, Handler)
        self.store = Store(db_path)

    def server_close(self):
        super().server_close()
        self.store.close()


def make_server(host, port, db_path):
    return CounterServer((host, port), db_path)


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
