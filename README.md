# Макет C — Navoiy davlat universiteti (NavDU) · дизайн-концепт с видео

Одностраничный статический макет главной страницы сайта Навоийского государственного
университета. Контент — узбекский (латиница), все данные приведены как образец.

- **Live (Hermes):** http://185.217.199.92:8083
- **GitHub Pages:** https://bekkibay.github.io/ndu/

## Что внутри

- **Hero с фоновым видео** (`assets/hero-source.mp4`, постер `hero-still.jpg`): автозапуск без звука,
  кнопка пауза/играть, видео останавливается вне экрана, при скрытой вкладке, при открытом диалоге
  и при `prefers-reduced-motion`.
- Секции главной: цифры университета, новости, ступени образования, «Universitet haqida»,
  кампусная жизнь (с видеодиалогом), события, блок приёма, футер с контактами.
- Шапка становится компактной после прокрутки (`.scrolled`), мобильное меню с `aria-expanded`
  и закрытием по Escape; появление блоков — `.reveal` через IntersectionObserver.
- Шрифт Manrope лежит локально (`assets/manrope-*.woff2`, `assets/fonts.css`) — интернет для
  просмотра не нужен.

## Как открыть

Открыть `index.html` в браузере. Сборка не нужна.

## Структура

```
index.html            страница
style.css             стили (токены в :root, компоненты, адаптив)
main.js               видео, шапка, мобильное меню, reveal-анимации
assets/               изображения (webp + исходники png/jpg), видео, шрифты
assets/sources.json   откуда скачаны исходники
download_assets.py    скачивает исходники из sources.json заново
preview/              скриншоты
scripts/              check_links.py (CI), stamp_assets.py (деплой)
deploy/               docker-compose + nginx для Hermes, README по деплою
.github/workflows/    ci.yml (проверка ссылок), deploy.yml (rsync на Hermes + GitHub Pages)
```

## CI/CD

Каждый push в `main`: проверка ссылок и ассетов → rsync на Hermes (без `--delete`) → проверка,
что сайт отвечает 200 → параллельно публикация на GitHub Pages. Подробности в `deploy/README.md`.
