#!/usr/bin/env python3
"""Backend of the NavDU news admin: login by password, commits to git, instant publish.

Why this exists: the first version of the admin sent a GitHub fine-grained token
from the browser straight to api.github.com. That works, but it makes every
editor create and carry a GitHub token, and it makes the site wait for CI before
a post appears. This service replaces that with a normal login, keeps the token
on the server, and rebuilds the news pages in the document root right after the
commit, so a post is live in seconds.

Git stays the source of truth. Every action is still exactly one commit in
BekkiBay/ndu; the local rebuild only mirrors what was just committed, and the
regular CI deploy later writes the same bytes. If the local rebuild fails, the
post is still committed and the CI deploy publishes it.

Endpoints (all under /api/ via nginx, see deploy/nginx-site.conf):

    POST   /login            {username, password} -> session cookie
    POST   /logout           drops the session
    GET    /session          {user} for a valid session, 401 otherwise
    GET    /news             {posts: [...]} as committed in the repository
    PUT    /posts/<slug>     create or update a post, then publish
    DELETE /posts/<slug>     delete a post and its images, then publish
    GET    /deploy           status of the latest CI run
    GET    /health           liveness, no session needed

Configuration comes from the environment (deploy/api.env on the server, see
deploy/README.md); nothing secret lives in this repository.

    ADMIN_USER              login name
    ADMIN_PASSWORD_HASH     from `python3 api.py hash-password`
    GITHUB_TOKEN            fine-grained token, Contents RW + Actions Read
    GITHUB_REPO             owner/name, default BekkiBay/ndu
    GITHUB_BRANCH           default main
    SITE_ROOT               document root to publish into, default /site
    BUILD_SCRIPT            copy of scripts/build_news.py, default /app/build_news.py
    API_DB                  session database, default /data/api.db
    COOKIE_SECURE           0 to allow plain http (local testing only)

Run `python3 api.py hash-password` to turn a password into ADMIN_PASSWORD_HASH.
"""
import base64
import binascii
import getpass
import hashlib
import hmac
import http.server
import importlib.util
import json
import os
import pathlib
import re
import secrets
import shutil
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request

PORT = int(os.environ.get('API_PORT', '8080'))
DB_PATH = os.environ.get('API_DB', '/data/api.db')
SITE_ROOT = pathlib.Path(os.environ.get('SITE_ROOT', '/site'))
BUILD_SCRIPT = os.environ.get('BUILD_SCRIPT', '/app/build_news.py')
REPO = os.environ.get('GITHUB_REPO', 'BekkiBay/ndu')
BRANCH = os.environ.get('GITHUB_BRANCH', 'main')
NEWS_PATH = 'content/news.json'
IMAGES_DIR = 'images/nsu/news/'
COOKIE = 'ndu_session'
COOKIE_SECURE = os.environ.get('COOKIE_SECURE', '1') != '0'

# A cover plus a gallery of full-size photos, base64-encoded, has to fit in one
# request; the browser already shrinks every image to 1600px JPEG.
MAX_BODY = 64 * 1024 * 1024
SESSION_IDLE = 30 * 24 * 3600
SESSION_MAX_AGE = 90 * 24 * 3600
# Failed logins per IP before the login endpoint starts refusing.
LOGIN_MAX_FAILURES = 10
LOGIN_WINDOW = 15 * 60

SLUG_RE = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
SLUG_MAX = 80
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
# Paths this service is allowed to write: only images of the post being saved.
SAFE_PATH_RE = re.compile(r'^images/nsu/news/[a-z0-9-]+/[A-Za-z0-9._-]+$')


