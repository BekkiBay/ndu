# Деплой сайта NDU на сервер Hermes

Сайт — статика, поэтому на сервере он живёт в отдельном контейнере nginx,
никак не связанном с боевым стеком `navoiyliklar` и с остальными макетами
(`udea-static`, `wiut-static`, `newuu-static`).

| Что | Значение |
|---|---|
| Сервер | `185.217.199.92` (Hermes, Ubuntu 24.04, вход под root) |
| Compose-проект | `ndu-static`, контейнеры `ndu-static` (nginx) и `ndu-counter` (счётчик просмотров) |
| Конфиг на сервере | `/opt/ndu-static/` |
| Document root | `/var/www/ndu` |
| Порт | `8083` |
| Адрес | http://185.217.199.92:8083 |
| GitHub Pages | https://bekkibay.github.io/ndu/ |

## Правило: ничего на сервере не удаляем

`rsync` в workflow запускается **без `--delete`** — деплой только добавляет и
обновляет файлы. Compose-проект ограничен своими контейнерами, `Caddyfile`
стека `navoiyliklar` автоматика не трогает.

Единственное исключение: страницы удалённых новостей. Сразу за основным
rsync идёт второй, `rsync --delete --include='news-*.html' --exclude='*'`,
который удаляет с сервера только файлы `news-*.html`, отсутствующие в сборке.
Ничего другого он тронуть не может: маска исключает все остальные файлы.

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

1. `check` — прогоняет `ci.yml`: юнит-тесты (`tests/`), штампы `?v=` у
   CSS/JS актуальны (`scripts/stamp_assets.py`), сборка новостей, все
   внутренние ссылки и ресурсы резолвятся (`scripts/check_links.py`); без
   этого деплой не пойдёт;
2. `deploy` — сборка новостей (`scripts/build_news.py`), rsync сайта в
   `/var/www/ndu`, точечное удаление страниц удалённых новостей,
   синхронизация `deploy/` в `/opt/ndu-static`, `docker compose -p ndu-static
   up -d`, перечитывание конфига nginx и проверка, что `SITE_URL` и
   `SITE_URL/views/health` отвечают `200`;
3. `pages` — параллельная публикация копии на GitHub Pages
   (переменная `ENABLE_PAGES=true`).

Секреты репозитория: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PORT`,
`DEPLOY_PATH` (`/var/www/ndu`), `DEPLOY_SSH_KEY` (приватная половина ключа
`github-actions-ndu`).
Переменные: `SITE_URL`, `ENABLE_PAGES`.

## Счётчик просмотров

Просмотры новостей считает контейнер `ndu-counter` (`deploy/counter/counter.py`,
Python stdlib + SQLite). Наружу порт не публикуется: nginx контейнера
`ndu-static` проксирует `/views/` в `http://counter:8080/`, поэтому страницы
и админка ходят к счётчику через тот же origin, что и сайт.

| Что | Как |
|---|---|
| Проверить | `curl http://127.0.0.1:8083/views/health` → `{"status": "ok"}` |
| Все счётчики | `curl http://127.0.0.1:8083/views/counts` |
| Логи | `docker logs -f ndu-counter` |
| База | том `ndu-counter-data`, файл `/data/views.db` внутри контейнера |
| Бэкап | `docker cp ndu-counter:/data/views.db ./views-$(date +%F).db` |
| Восстановить | `docker cp ./views.db ndu-counter:/data/views.db && docker restart ndu-counter` |

Один просмотр = одна пара (пост, посетитель) в сутки; посетитель — хеш IP и
User-Agent, в открытом виде не хранится. Боты по User-Agent не считаются.
Скрипт сервиса лежит в `/opt/ndu-static/counter/`, деплой обновляет его
вместе с остальным каталогом `deploy/`; после изменения скрипта контейнер
перезапускается командой `docker compose -p ndu-static restart counter`
(compose делает это сам, если менялся `docker-compose.yml`).

## Поддомен вместо порта

Чтобы отдавать сайт по домену, нужна A-запись и один блок `reverse_proxy`
в `/opt/navoiyliklar/Caddyfile`:

```
ndu.navoiyliklar.uz {
    reverse_proxy 127.0.0.1:8083
}
```

Это правка чужого стека, поэтому автоматикой не делается — только вручную.
