// NavDU news admin: edits content/news.json and the post images in BekkiBay/ndu
// through the GitHub API. Every action is exactly one commit; CI builds and
// deploys the site afterwards (1-2 minutes).
import { GitHub, GitHubError } from './github.js';
import { prepareImage, blobToBase64, blobToDataUrl } from './images.js';
import { slugify, isValidSlug } from './slug.js';

const SITE_ROOT = new URL('..', location.href); // http://host:8083/  or  https://…/ndu/
const TOKEN_KEY = 'ndu.admin.token';
const BRANCH = localStorage.getItem('ndu.admin.branch') || 'main'; // dev override only
const IMAGES_DIR = 'images/nsu/news/';
const $ = (id) => document.getElementById(id);

const state = {
  gh: null,
  news: null,           // {posts:[...]} as last read from the repository
  views: {},            // slug -> count
  editing: null,        // slug of the post being edited; null for a new post
  slugTouched: false,   // the user edited the slug by hand
  cover: null,          // {blob, url} pending cover, or null (keep the current one)
  gallery: [],          // [{path} | {blob, url}] in display order
  quill: null,
  runTimer: null,
  saving: false,
};

// ---------------------------------------------------------------- helpers

function siteUrl(path) {
  return new URL(path, SITE_ROOT).href;
}

function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function formatDate(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-');
  return `${d}.${m}.${y}`;
}

const MONTHS_UZ = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
  'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'];

function formatDateUz(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-').map(Number);
  return `${d}-${MONTHS_UZ[m - 1]}, ${y}`;
}

// Same order as scripts/build_news.py: dated posts newest first, then undated in file order.
function sortPosts(posts) {
  const dated = posts.filter((p) => p.date);
  const undated = posts.filter((p) => !p.date);
  dated.sort((a, b) => b.date.localeCompare(a.date) || (b.updated || '').localeCompare(a.updated || ''));
  return dated.concat(undated);
}

function stamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

function showScreen(name) {
  for (const s of ['login', 'list', 'edit']) $(`screen-${s}`).hidden = s !== name;
  $('logout').hidden = name === 'login';
  $('deploy').hidden = name === 'login';
  window.scrollTo(0, 0);
}

function setError(id, message) {
  const el = $(id);
  el.textContent = message || '';
  el.hidden = !message;
}

function describe(e) {
  if (e instanceof GitHubError) return `GitHub: ${e.message} (${e.status})`;
  return e && e.message ? e.message : String(e);
}

// Any 401 means the token is gone: back to the login screen.
async function guarded(fn) {
  try {
    return await fn();
  } catch (e) {
    if (e instanceof GitHubError && e.status === 401) {
      logout('Токен отозван или истёк. Войдите заново.');
      return undefined;
    }
    throw e;
  }
}

// ---------------------------------------------------------------- auth

async function login(token, fromForm) {
  const gh = new GitHub(token, BRANCH);
  $('login-btn').disabled = true;
  setError('login-error', '');
  try {
    await gh.repo();
  } catch (e) {
    $('login-btn').disabled = false;
    const msg = e instanceof GitHubError && e.status === 401 ? 'Токен не принят GitHub.'
      : e instanceof GitHubError && (e.status === 403 || e.status === 404) ? 'У токена нет доступа к BekkiBay/ndu.'
        : describe(e);
    if (fromForm) setError('login-error', msg);
    else localStorage.removeItem(TOKEN_KEY);
    showScreen('login');
    return;
  }
  $('login-btn').disabled = false;
  localStorage.setItem(TOKEN_KEY, token);
  state.gh = gh;
  await loadList();
}

function logout(message) {
  localStorage.removeItem(TOKEN_KEY);
  state.gh = null;
  state.news = null;
  clearTimeout(state.runTimer);
  $('token').value = '';
  setError('login-error', message || '');
  showScreen('login');
}

// ---------------------------------------------------------------- list