class ApiError(Exception):
    """An error meant for the browser: status code plus a message in Russian."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


# --------------------------------------------------------------------------- passwords

def hash_password(password, *, n=2 ** 14, r=8, p=1):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=n, r=r, p=p, dklen=32)
    return 'scrypt${}${}${}${}${}'.format(
        n, r, p, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def verify_password(password, encoded):
    """Constant-time check of a password against a stored scrypt hash."""
    try:
        scheme, n, r, p, salt_b64, digest_b64 = encoded.split('$')
        if scheme != 'scrypt':
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except (ValueError, binascii.Error):
        return False
    if not salt or not expected:
        return False
    actual = hashlib.scrypt(password.encode('utf-8'), salt=salt,
                            n=int(n), r=int(r), p=int(p), dklen=len(expected))
    return hmac.compare_digest(actual, expected)


# --------------------------------------------------------------------------- storage

class Store:
    """Sessions and login throttling. One connection guarded by a lock, like the counter."""

    def __init__(self, path):
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS sessions (
                token     TEXT PRIMARY KEY,
                user      TEXT NOT NULL,
                created   INTEGER NOT NULL,
                last_seen INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS login_failures (
                ip TEXT NOT NULL,
                ts INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS login_failures_ip ON login_failures (ip, ts);
        ''')
        self.db.commit()

    def create_session(self, user):
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with self.lock:
            self.db.execute('INSERT INTO sessions (token, user, created, last_seen) VALUES (?,?,?,?)',
                            (token, user, now, now))
            self.db.commit()
        return token

    def touch_session(self, token):
        """Returns the user of a live session and extends it, or None."""
        if not token:
            return None
        now = int(time.time())
        with self.lock:
            row = self.db.execute('SELECT user, created, last_seen FROM sessions WHERE token = ?',
                                  (token,)).fetchone()
            if row is None:
                return None
            user, created, last_seen = row
            if now - last_seen > SESSION_IDLE or now - created > SESSION_MAX_AGE:
                self.db.execute('DELETE FROM sessions WHERE token = ?', (token,))
                self.db.commit()
                return None
            # One write per minute at most: every request would be pointless churn.
            if now - last_seen > 60:
                self.db.execute('UPDATE sessions SET last_seen = ? WHERE token = ?', (now, token))
                self.db.commit()
            return user

    def drop_session(self, token):
        if not token:
            return
        with self.lock:
            self.db.execute('DELETE FROM sessions WHERE token = ?', (token,))
            self.db.commit()

    def login_blocked(self, ip):
        cutoff = int(time.time()) - LOGIN_WINDOW
        with self.lock:
            self.db.execute('DELETE FROM login_failures WHERE ts < ?', (cutoff,))
            self.db.commit()
            (count,) = self.db.execute('SELECT COUNT(*) FROM login_failures WHERE ip = ? AND ts >= ?',
                                       (ip, cutoff)).fetchone()
        return count >= LOGIN_MAX_FAILURES

    def record_failure(self, ip):
        with self.lock:
            self.db.execute('INSERT INTO login_failures (ip, ts) VALUES (?,?)', (ip, int(time.time())))
            self.db.commit()

    def clear_failures(self, ip):
        with self.lock:
            self.db.execute('DELETE FROM login_failures WHERE ip = ?', (ip,))
            self.db.commit()

    def close(self):
        with self.lock:
            self.db.close()


# --------------------------------------------------------------------------- GitHub

class GitHub:
    """The parts of the Git Data API the admin needs; one commit per action.

    A port of what admin/github.js used to do in the browser, so the commit
    shape (blobs -> tree -> commit -> ref, one retry when the branch moved) is
    unchanged.
    """

    API = 'https://api.github.com'

    def __init__(self, token, repo=REPO, branch=BRANCH, timeout=60):
        self.token = token
        self.repo = repo
        self.branch = branch
        self.timeout = timeout

    def api(self, method, path, body=None):
        data = json.dumps(body).encode('utf-8') if body is not None else None
        req = urllib.request.Request(self.API + path, data=data, method=method)
        req.add_header('Authorization', f'Bearer {self.token}')
        req.add_header('Accept', 'application/vnd.github+json')
        req.add_header('X-GitHub-Api-Version', '2022-11-28')
        req.add_header('User-Agent', 'ndu-admin')
        if data is not None:
            req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                message = json.loads(raw).get('message') or f'GitHub {e.code}'
            except (ValueError, AttributeError):
                message = f'GitHub {e.code}'
            raise ApiError(e.code, message) from None
        except urllib.error.URLError as e:
            raise ApiError(502, f'GitHub недоступен: {e.reason}') from None

    def head(self):
        ref = self.api('GET', f'/repos/{self.repo}/git/ref/heads/{self.branch}')
        commit = self.api('GET', f'/repos/{self.repo}/git/commits/{ref["object"]["sha"]}')
        return ref['object']['sha'], commit['tree']['sha']

    def read_news(self, commit_sha):
        file = self.api('GET', f'/repos/{self.repo}/contents/{NEWS_PATH}?ref={commit_sha}')
        raw = base64.b64decode(file['content'])
        return json.loads(raw.decode('utf-8'))

    def list_dir(self, path):
        try:
            items = self.api('GET', f'/repos/{self.repo}/contents/{path}?ref={self.branch}')
        except ApiError as e:
            if e.status == 404:
                return []
            raise
        if not isinstance(items, list):
            return []
        return [i['path'] for i in items if i['type'] == 'file']

    def commit(self, message, mutate, files):
        """mutate(news) -> next news; files: [{path, base64}] or [{path, delete: True}].

        `message` may be a callable taking the mutated news, for a commit
        subject that depends on what the mutation turned out to do.

        Returns (commit_sha, next_news). Retries once when the branch moved
        under us, exactly like the browser client did.
        """
        for attempt in range(2):
            commit_sha, tree_sha = self.head()
            news = self.read_news(commit_sha)
            nxt = mutate(json.loads(json.dumps(news)))
            subject = message(nxt) if callable(message) else message
            tree = [{
                'path': NEWS_PATH, 'mode': '100644', 'type': 'blob',
                'content': json.dumps(nxt, ensure_ascii=False, indent=2) + '\n',
            }]
            for f in files:
                if f.get('delete'):
                    tree.append({'path': f['path'], 'mode': '100644', 'type': 'blob', 'sha': None})
                    continue
                blob = self.api('POST', f'/repos/{self.repo}/git/blobs',
                                {'content': f['base64'], 'encoding': 'base64'})
                tree.append({'path': f['path'], 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
            new_tree = self.api('POST', f'/repos/{self.repo}/git/trees',
                                {'base_tree': tree_sha, 'tree': tree})
            new_commit = self.api('POST', f'/repos/{self.repo}/git/commits',
                                  {'message': subject, 'tree': new_tree['sha'], 'parents': [commit_sha]})
            try:
                self.api('PATCH', f'/repos/{self.repo}/git/refs/heads/{self.branch}',
                         {'sha': new_commit['sha'], 'force': False})
                return new_commit['sha'], nxt
            except ApiError as e:
                if attempt == 0 and e.status in (409, 422):
                    continue
                raise
        raise ApiError(409, 'Ветка изменилась во время сохранения, попробуйте ещё раз')

    def latest_run(self):
        data = self.api('GET', f'/repos/{self.repo}/actions/runs?branch={self.branch}&per_page=1')
        runs = (data or {}).get('workflow_runs') or []
        return runs[0] if runs else None


# --------------------------------------------------------------------------- publishing

def load_builder(path):
    """Imports scripts/build_news.py from an arbitrary location."""
    spec = importlib.util.spec_from_file_location('build_news', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_site_path(root, rel):
    """Resolves a repository-relative path inside root, refusing anything outside it."""
    target = (root / rel).resolve()
    root = root.resolve()
    if target != root and root not in target.parents:
        raise ApiError(400, f'Недопустимый путь: {rel}')
    return target


class Publisher:
    """Mirrors a commit into the document root so the site updates in seconds."""

    def __init__(self, root=SITE_ROOT, build_script=BUILD_SCRIPT):
        self.root = pathlib.Path(root)
        self.build_script = build_script
        self.lock = threading.Lock()

    def write_images(self, files):
        for f in files:
            if f.get('delete'):
                continue
            target = safe_site_path(self.root, f['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(f['base64']))

    def remove(self, paths):
        for rel in paths:
            target = safe_site_path(self.root, rel)
            if target.is_file():
                target.unlink()

    def remove_dir(self, rel):
        target = safe_site_path(self.root, rel)
        if target.is_dir():
            shutil.rmtree(target)

    def publish(self, news):
        """Writes news.json into the document root and regenerates the pages there.

        Returns None on success or a human-readable reason why the site could
        not be rebuilt locally; the commit itself has already happened either
        way, so the caller reports the post as published and mentions the CI
        deploy as the fallback.
        """
        with self.lock:
            try:
                content = self.root / 'content'
                content.mkdir(parents=True, exist_ok=True)
                (content / 'news.json').write_text(
                    json.dumps(news, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                builder = load_builder(self.build_script)
                builder.build(self.root)
                return None
            except Exception as e:                       # noqa: BLE001 - reported, never fatal
                log(f'publish failed: {type(e).__name__}: {e}')
                return f'{type(e).__name__}: {e}'


# --------------------------------------------------------------------------- posts

def clean_post(slug, data, existing):
    """Validates the record the browser sent and returns what goes into news.json."""
    if not SLUG_RE.match(slug) or len(slug) > SLUG_MAX:
        raise ApiError(400, 'Slug: только латинские буквы, цифры и дефисы, до 80 символов.')
    title = (data.get('title') or '').strip()
    if not title:
        raise ApiError(400, 'Введите заголовок.')
    date = data.get('date') or None
    if date is not None and not DATE_RE.match(date):
        raise ApiError(400, 'Дата в формате ГГГГ-ММ-ДД.')
    cover = data.get('cover') or (existing or {}).get('cover')
    if not cover:
        raise ApiError(400, 'Выберите обложку.')
    gallery = data.get('gallery') or []
    if not isinstance(gallery, list) or any(not isinstance(p, str) for p in gallery):
        raise ApiError(400, 'Галерея повреждена.')
    return {
        'slug': slug,
        'title': title,
        'date': date,
        'excerpt': (data.get('excerpt') or '').strip(),
        'cover': cover,
        'body': data.get('body') or '',
        'gallery': gallery,
        'updated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }


def clean_files(slug, files):
    """Uploads the browser sent: only images inside the post's own folder.

    Deletions are never taken from the browser; the server works out which old
    images a post no longer references (see stale_images).
    """
    out = []
    prefix = f'{IMAGES_DIR}{slug}/'
    for f in files or []:
        path = f.get('path') or ''
        if not path.startswith(prefix) or not SAFE_PATH_RE.match(path) or '..' in path:
            raise ApiError(400, f'Недопустимый путь картинки: {path}')
        content = f.get('base64') or ''
        try:
            raw = base64.b64decode(content, validate=True)
        except (binascii.Error, ValueError):
            raise ApiError(400, f'Картинка повреждена: {path}') from None
        if not raw:
            raise ApiError(400, f'Пустая картинка: {path}')
        out.append({'path': path, 'base64': content})
    return out


SRC_RE = re.compile(r'src="([^"]+)"')


def referenced_images(post, prefix):
    """Every image of a post that lives in the post's own folder."""
    out = set()
    if not post:
        return out
    cover = post.get('cover') or ''
    if cover.startswith(prefix):
        out.add(cover)
    for path in post.get('gallery') or []:
        if path.startswith(prefix):
            out.add(path)
    for src in SRC_RE.findall(post.get('body') or ''):
        if src.startswith(prefix):
            out.add(src)
    return out


