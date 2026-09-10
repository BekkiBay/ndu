// Client of the admin backend (deploy/api/api.py), served under /api/ by nginx.
//
// Replaces the old direct-to-GitHub client: the browser no longer holds a
// GitHub token, it holds a session cookie the server issued. The cookie is
// HttpOnly, so nothing here can read it; `credentials: 'same-origin'` is what
// makes the browser send it.
const BASE = new URL('../api/', import.meta.url); // /admin/api.js -> /api/

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

// A site copy without the backend (GitHub Pages) answers /api/ with its 404
// page, so a non-JSON answer means "there is no backend here".
const NO_BACKEND = 'Здесь админка не работает: откройте https://ndu.uz/admin/';

async function call(method, path, body) {
  let resp;
  try {
    resp = await fetch(new URL(path, BASE), {
      method,
      credentials: 'same-origin',
      cache: 'no-store',
      // A cross-site form cannot set this header, so it also acts as the CSRF check.
      headers: { 'X-Requested-With': 'ndu-admin', ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError(0, `Нет связи с сервером: ${e.message}`);
  }
  const text = await resp.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new ApiError(resp.status, resp.status === 404 ? NO_BACKEND : 'Сервер ответил неожиданно.');
  }
  if (!resp.ok) throw new ApiError(resp.status, data.error || `Ошибка ${resp.status}`);
  return data;
}

export const Api = {
  login: (username, password) => call('POST', 'login', { username, password }),
  logout: () => call('POST', 'logout'),
  session: () => call('GET', 'session'),
  news: () => call('GET', 'news'),
  deploy: () => call('GET', 'deploy'),
  // post: {title, date, excerpt, cover, body, gallery, files:[{path, base64}]}
  savePost: (slug, post) => call('PUT', `posts/${encodeURIComponent(slug)}`, post),
  deletePost: (slug) => call('DELETE', `posts/${encodeURIComponent(slug)}`),
};
