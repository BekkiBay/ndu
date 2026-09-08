# Деплой сайта NDU на сервер Hermes

Сайт — статика, поэтому на сервере он живёт в отдельном контейнере nginx,
никак не связанном с боевым стеком `navoiyliklar` и с остальными макетами
(`udea-static`, `wiut-static`, `newuu-static`).

| Что | Значение |
|---|---|
| Сервер | `185.217.199.92` (Hermes, Ubuntu 24.04, вход под root) |
| Compose-проект | `ndu-static`, контейнер `ndu-static` |
| Конфиг на сервере | `/opt/ndu-static/` |
| Document root | `/var/www/ndu` |
| Порт | `8083` |
| Адрес | http://185.217.199.92:8083 |
| GitHub Pages | https://bekkibay.github.io/ndu/ |

## Правило: ничего на сервере не удаляем

`rsync` в workflow запускается **без `--delete`** — деплой только добавляет и
обновляет файлы. Compose-проект ограничен своим контейнером, `Caddyfile`
стека `navoiyliklar` автоматика не трогает.

## Первый запуск (делается один раз, вручную под root)

```bash
scp deploy/docker-compose.yml deploy/nginx-site.conf deploy/server-setup.sh root@185.217.199.92:/opt/ndu-static/
ssh root@185.217.199.92 'bash /opt/ndu-static/server-setup.sh'
```

Другой порт: `NDU_PORT=9093 bash server-setup.sh`.
Скрипт идемпотентен и откажется занимать порт, если тот занят кем-то ещё.

Ключ CI один раз добавляется на сервер:

```bash
ssh root@185.217.199.92 'echo "ssh-ed25519 AAAA... github-actions-ndu" >> ~/.ssh/authorized_keys'
```

## Дальше — автоматически

`.github/workflows/deploy.yml` на каждый push в `main`:

1. `check` — прогоняет `ci.yml` (`scripts/check_links.py`: все внутренние
   ссылки и ресурсы должны резолвиться; `scripts/stamp_assets.py`: штампы
   `?v=` у CSS/JS актуальны), без этого деплой не пойдёт;
2. `deploy` — rsync сайта в `/var/www/ndu`, синхронизация `deploy/` в
   `/opt/ndu-static`, `docker compose -p ndu-static up -d`, перечитывание
   конфига nginx и проверка, что `SITE_URL` отвечает `200`;
3. `pages` — параллельная публикация копии на GitHub Pages
   (переменная `ENABLE_PAGES=true`).

Секреты репозитория: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PORT`,
`DEPLOY_PATH` (`/var/www/ndu`), `DEPLOY_SSH_KEY` (приватная половина ключа
`github-actions-ndu`).
Переменные: `SITE_URL`, `ENABLE_PAGES`.

## Поддомен вместо порта

Чтобы отдавать сайт по домену, нужна A-запись и один блок `reverse_proxy`
в `/opt/navoiyliklar/Caddyfile`:

```
ndu.navoiyliklar.uz {
    reverse_proxy 127.0.0.1:8083
}
```

Это правка чужого стека, поэтому автоматикой не делается — только вручную.
