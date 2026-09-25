# NDU — сайт Навоийского государственного университета

Итоговый проект; в него по кусочкам переезжают лучшие части остальных макетов
(Макет 2, Макет 3, Макет C).
Репозиторий: https://github.com/BekkiBay/ndu

Многостраничный статический сайт **Навоийского государственного университета
(NavDU)** на узбекском, русском и английском. Вёрстка, CSS, JS, шрифты и
компоненты — от базового шаблона (Joomla + Helix Ultimate + SP Page Builder),
контент — с [nsuz.uz](https://nsuz.uz/uz).

## Запуск

ES-модули (Bootstrap 5, Joomla core) не грузятся по `file://`, поэтому нужен
локальный HTTP-сервер:

```bash
cd NDU
python3 scripts/build_i18n.py   # собирает ru/ и en/ из узбекских страниц
python3 scripts/build_news.py   # генерирует новости для всех трёх языков
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

## Три языка

Сайт существует на узбекском, русском и английском. **Источник правды —
узбекские страницы в корне репозитория**; они правятся руками, а переводы
генерируются:

| Язык | Где лежит | Пример |
|---|---|---|
| O‘zbekcha | корень | `ndu.uz/about.html` |
| Русский | `ru/` | `ndu.uz/ru/about.html` |
| English | `en/` | `ndu.uz/en/about.html` |

`scripts/build_i18n.py` берёт каждую узбекскую страницу и кладёт её копию в
`ru/` и `en/`:

- текст, `<title>`, `<meta name="description">` и человекочитаемые атрибуты
  (`alt`, `title`, `placeholder`, `aria-label`) заменяются по словарю
  `content/i18n/ru.json` и `content/i18n/en.json` (ключ — узбекская строка);
- ссылки на общие файлы (`assets/`, `images/`, `media/`, `templates/`,
  `components/`, `views/`, `admin/`) получают префикс `../`, а ссылки на
  соседние страницы остаются относительными — в каждом каталоге лежит полный
  набор из 109 страниц;
- переписываются `<html lang>`, переключатель языка в шапке и блок
  `<link rel="alternate" hreflang>` между маркерами `<!-- i18n:alternate -->`.

Разметка не переформатируется: файл режется на токены и заменяются только
найденные отрезки, всё остальное переносится байт в байт (проверяется тестом
`tests/test_i18n.py`).

**Переключатель языка** (`.lang__menu` в шапке) — обычные ссылки на ту же
страницу в другом каталоге, поэтому он работает и без JavaScript. Активный
язык подсвечен, у кнопки — флаг (`assets/flag-uz.svg`, `flag-ru.svg`,
`flag-en.svg`).

### Как добавить или поправить перевод

```bash
python3 scripts/i18n_extract.py              # обновить каталог content/i18n/uz.json
python3 scripts/i18n_extract.py --missing ru # что ещё не переведено на русский
# дописать пары "узбекская строка": "перевод" в content/i18n/ru.json и en.json
python3 scripts/build_i18n.py && python3 scripts/build_news.py
```

Строки без перевода остаются узбекскими — сайт от этого не ломается. Числа,
телефоны и адреса почты в словарь не попадают.

`ru/` и `en/` — в `.gitignore`: их собирает CI, как и страницы новостей.

## Что где

```
index.html                      главная
ru/, en/                        переводы (генерируются, см. «Три языка»)
content/i18n/uz.json            каталог переводимых строк (для людей)
content/i18n/ru.json, en.json   словари переводов — источник правды
<раздел>-<подраздел>.html       внутренние страницы (плоские имена = относительные пути работают)
content/news.json               посты новостей — источник правды (правится админкой)
images/nsu/news/<slug>/         фотографии поста, загруженные через админку
admin/                          админка новостей (см. «Новости и админка»)
scripts/i18n.py                 разбор и перезапись HTML: подмена строк, перенос ссылок
scripts/build_i18n.py           собирает ru/ и en/ из узбекских страниц
scripts/i18n_extract.py         каталог переводимых строк и отчёт о пропусках
scripts/build_news.py           генерирует news.html, news-*.html и карусель — на всех языках
deploy/counter/counter.py       сервис счётчика просмотров (контейнер ndu-counter)
tests/                          юнит-тесты сборки и счётчика (python3 -m unittest discover -s tests)
assets/css/nsu.css              стили контентных блоков NavDU (палитра/шрифты шаблона)
images/nsu/                     фотографии и логотип NavDU
templates/lt_university/        базовый шаблон: CSS, JS, шрифты
components/com_sppagebuilder/   SP Page Builder: слайдеры, аддоны
media/                          Joomla core, Bootstrap 5, jQuery, ConvertForms
```

## Новости и админка

Новости не лежат в репозитории готовыми страницами. Источник правды —
`content/news.json`: массив постов с полями `slug`, `title`, `date`
(`YYYY-MM-DD` или `null`), `excerpt`, `cover`, `body` (HTML из редактора),
`gallery`, `updated`. Переводы поста лежат рядом, в полях с суффиксом языка:
`title_ru`, `excerpt_ru`, `body_ru`, `title_en`, `excerpt_en`, `body_en`.
Пустого или отсутствующего поля достаточно: на этом языке покажется
узбекский оригинал. Из `news.json` `scripts/build_news.py` генерирует — для
каждого языка, у которого уже собрана оболочка (`<lang>/contact.html`):

- `news-<slug>.html` — страницу каждого поста (оболочка берётся из
  `contact.html`, поэтому шапка и подвал новостей всегда совпадают с сайтом);
- `news.html` — список карточек, сначала посты с датой (новые выше), потом без;
- блок между маркерами `<!-- news:carousel -->` и `<!-- /news:carousel -->` в
  `index.html` — карусель из шести последних постов.

Пост с полем `"section": "kelajakka-qadam"` уходит из «Yangiliklar» и карусели
на страницу своего раздела `kelajakka-qadam.html` («Kelajakka qadam dasturi»,
отдельный пункт главного меню). Разделы описаны в `SECTIONS` в
`scripts/build_news.py`; страница раздела тоже генерируется и лежит в
`build_i18n.GENERATED_PAGES`. Админка поле `section` не показывает, но при
правке поста сохраняет.

`news.html` и `news-*.html` в `.gitignore`: CI собирает их перед проверками и
деплоем, локально — команда из раздела «Запуск». `index.html` остаётся в git,
сборка правит в нём только блок между маркерами. Запускать `build_news.py`
надо **после** `build_i18n.py`: оболочку для `ru/` и `en/` он берёт из
`ru/contact.html` и `en/contact.html`.

**Админка** — `https://ndu.uz/admin/`. Создание, редактирование и удаление
постов, текст в визуальном редакторе (Quill), обложка, фото в тексте и галерея.

Над полями поста — вкладки **O‘zbekcha · Русский · English**. Заголовок, анонс
и текст у каждого языка свои, а дата, slug, обложка и галерея — общие.
Обязателен только узбекский заголовок: он оригинал. Пустой перевод не
сохраняется в `news.json`, и страница на этом языке показывает узбекский текст.
Фото, вставленное только в перевод, тоже загружается и не считается лишним
(`referenced_images` в `deploy/api/api.py` смотрит во все три версии текста).

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
  из шаблона заменена на плитки с названиями партнёров и странами.
- Видео-фон первого слайда — `images/nsu/video/hero.mp4` (1.2 МБ, 12 с, съёмка
  того же читального зала, что и на фото слайда), взято из `Макет 2`.

- Из базового шаблона удалены: виджет доступности Joomla (иконка инвалидной коляски,
  `media/vendor/accessibility/js/accessibility.min.js` + его инициализация) и
  видео-фон второго слайда hero (`<div class="sp-video-background">` с чужим
  YouTube-роликом — именно он давал белый «пустой» слайд при перелистывании).
- Следов чужого бренда в отдаваемых файлах не осталось (2026-09-18): соцсети
  (`og:url`, `og:site_name`, `og:image`, `og:locale`, `twitter:site`,
  `twitter:image`) указывают на NavDU, пути Joomla в конфиге страницы — на
  `https://ndu.uz/`, три внешние ссылки с главной ведут на свои страницы
  (`faculties.html`, `about-partnerships-erasmus.html`, `about-jobs.html`),
  а мёртвый скрипт капитализации меню (он работал по удалённому
  `.offcanvas-menu`) убран. Файл со стилями шаблона называется
  `assets/css/template-inline.css`, его класс — `.nsu-bg-col`.

## Проверено

- 0 битых внутренних ссылок и 0 битых ссылок на ресурсы (109 страниц × 3 языка).
- 0 HTTP-404 при загрузке страниц в браузере.
- Нет горизонтального переполнения на 320/375/414/768/1024/1280/1440/1920 px.
- Мобильное off-canvas меню и десктопное мега-меню собраны заново под структуру NavDU.
- Слайдеры (hero, новости, талабалик хаёти, партнёры) и анимации работают.


## Деплой

Живая версия: **http://185.217.199.92:8083** (сервер Hermes) и копия на
**https://bekkibay.github.io/ndu/**.

CI/CD — `.github/workflows/`: `ci.yml` гоняет юнит-тесты, проверяет штампы
`?v=`, собирает переводы и новости и проверяет, что все внутренние ссылки и
ресурсы резолвятся во всех трёх языковых деревьях; `deploy.yml` после успешной
проверки раскатывает сайт на Hermes (rsync без `--delete`; единственное
исключение — страницы удалённых новостей `news-*.html`, в том числе в `ru/` и
`en/`) и на GitHub Pages, поднимает контейнер счётчика. Рядом с `api.py` на
сервер кладутся `build_news.py`, `build_i18n.py` и `i18n.py` — генератор
импортирует их, когда админка пересобирает страницы. Подробности и
первичная настройка сервера — в [`deploy/README.md`](deploy/README.md).

## Как пересобрать

Переводы собираются `scripts/build_i18n.py`, новости — `scripts/build_news.py`
(именно в таком порядке, см. выше).
Остальной сайт генерировался скриптами, которые лежат вне репозитория, в
рабочей папке сессии: `site_data.py` (парсинг nsuz.uz) → `build.py`
(внутренние страницы) → `gen_home.py` (главная). Шапка/подвал/меню собираются
в `shell.py`, контентные блоки — в `render.py`, структура меню — в
`menu_def.py`. Если менять шапку или подвал, менять их надо на всех страницах,
включая `contact.html`: из него сборка новостей берёт оболочку.