def stale_images(record, uploading, in_repo, prefix):
    """Images of the post still in the repository that the new record drops."""
    keep = referenced_images(record, prefix) | set(uploading)
    return sorted(p for p in in_repo if p not in keep)


# --------------------------------------------------------------------------- HTTP

def log(message):
    sys.stdout.write(f'{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} {message}\n')
    sys.stdout.flush()


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'ndu-api'
    protocol_version = 'HTTP/1.1'

    # -------------------------------------------------------------- plumbing

    @property
    def store(self):
        return self.server.store

    @property
    def github(self):
        return self.server.github

    @property
    def publisher(self):
        return self.server.publisher

    def client_ip(self):
        forwarded = self.headers.get('X-Forwarded-For', '')
        return forwarded.split(',')[0].strip() or self.client_address[0]

    def cookie_token(self):
        for part in (self.headers.get('Cookie') or '').split(';'):
            name, _, value = part.strip().partition('=')
            if name == COOKIE:
                return value
        return None

    def send_json(self, status, payload, cookie=None):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            length = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            raise ApiError(400, 'Неверный запрос.') from None
        if length <= 0:
            raise ApiError(400, 'Пустой запрос.')
        if length > MAX_BODY:
            raise ApiError(413, 'Слишком большой запрос: уменьшите количество или размер фотографий.')
        try:
            return json.loads(self.rfile.read(length).decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, 'Неверный формат запроса.') from None

    def require_session(self):
        user = self.store.touch_session(self.cookie_token())
        if not user:
            raise ApiError(401, 'Войдите заново.')
        return user

    def require_same_origin(self):
        """A cross-site form cannot set this header without a CORS preflight.

        Belt and braces next to SameSite=Strict on the cookie: both have to be
        bypassed for a CSRF to reach a mutating endpoint.
        """
        if self.headers.get('X-Requested-With') != 'ndu-admin':
            raise ApiError(403, 'Запрос отклонён.')

    def session_cookie(self, token, max_age=SESSION_MAX_AGE):
        parts = [f'{COOKIE}={token}', 'Path=/', 'HttpOnly', 'SameSite=Strict', f'Max-Age={max_age}']
        if COOKIE_SECURE:
            parts.append('Secure')
        return '; '.join(parts)

    # -------------------------------------------------------------- routing

    def do_GET(self):
        self.route('GET')

    def do_POST(self):
        self.route('POST')

    def do_PUT(self):
        self.route('PUT')

    def do_DELETE(self):
        self.route('DELETE')

    def route(self, method):
        path = self.path.split('?', 1)[0].rstrip('/') or '/'
        try:
            if method == 'GET' and path in ('/health', '/'):
                # Liveness only: the process is up. `configured` says whether
                # the credentials are in place, so a server waiting for its
                # api.env does not turn the whole deploy red.
                return self.send_json(200, {'status': 'ok', 'configured': self.server.configured})
            if not self.server.configured:
                raise ApiError(503, 'Админка ещё не настроена на сервере: нет api.env.')
            if method == 'POST' and path == '/login':
                return self.handle_login()
            if method == 'POST' and path == '/logout':
                return self.handle_logout()
            if method == 'GET' and path == '/session':
                return self.send_json(200, {'user': self.require_session()})
            if method == 'GET' and path == '/news':
                return self.handle_news()
            if method == 'GET' and path == '/deploy':
                return self.handle_deploy()
            if path.startswith('/posts/'):
                slug = path[len('/posts/'):]
                if method == 'PUT':
                    return self.handle_put_post(slug)
                if method == 'DELETE':
                    return self.handle_delete_post(slug)
            self.send_json(404, {'error': 'Не найдено'})
        except ApiError as e:
            self.send_json(e.status, {'error': e.message})
        except Exception as e:                            # noqa: BLE001 - never leak a traceback
            log(f'{method} {path} failed: {type(e).__name__}: {e}')
            self.send_json(500, {'error': 'Внутренняя ошибка сервера.'})

    # -------------------------------------------------------------- handlers

    def handle_login(self):
        self.require_same_origin()
        ip = self.client_ip()
        if self.store.login_blocked(ip):
            raise ApiError(429, 'Слишком много попыток входа. Подождите 15 минут.')
        data = self.read_json()
        user = (data.get('username') or '').strip()
        password = data.get('password') or ''
        expected_user = self.server.admin_user
        # Always run the hash so a wrong user name costs the same as a wrong password.
        ok = verify_password(password, self.server.admin_hash)
        if not (ok and hmac.compare_digest(user, expected_user)):
            self.store.record_failure(ip)
            log(f'login failed for {user!r} from {ip}')
            raise ApiError(401, 'Неверный логин или пароль.')
        self.store.clear_failures(ip)
        token = self.store.create_session(user)
        log(f'login ok for {user!r} from {ip}')
        self.send_json(200, {'user': user}, cookie=self.session_cookie(token))

    def handle_logout(self):
        self.store.drop_session(self.cookie_token())
        self.send_json(200, {'ok': True}, cookie=self.session_cookie('', max_age=0))

    def handle_news(self):
        self.require_session()
        commit_sha, _ = self.github.head()
        return self.send_json(200, self.github.read_news(commit_sha))

    def handle_deploy(self):
        self.require_session()
        run = self.github.latest_run()
        if not run:
            return self.send_json(200, {'run': None})
        return self.send_json(200, {'run': {
            'status': run.get('status'),
            'conclusion': run.get('conclusion'),
            'updated_at': run.get('updated_at'),
            'html_url': run.get('html_url'),
        }})

    def handle_put_post(self, slug):
        self.require_same_origin()
        self.require_session()
        data = self.read_json()
        uploads = clean_files(slug, data.get('files'))
        prefix = f'{IMAGES_DIR}{slug}/'

        # Work out the record and the images to drop from the current head. The
        # commit re-reads news.json anyway, so a race only costs the retry; the
        # deletions stay correct because they are intersected with what the
        # repository actually holds right now.
        commit_sha, _ = self.github.head()
        current = self.github.read_news(commit_sha)
        existing = next((p for p in (current.get('posts') or []) if p.get('slug') == slug), None)
        record = clean_post(slug, data, existing)
        in_repo = self.github.list_dir(f'{IMAGES_DIR}{slug}')
        files = uploads + [
            {'path': p, 'delete': True}
            for p in stale_images(record, [f['path'] for f in uploads], in_repo, prefix)
        ]

        def mutate(news):
            posts = news.get('posts') or []
            index = next((i for i, p in enumerate(posts) if p.get('slug') == slug), -1)
            if index >= 0:
                posts[index] = record
            else:
                posts.append(record)
            news['posts'] = posts
            return news

        verb = 'update' if existing else 'add'
        sha, news = self.github.commit(f'news: {verb} «{record["title"]}»', mutate, files)
        self.publisher.write_images(files)
        self.publisher.remove(f['path'] for f in files if f.get('delete'))
        warning = self.publisher.publish(news)
        log(f'{verb} {slug} in {sha[:8]}'
            + (f' (local rebuild failed: {warning})' if warning else ''))
        self.send_json(200, {'sha': sha, 'news': news, 'warning': warning})

    def handle_delete_post(self, slug):
        self.require_same_origin()
        self.require_session()
        if not SLUG_RE.match(slug):
            raise ApiError(400, 'Неверный slug.')
        title_box = {}

        def mutate(news):
            posts = news.get('posts') or []
            post = next((p for p in posts if p.get('slug') == slug), None)
            if post is None:
                raise ApiError(404, 'Пост не найден.')
            title_box['title'] = post.get('title') or slug
            news['posts'] = [p for p in posts if p.get('slug') != slug]
            return news

        files = [{'path': p, 'delete': True} for p in self.github.list_dir(f'{IMAGES_DIR}{slug}')]
        # The title is only known once mutate has found the post, so the commit
        # subject is built from the mutated state rather than passed in ready.
        sha, news = self.github.commit(
            lambda _news: f'news: delete «{title_box.get("title", slug)}»', mutate, files)
        self.publisher.remove_dir(f'{IMAGES_DIR}{slug}')
        warning = self.publisher.publish(news)
        log(f'deleted {slug} in {sha[:8]}' + (f' (local rebuild failed: {warning})' if warning else ''))
        self.send_json(200, {'sha': sha, 'news': news, 'warning': warning})

    def log_message(self, fmt, *args):
        log(f'{self.client_ip()} {fmt % args}')


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, store, github, publisher, admin_user, admin_hash, configured=True):
        super().__init__(addr, Handler)
        self.store = store
        self.github = github
        self.publisher = publisher
        self.admin_user = admin_user
        self.admin_hash = admin_hash
        self.configured = configured


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == 'hash-password':
        password = getpass.getpass('Пароль: ')
        again = getpass.getpass('Ещё раз: ')
        if password != again:
            raise SystemExit('Пароли не совпадают')
        if len(password) < 10:
            raise SystemExit('Слишком короткий пароль: минимум 10 символов')
        print(hash_password(password))
        return 0

    # A missing api.env must not crash-loop the container: the service stays up,
    # answers /health, and refuses everything else with a clear message until
    # the credentials are in place.
    missing = [k for k in ('ADMIN_USER', 'ADMIN_PASSWORD_HASH', 'GITHUB_TOKEN') if not os.environ.get(k)]
    store = Store(DB_PATH)
    github = GitHub(os.environ.get('GITHUB_TOKEN', ''))
    publisher = Publisher()
    server = Server(('', PORT), store, github, publisher,
                    os.environ.get('ADMIN_USER', ''), os.environ.get('ADMIN_PASSWORD_HASH', ''),
                    configured=not missing)
    if missing:
        log(f'NOT CONFIGURED: missing {", ".join(missing)} - only /health will answer')
    log(f'listening on :{PORT}, repo {REPO}@{BRANCH}, site {SITE_ROOT}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
