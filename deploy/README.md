# Деплой макета на сервер Hermes

Сайт — статика, поэтому на сервере он живёт в отдельном контейнере nginx,
никак не связанном с боевым стеком `navoiyliklar` и с `udea-static`.

| Что | Значение |
|---|---|
| Сервер | `185.217.199.92` (Hermes, Ubuntu 24.04, вход под root) |
| Compose-проект | `wiut-static`, контейнер `wiut-static` |
| Конфиг на сервере | `/opt/wiut-static/` |
| Document root | `/var/www/wuit-navoiyliklar` |
| Порт | `8081` |
| Адрес | http://185.217.199.92:8081 |

## Правило: ничего на сервере не удаляем

`rsync` в workflow запускается **без `--delete`** — деплой только добавляет и
обновляет файлы. Compose-проект ограничен своим контейнером, `Caddyfile`
стека `navoiyliklar` автоматика не трогает.

## Первый запуск (делается один раз, вручную под root)

```bash
scp -r deploy/* root@185.217.199.92:/opt/wiut-static/
ssh root@185.217.199.92 'bash /opt/wiut-static/server-setup.sh'
```

Другой порт: `WIUT_PORT=9091 bash server-setup.sh`.
Скрипт идемпотентен и откажется занимать порт, если тот занят кем-то ещё.

## Дальше — автоматически

`.github/workflows/deploy.yml` на каждый push в `main`:

1. `check` — прогоняет `ci.yml` (`scripts/check_links.py`: все внутренние
   ссылки и ресурсы должны резолвиться), без этого деплой не пойдёт;
2. `deploy` — rsync сайта в `/var/www/wuit-navoiyliklar`, синхронизация
   `deploy/` в `/opt/wiut-static`, `docker compose -p wiut-static up -d`,
   и проверка, что `SITE_URL` отвечает `200`;
3. `pages` — параллельная публикация копии на GitHub Pages.

Секреты репозитория: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PORT`,
`DEPLOY_PATH`, `DEPLOY_SSH_KEY` (отдельный ключ `github-actions-wiut`,
добавлен в `~/.ssh/authorized_keys` root'а).
Переменные: `SITE_URL`, `ENABLE_PAGES`.

## Поддомен вместо порта

Чтобы отдавать макет по домену, нужна A-запись и один блок `reverse_proxy`
в `/opt/navoiyliklar/Caddyfile`:

```
wiut.navoiyliklar.uz {
    reverse_proxy 127.0.0.1:8081
}
```

Это правка чужого стека, поэтому автоматикой не делается — только вручную.
