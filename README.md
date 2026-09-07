# Макет WIUT — сайт NavDU в дизайне wiut.uz

Многостраничный статический сайт **Навоийского государственного университета
(NavDU)**, собранный в дизайне [wiut.uz](https://www.wiut.uz/): вёрстка, CSS, JS,
шрифты и компоненты взяты у оригинального шаблона (Joomla + Helix Ultimate +
SP Page Builder), а весь контент — с [nsuz.uz](https://nsuz.uz/uz).

## Запуск

ES-модули (Bootstrap 5, Joomla core) не грузятся по `file://`, поэтому нужен
локальный HTTP-сервер:

```bash
cd "Макет WIUT"
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
| Новости | 12 | `news.html` + 11 новостей |
| Прочее | 2 | `contact.html`, `brosdcast.html` |

Все ссылки внутри сайта рабочие (проверено: 0 битых), формы — заглушки
(`onsubmit="return false"`), кнопка «Hujjat topshirish» ведёт на `qabul.nsu.uz`.

## Что где

```
index.html                      главная (дизайн главной wiut.uz, контент NavDU)
<раздел>-<подраздел>.html       внутренние страницы (плоские имена = относительные пути работают)
assets/css/nsu.css              стили контентных блоков NavDU (палитра/шрифты WIUT)
images/nsu/                     фотографии и логотип NavDU
templates/lt_university/        шаблон WIUT: CSS, JS, шрифты
components/com_sppagebuilder/   SP Page Builder: слайдеры, аддоны
media/                          Joomla core, Bootstrap 5, jQuery, ConvertForms
```

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

Живая версия: **http://185.217.199.92:8081** (сервер Hermes) и копия на
**https://bekkibay.github.io/wuit_navoiyliklar/**.

CI/CD — `.github/workflows/`: `ci.yml` проверяет, что все внутренние ссылки и
ресурсы резолвятся, `deploy.yml` после успешной проверки раскатывает сайт на
Hermes (rsync без `--delete`) и на GitHub Pages. Подробности и первичная
настройка сервера — в [`deploy/README.md`](deploy/README.md).

## Как пересобрать

Сайт генерируется скриптами (лежат вне репозитория, в рабочей папке сессии):
`site_data.py` (парсинг nsuz.uz) → `build.py` (внутренние страницы) →
`gen_home.py` (главная). Шапка/подвал/меню собираются в `shell.py`, контентные
блоки — в `render.py`, структура меню — в `menu_def.py`.