async function loadList(notice) {
  const viewsPromise = fetch(siteUrl('views/counts'), { cache: 'no-store' })
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}));
  const head = await guarded(() => state.gh.head());
  if (!head) return;
  state.news = await guarded(() => state.gh.readNews(head.commitSha));
  if (!state.news) return;
  state.views = await viewsPromise;
  renderList();
  const n = $('notice');
  n.textContent = notice || '';
  n.hidden = !notice;
  showScreen('list');
  pollRun();
}

function renderList() {
  const posts = sortPosts(state.news.posts);
  $('count').textContent = `(${posts.length})`;
  const rows = $('rows');
  rows.textContent = '';
  for (const p of posts) {
    const tr = document.createElement('tr');
    const img = document.createElement('img');
    img.src = siteUrl(p.cover);
    img.alt = '';
    img.loading = 'lazy';
    tr.appendChild(document.createElement('td')).appendChild(img);
    const a = document.createElement('a');
    a.className = 'title';
    a.href = siteUrl(`news-${p.slug}.html`);
    a.target = '_blank';
    a.rel = 'noopener';
    a.textContent = p.title;
    tr.appendChild(document.createElement('td')).appendChild(a);
    tr.appendChild(document.createElement('td')).textContent = formatDate(p.date);
    const views = tr.appendChild(document.createElement('td'));
    views.className = 'num';
    views.textContent = p.slug in state.views ? String(state.views[p.slug]) : '—';
    const actions = tr.appendChild(document.createElement('td'));
    actions.className = 'actions';
    const edit = document.createElement('button');
    edit.type = 'button';
    edit.textContent = 'Изменить';
    edit.onclick = () => openEditor(p.slug);
    const del = document.createElement('button');
    del.type = 'button';
    del.className = 'danger';
    del.textContent = 'Удалить';
    del.onclick = () => deletePost(p.slug);
    actions.append(edit, del);
    rows.appendChild(tr);
  }
}

// ---------------------------------------------------------------- deploy status

async function pollRun() {
  clearTimeout(state.runTimer);
  const box = $('deploy');
  let run;
  try {
    run = await state.gh.latestRun();
  } catch (e) {
    box.textContent = e instanceof GitHubError && e.status === 403
      ? 'Статус деплоя: нет права Actions — Read у токена' : `Статус деплоя недоступен: ${describe(e)}`;
    return;
  }
  if (!run) {
    box.textContent = 'Деплоев ещё не было';
    return;
  }
  const when = new Date(run.updated_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' });
  let label;
  if (run.status !== 'completed') label = run.status === 'queued' ? '⏳ Деплой в очереди' : '⏳ Деплой выполняется';
  else if (run.conclusion === 'success') label = '✅ Деплой успешен';
  else if (run.conclusion === 'cancelled') label = '⚠️ Деплой отменён';
  else label = '❌ Деплой упал';
  box.textContent = '';
  box.append(`${label} · ${when} · `);
  const a = document.createElement('a');
  a.href = run.html_url;
  a.target = '_blank';
  a.rel = 'noopener';
  a.textContent = 'подробности';
  box.appendChild(a);
  state.runTimer = setTimeout(pollRun, run.status !== 'completed' ? 20000 : 60000);
}

// ---------------------------------------------------------------- editor

function ensureQuill() {
  if (state.quill) return state.quill;
  state.quill = new Quill('#quill', {
    theme: 'snow',
    placeholder: 'Текст новости…',
    modules: {
      toolbar: {
        container: [
          [{ header: [2, 3, false] }],
          ['bold', 'italic', 'underline'],
          ['link', 'blockquote'],
          [{ list: 'ordered' }, { list: 'bullet' }],
          ['image'],
          ['clean'],
        ],
        handlers: { image: pickInlineImage },
      },
    },
  });
  state.quill.on('text-change', renderPreview);
  return state.quill;
}

function pickInlineImage() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.onchange = async () => {
    const file = input.files[0];
    if (!file) return;
    try {
      const { blob } = await prepareImage(file);
      const dataUrl = await blobToDataUrl(blob);
      const quill = state.quill;
      const range = quill.getSelection(true);
      quill.insertEmbed(range.index, 'image', dataUrl, 'user');
      quill.setSelection(range.index + 1, 0, 'silent');
    } catch (e) {
      setError('form-error', `Не удалось обработать картинку: ${describe(e)}`);
    }
  };
  input.click();
}

