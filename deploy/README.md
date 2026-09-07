# Deploy

Static site, served by its own nginx container on Hermes, plus a GitHub Pages copy.

| | |
|---|---|
| Compose project | `ndu-static` |
| Config on server | `/opt/ndu-static` |
| Document root | `/var/www/ndu` |
| Port | `8083` |
| URL | http://185.217.199.92:8083 |
| GitHub Pages | https://bekkibay.github.io/ndu/ |

Nothing here touches `/opt/navoiyliklar`, `/opt/udea-static`, `/opt/wiut-static`
or `/opt/newuu-static` — separate project, separate container, separate port.

## First run on a new server

```bash
scp deploy/docker-compose.yml deploy/nginx-site.conf deploy/server-setup.sh root@HOST:/opt/ndu-static/
ssh root@HOST 'cd /opt/ndu-static && bash server-setup.sh'
```

`server-setup.sh` is idempotent and refuses to take a port another service
already listens on (`NDU_PORT=9093 bash server-setup.sh` to move it).

The CI deploy key must be authorised on the server once:

```bash
ssh root@HOST 'echo "ssh-ed25519 AAAA... github-actions-ndu" >> ~/.ssh/authorized_keys'
```

## Continuous deployment

`.github/workflows/deploy.yml` runs on every push to `main`:

1. `ci.yml` runs `scripts/check_links.py` as a gate — a broken internal link
   or a missing asset stops the deploy.
2. `scripts/stamp_assets.py` rewrites `style.css` / `main.js` references to
   `?v=<hash>` on the checkout, so browsers pick up a new design pass.
3. `rsync` uploads the site **without `--delete`**, so the workflow never
   removes anything already on the server. `preview/`, `scripts/`, `deploy/`,
   `.github/`, `download_assets.py` and `README.md` are not uploaded.
4. The compose project is reconciled (`docker compose up -d`) — a no-op when
   `deploy/` did not change.
5. The deploy fails unless `SITE_URL` answers with HTTP 200.
6. In parallel, the `pages` job publishes the same checkout to GitHub Pages
   (repository variable `ENABLE_PAGES=true`; the repo is public).

### Repository configuration

Secrets:

| Name | Value |
|---|---|
| `DEPLOY_HOST` | server IP |
| `DEPLOY_USER` | `root` |
| `DEPLOY_PORT` | `22` |
| `DEPLOY_PATH` | `/var/www/ndu` |
| `DEPLOY_SSH_KEY` | private half of the `github-actions-ndu` key |

Variables:

| Name | Value |
|---|---|
| `SITE_URL` | `http://185.217.199.92:8083` |
| `ENABLE_PAGES` | `true` |
