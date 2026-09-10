# NDU — сайт Навоийского государственного университета

Итоговый проект. Основа — макет WIUT (дизайн wiut.uz); дальше в него по кусочкам
переезжают лучшие части остальных макетов (Макет 2, Макет 3, Макет C).
Репозиторий: https://github.com/BekkiBay/ndu

Многостраничный статический сайт **Навоийского государственного университета
(NavDU)**, собранный в дизайне [wiut.uz](https://www.wiut.uz/): вёрстка, CSS, JS,
шрифты и компоненты взяты у оригинального шаблона (Joomla + Helix Ultimate +
SP Page Builder), а весь контент — с [nsuz.uz](https://nsuz.uz/uz).

## Запуск

ES-модули (Bootstrap 5, Joomla core) не грузятся по `file://`, поэтому нужен
локальный HTTP-сервер:

```bash
cd NDU
python3 scripts/build_news.py   # генерирует news.html и news-*.html из content/news.json
python3 -m http.server 8899
```

Открыть http://localhost:8899/

С телефона в той же Wi-Fi сети: `ipconfig getifaddr en0`, затем `http://<IP>:8899/`.

## Структура сайта

**107 страниц**, меню повторяет структуру nsuz.uz:

| Раздел | Страниц | Примеры |
|---|---|---|
| Главная | 1 | `index.html` |
| UNIVERSITET | 37 | `about.html`, `about-history.html`, `about-rector.html`, `about-governance-*`, `about-departments-*`, `about-regulations-*`, `about-partnerships-*` |
| TA'LIM | 8 | `education-bachelor.html`, `education-master.html`, `education-phd-dsc.html`, `education-calendar.html`, `education-grading.html` |
| FAKULTETLAR | 8 (`faculties.html` + 7) | `faculties.html`, `faculty-tillar.html`, `faculty-tarix.html`, … (7 факультетов) |
| QABUL | 15 | `admissions-study.html`, `admissions-bachelor*.html`, `admissions-master*.html`, `admissions-international*.html`, `reception.html` |
| ILMIY FAOLIYAT | 10 | `research.html`, `research-council.html`, `research-journals.html`, `articles.html` |
| TALABALAR HAYOTI | 13 | `student-life.html`, `student-life-library.html`, `student-life-sports.html`, `student-life-student-council*.html` |
| XALQARO | 1 | `international-office.html` |
| Новости | 12 | `news.html` + посты из `content/news.json` (генерируются, см. ниже) |
| Прочее | 2 | `contact.html`, `brosdcast.html` |

Все ссылки внутри сайта рабочие (проверено: 0 битых), формы — заглушки
(`onsubmit="return false"`), кнопка «Hujjat topshirish» ведёт на `qabul.nsu.uz`.

## Что где

```
index.html                      главная (дизайн главной wiut.uz, контент NavDU)
<раздел>-<подраздел>.html       внутренние страницы (плоские имена = относительные пути работают)
content/news.json               посты новостей — источник правды (правится админкой)
images/nsu/news/<slug>/         фотографии поста, загруженные через админку
admin/                          админка новостей (см. «Новости и админка»)
scripts/build_news.py           генерирует news.html, news-*.html и карусель на главной
deploy/counter/counter.py       сервис счётчика просмотров (контейнер ndu-counter)
tests/                          юнит-тесты сборки и счётчика (python3 -m unittest discover -s tests)
assets/css/nsu.css              стили контентных блоков NavDU (палитра/шрифты WIUT)
images/nsu/                     фотографии и логотип NavDU
templates/lt_university/        шаблон WIUT: CSS, JS, шрифты
components/com_sppagebuilder/   SP Page Builder: слайдеры, аддоны
media/                          Joomla core, Bootstrap 5, jQuery, ConvertForms
```

## Новости и админка

Новости не лежат в репозитории готовыми страницами. Источник правды —
`content/news.json`: массив постов с полями `slug`, `title`, `date`
(`YYYY-MM-DD` или `null`), `excerpt`, `cover`, `body` (HTML из редактора),
`gallery`, `updated`. Из него `scripts/build_news.py` генерирует:

- `news-<slug>.html` — страницу каждого поста (оболочка берётся из
  `contact.html`, поэтому шапка и подвал новостей всегда совпадают с сайтом);
- `news.html` — список карточек, сначала посты с датой (новые выше), потом без;
- блок между маркерами `<!-- news:carousel -->` и `<!-- /news:carousel -->` в
  `index.html` — карусель из шести последних постов.

`news.html` и `news-*.html` в `.gitignore`: CI собирает их перед проверками и
деплоем, локально — команда из раздела «Запуск». `index.html` остаётся в git,
сборка правит в нём только блок между маркерами.

**Админка** — `https://ndu.uz/admin/`. Создание, редактирование и удаление
постов, текст в визуальном редакторе (Quill), обложка, фото в тексте и галерея.

**Вход по логину и паролю.** Пароль проверяет бэкенд админки
(`deploy/api/api.py`, контейнер `ndu-api`, доступен через nginx по `/api/`);
в браузере остаётся только сессия в cookie `HttpOnly`. Каждое действие —
по-прежнему **один коммит** в `main`, но делает его сервер своим
GitHub-токеном, и он же сразу пересобирает страницы новостей в `/var/www/ndu`.
Пост виден на сайте за секунды; обычный деплой позже кладёт те же файлы.
Настройка и смена пароля — в `deploy/README.md`.

Бэкенд есть только на сервере, поэтому на копии GitHub Pages админка не
работает и сразу говорит об этом.

Фото сжимаются в браузере (длинная сторона ≤ 1600 px, JPEG) и кладутся в
`images/nsu/news/<slug>/` с меткой времени в имени, чтобы замена картинки не
упиралась в кэш браузера. При удалении поста удаляется и его папка; общие файлы
`images/nsu/news/*.jpg` импортированных постов админка не трогает.

**Просмотры** считает контейнер `ndu-counter` на Hermes
(`deploy/counter/counter.py`), доступный через nginx сайта по адресу
`/views/`: страница поста делает `POST views/hit`, админка читает
`views/counts`. Один просмотр на (пост, посетитель, сутки), боты не считаются.
На копии GitHub Pages счётчика нет — блок просмотров там просто скрыт.

## Контент NavDU

- Тексты, заголовки, списки, таблицы и структура меню — с nsuz.uz/uz (узбекский).
- Ректор: Muxiddin Baxriddinovich Kalonov, DSc, professor.
- Контакты: Navoiy sh., G'alaba shoh ko'chasi, 103 · +998 (79) 223-77-89 ·
  info@nsu.uz, admission@nsu.uz · соцсети nsu.uz.
- Цифры: 19 500 талаба, 550+ профессор-преподаватель, 7 факультетов, 28+ кафедр.
- Дат у новостей на nsuz.uz нет — поэтому в карточках новостей вместо даты стоит
  рубрика «YANGILIKLAR» (даты не выдумывались).
- Партнёры на nsuz.uz даны текстом (без логотипов), поэтому карусель логотипов
  WIUT заменена на плитки с названиями партнёров и странами.
- Видео-фон первого слайда — `images/nsu/video/hero.mp4` (1.2 МБ, 12 с, съёмка
  того же читального зала, что и на фото слайда), взято из `Макет 2`.

- Из шаблона WIUT удалены: виджет доступности Joomla (иконка инвалидной коляски,
  `media/vendor/accessibility/js/accessibility.min.js` + его инициализация) и
  видео-фон второго слайда hero (`<div class="sp-video-background">` с чужим
  YouTube-роликом — именно он давал белый «пустой» слайд при перелистывании).

## Проверено

- 0 битых внутренних ссылок и 0 битых ссылок на ресурсы (107 страниц).
- 0 HTTP-404 при загрузке страниц в браузере.
- Нет горизонтального переполнения на 320/375/414/768/1024/1280/1440/1920 px.
- Мобильное off-canvas меню и десктопное мега-меню собраны заново под структуру NavDU.
- Слайдеры (hero, новости, талабалик хаёти, партнёры) и анимации работают.


## Деплой

Живая версия: **http://185.217.199.92:8083** (сервер Hermes) и копия на
**https://bekkibay.github.io/ndu/**.

CI/CD — `.github/workflows/`: `ci.yml` гоняет юнит-тесты, проверяет штампы
`?v=`, собирает новости и проверяет, что все внутренние ссылки и ресурсы
резолвятся; `deploy.yml` после успешной проверки раскатывает сайт на Hermes
(rsync без `--delete`; единственное исключение — страницы удалённых новостей
`news-*.html`) и на GitHub Pages, поднимает контейнер счётчика. Подробности и
первичная настройка сервера — в [`deploy/README.md`](deploy/README.md).

## Как пересобрать

Новости собираются `scripts/build_news.py` из репозитория (см. выше).
Остальной сайт генерировался скриптами, которые лежат вне репозитория, в
рабочей папке сессии: `site_data.py` (парсинг nsuz.uz) → `build.py`
(внутренние страницы) → `gen_home.py` (главная). Шапка/подвал/меню собираются
в `shell.py`, контентные блоки — в `render.py`, структура меню — в
`menu_def.py`. Если менять шапку или подвал, менять их надо на всех страницах,
включая `contact.html`: из него сборка новостей берёт оболочку.