// Quill 2 serialises every space as &nbsp;, which would stop text from wrapping on the site.
function bodyHtml() {
  return state.quill.getSemanticHTML().replace(/&nbsp;/g, ' ');
}

function findPost(slug) {
  return state.news.posts.find((p) => p.slug === slug) || null;
}

// Body HTML as stored in the repository -> HTML the editor can display.
function absolutize(html) {
  return html.replaceAll(`src="${IMAGES_DIR}`, `src="${siteUrl(IMAGES_DIR)}`);
}

function openEditor(slug) {
  const post = slug ? findPost(slug) : null;
  const quill = ensureQuill();
  state.editing = post ? post.slug : null;
  state.slugTouched = false;
  state.cover = null;
  state.gallery = post ? post.gallery.map((path) => ({ path })) : [];
  setError('form-error', '');
  $('edit-title').textContent = post ? 'Редактирование поста' : 'Новый пост';
  $('f-title').value = post ? post.title : '';
  $('f-date').value = post ? (post.date || '') : today();
  $('f-slug').value = post ? post.slug : '';
  $('f-slug').readOnly = !!post;
  $('f-excerpt').value = post ? (post.excerpt || '') : '';
  $('excerpt-len').textContent = String($('f-excerpt').value.length);
  const cover = $('cover-preview');
  cover.hidden = !post;
  cover.src = post ? siteUrl(post.cover) : '';
  $('f-cover').value = '';
  $('f-gallery').value = '';
  $('delete').hidden = !post;
  quill.setContents([], 'silent');
  if (post && post.body) quill.clipboard.dangerouslyPasteHTML(0, absolutize(post.body), 'silent');
  quill.history.clear();
  updateSlugPreview();
  renderGallery();
  renderPreview();
  showScreen('edit');
}

function updateSlugPreview() {
  $('slug-preview').textContent = $('f-slug').value || '…';
}

function renderGallery() {
  const box = $('gallery');
  box.textContent = '';
  state.gallery.forEach((item, i) => {
    const div = document.createElement('div');
    div.className = 'item';
    const img = document.createElement('img');
    img.src = item.blob ? item.url : siteUrl(item.path);
    img.alt = '';
    div.appendChild(img);
    const tools = document.createElement('div');
    tools.className = 'tools';
    const mk = (text, title, onclick, disabled) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = text;
      b.title = title;
      b.disabled = !!disabled;
      b.onclick = onclick;
      return b;
    };
    tools.append(
      mk('↑', 'Выше', () => { [state.gallery[i - 1], state.gallery[i]] = [state.gallery[i], state.gallery[i - 1]]; renderGallery(); renderPreview(); }, i === 0),
      mk('↓', 'Ниже', () => { [state.gallery[i + 1], state.gallery[i]] = [state.gallery[i], state.gallery[i + 1]]; renderGallery(); renderPreview(); }, i === state.gallery.length - 1),
      mk('×', 'Убрать', () => { state.gallery.splice(i, 1); renderGallery(); renderPreview(); }),
    );
    div.appendChild(tools);
    box.appendChild(div);
  });
}

function currentCoverUrl() {
  if (state.cover) return state.cover.url;
  const post = state.editing ? findPost(state.editing) : null;
  return post ? siteUrl(post.cover) : '';
}

