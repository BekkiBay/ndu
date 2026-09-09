// Thin GitHub REST client + "one commit per action" through the Git Data API.
export const OWNER = 'BekkiBay';
export const REPO = 'ndu';
export const NEWS_PATH = 'content/news.json';
const API = 'https://api.github.com';

export class GitHubError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export class GitHub {
  constructor(token, branch = 'main') {
    this.token = token;
    this.branch = branch;
  }

  async api(method, path, body) {
    const resp = await fetch(API + path, {
      method,
      headers: {
        Authorization: `Bearer ${this.token}`,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (resp.status === 204) return null;
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new GitHubError(resp.status, data.message || `GitHub ${resp.status}`);
    return data;
  }

  repo() {
    return this.api('GET', `/repos/${OWNER}/${REPO}`);
  }

  // Latest commit on the branch and the tree it points at.
  async head() {
    const ref = await this.api('GET', `/repos/${OWNER}/${REPO}/git/ref/heads/${this.branch}`);
    const commit = await this.api('GET', `/repos/${OWNER}/${REPO}/git/commits/${ref.object.sha}`);
    return { commitSha: ref.object.sha, treeSha: commit.tree.sha };
  }

  async readNews(commitSha) {
    const file = await this.api('GET', `/repos/${OWNER}/${REPO}/contents/${NEWS_PATH}?ref=${commitSha}`);
    const bytes = Uint8Array.from(atob(file.content.replace(/\n/g, '')), (c) => c.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  }

  // One commit: mutate(freshNews) -> nextNews, plus image files.
  // files: [{path, base64}] to add/replace, [{path, delete: true}] to remove.
  async commit(message, mutate, files) {
    for (let attempt = 0; attempt < 2; attempt++) {
      const { commitSha, treeSha } = await this.head();
      const news = await this.readNews(commitSha);
      const next = mutate(structuredClone(news));
      const tree = [{
        path: NEWS_PATH, mode: '100644', type: 'blob',
        content: JSON.stringify(next, null, 2) + '\n',
      }];
      for (const f of files) {
        if (f.delete) {
          tree.push({ path: f.path, mode: '100644', type: 'blob', sha: null });
          continue;
        }
        const blob = await this.api('POST', `/repos/${OWNER}/${REPO}/git/blobs`,
          { content: f.base64, encoding: 'base64' });
        tree.push({ path: f.path, mode: '100644', type: 'blob', sha: blob.sha });
      }
      const newTree = await this.api('POST', `/repos/${OWNER}/${REPO}/git/trees`, { base_tree: treeSha, tree });
      const newCommit = await this.api('POST', `/repos/${OWNER}/${REPO}/git/commits`,
        { message, tree: newTree.sha, parents: [commitSha] });
      try {
        await this.api('PATCH', `/repos/${OWNER}/${REPO}/git/refs/heads/${this.branch}`,
          { sha: newCommit.sha, force: false });
        return { sha: newCommit.sha, news: next };
      } catch (e) {
        // The branch moved under us: retry once from the new head.
        if (attempt === 0 && (e.status === 409 || e.status === 422)) continue;
        throw e;
      }
    }
    throw new GitHubError(409, 'Ветка изменилась во время сохранения, попробуйте ещё раз');
  }

  // Paths of the files directly inside a repository directory; [] when it does not exist.
  async listDir(path) {
    try {
      const items = await this.api('GET', `/repos/${OWNER}/${REPO}/contents/${path}?ref=${this.branch}`);
      return Array.isArray(items) ? items.filter((i) => i.type === 'file').map((i) => i.path) : [];
    } catch (e) {
      if (e.status === 404) return [];
      throw e;
    }
  }

  latestRun() {
    return this.api('GET', `/repos/${OWNER}/${REPO}/actions/runs?branch=${this.branch}&per_page=1`)
      .then((d) => d.workflow_runs?.[0] || null);
  }
}