function renderPreview() {
  if (!state.quill) return;
  $('p-title').textContent = $('f-title').value || 'Заголовок';
  $('p-date').textContent = formatDateUz($('f-date').value);
  const cover = currentCoverUrl();
  $('p-hero').style.backgroundImage = cover ? `url("${cover}")` : '';
  $('p-body').innerHTML = bodyHtml();
  const g = $('p-gallery');
  g.textContent = '';
  for (const item of state.gallery) {
    const img = document.createElement('img');
    img.src = item.blob ? item.url : siteUrl(item.path);
    img.alt = '';
    g.appendChild(img);
  }
}

// ---------------------------------------------------------------- save

function validate() {
  const title = $('f-title').value.trim();
  if (!title) return { error: 'Введите заголовок.', focus: 'f-title' };
  const slug = $('f-slug').value.trim();
  if (!isValidSlug(slug)) return { error: 'Slug: только латинские буквы, цифры и дефисы, до 80 символов.', focus: 'f-slug' };
  if (!state.editing && findPost(slug)) return { error: `Slug «${slug}» уже занят другим постом.`, focus: 'f-slug' };
  const date = $('f-date').value;
  if (date && !/^\d{4}-\d{2}-\d{2}$/.test(date)) return { error: 'Дата в формате ГГГГ-ММ-ДД.', focus: 'f-date' };
  if (!state.cover && !(state.editing && findPost(state.editing))) return { error: 'Выберите обложку.', focus: 'f-cover' };
  return { title, slug, date: date || null };
}

// Paths of every image of a post that lives in the post's own folder.
function ownImages(post, dir) {
  const out = new Set();
  if (!post) return out;
  if (post.cover && post.cover.startsWith(dir)) out.add(post.cover);
  for (const p of post.gallery || []) if (p.startsWith(dir)) out.add(p);
  const doc = new DOMParser().parseFromString(post.body || '', 'text/html');
  for (const img of doc.querySelectorAll('img')) {
    const src = img.getAttribute('src') || '';
    if (src.startsWith(dir)) out.add(src);
  }
  return out;
}

// Turns the editor state into the post record + the files to upload.
async function collectFiles(slug, existing) {
  const dir = `${IMAGES_DIR}${slug}/`;
  const mark = stamp();
  const files = [];

  let cover = existing ? existing.cover : null;
  if (state.cover) {
    cover = `${dir}${mark}-cover.jpg`;
    files.push({ path: cover, base64: await blobToBase64(state.cover.blob) });
  }

  const doc = new DOMParser().parseFromString(bodyHtml(), 'text/html');
  let n = 0;
  for (const img of doc.querySelectorAll('img')) {
    const src = img.getAttribute('src') || '';
    if (src.startsWith('data:image/')) {
      n += 1;
      const path = `${dir}${mark}-${String(n).padStart(2, '0')}.jpg`;
      files.push({ path, base64: src.split(',')[1] });
      img.setAttribute('src', path);
    } else if (src.startsWith(siteUrl(IMAGES_DIR))) {
      img.setAttribute('src', src.slice(SITE_ROOT.href.length));
    }
  }
  let body = doc.body.innerHTML.trim();
  body = body.replace(/(<p>(<br>|\s|&nbsp;)*<\/p>\s*)+$/, '');

  const gallery = [];
  let g = 0;
  for (const item of state.gallery) {
    if (item.blob) {
      g += 1;
      const path = `${dir}${mark}-g${String(g).padStart(2, '0')}.jpg`;
      files.push({ path, base64: await blobToBase64(item.blob) });
      gallery.push(path);
    } else {
      gallery.push(item.path);
    }
  }

  const record = { cover, body, gallery };
  const keep = ownImages(record, dir);
  const inRepo = new Set(await state.gh.listDir(dir.slice(0, -1)));
  for (const path of ownImages(existing, dir)) {
    if (!keep.has(path) && inRepo.has(path)) files.push({ path, delete: true });
  }
  return { files, ...record };
}

async function savePost(event) {
  event.preventDefault();
  if (state.saving) return;
  setError('form-error', '');
  const v = validate();
  if (v.error) {
    setError('form-error', v.error);
    $(v.focus).focus();
    return;
  }
  state.saving = true;
  $('save').disabled = true;
  $('save').textContent = 'Публикуется…';
  try {
    const existing = state.editing ? findPost(state.editing) : null;
    const { files, cover, body, gallery } = await collectFiles(v.slug, existing);
    const excerpt = $('f-excerpt').value.trim();
    const record = {
      slug: v.slug, title: v.title, date: v.date, excerpt, cover, body, gallery,
      updated: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    };
    const message = `news: ${existing ? 'update' : 'add'} «${v.title}»`;
    const result = await guarded(() => state.gh.commit(message, (news) => {
      const i = news.posts.findIndex((p) => p.slug === v.slug);
      if (i >= 0) news.posts[i] = record;
      else news.posts.push(record);
      return news;
    }, files));
    if (!result) return;
    state.news = result.news;
    await loadList('Сохранено. Сайт обновится через 1–2 минуты после завершения деплоя.');
  } catch (e) {
    setError('form-error', `Не удалось сохранить: ${describe(e)}`);
  } finally {
    state.saving = false;
    $('save').disabled = false;
    $('save').textContent = 'Опубликовать';
  }
}

async function deletePost(slug) {
  const post = findPost(slug);
  if (!post) return;
  if (!confirm(`Удалить пост «${post.title}»? Страница и её фото исчезнут с сайта после деплоя.`)) return;
  const dir = `${IMAGES_DIR}${slug}`;
  try {
    const files = (await guarded(() => state.gh.listDir(dir)) || []).map((path) => ({ path, delete: true }));
    const result = await guarded(() => state.gh.commit(`news: delete «${post.title}»`, (news) => {
      news.posts = news.posts.filter((p) => p.slug !== slug);
      return news;
    }, files));
    if (!result) return;
    state.news = result.news;
    await loadList(`Пост «${post.title}» удалён. Сайт обновится через 1–2 минуты.`);
  } catch (e) {
    alert(`Не удалось удалить: ${describe(e)}`);
  }
}

// ---------------------------------------------------------------- wiring

function boot() {
  $('login-form').addEventListener('submit', (e) => {
    e.preventDefault();
    login($('token').value.trim(), true);
  });
  $('logout').addEventListener('click', () => logout());
  $('new-post').addEventListener('click', () => openEditor(null));
  $('back').addEventListener('click', () => loadList());
  $('cancel').addEventListener('click', () => loadList());
  $('post-form').addEventListener('submit', savePost);
  $('delete').addEventListener('click', () => state.editing && deletePost(state.editing));

  $('f-title').addEventListener('input', () => {
    if (!state.editing && !state.slugTouched) $('f-slug').value = slugify($('f-title').value);
    updateSlugPreview();
    renderPreview();
  });
  $('f-slug').addEventListener('input', () => {
    state.slugTouched = true;
    updateSlugPreview();
  });
  $('f-date').addEventListener('input', renderPreview);
  $('f-excerpt').addEventListener('input', () => {
    $('excerpt-len').textContent = String($('f-excerpt').value.length);
  });
  $('f-cover').addEventListener('change', async () => {
    const file = $('f-cover').files[0];
    if (!file) return;
    try {
      state.cover = await prepareImage(file);
      const img = $('cover-preview');
      img.src = state.cover.url;
      img.hidden = false;
      renderPreview();
    } catch (e) {
      setError('form-error', `Не удалось обработать обложку: ${describe(e)}`);
    }
  });
  $('f-gallery').addEventListener('change', async () => {
    try {
      for (const file of $('f-gallery').files) state.gallery.push(await prepareImage(file));
      $('f-gallery').value = '';
      renderGallery();
      renderPreview();
    } catch (e) {
      setError('form-error', `Не удалось обработать фото: ${describe(e)}`);
    }
  });

  const token = localStorage.getItem(TOKEN_KEY);
  if (token) login(token, false);
  else showScreen('login');
}

boot();
