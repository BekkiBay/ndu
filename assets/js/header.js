/* Шапка (из Макета 3): состояние после прокрутки, переключатель языка,
   мобильное меню.

   Обработчики висят на document, а элементы ищутся в момент события:
   скрипты базового шаблона (Helix / SP Page Builder) пересобирают часть DOM
   после загрузки, и прямые ссылки на элементы шапки устаревают. */
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };

  /* ---------- scrolled state ---------- */
  function onScroll() {
    var header = $('#siteHeader');
    if (!header) return;
    var y = window.scrollY || document.documentElement.scrollTop;
    header.classList.toggle('is-scrolled', y > 50);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('load', onScroll);
  document.addEventListener('DOMContentLoaded', onScroll);
  onScroll();

  /* ---------- mobile menu ---------- */
  function setMenu(open) {
    var mobileMenu = $('#mobileMenu');
    if (!mobileMenu) return;
    mobileMenu.classList.toggle('is-open', open);
    mobileMenu.setAttribute('aria-hidden', String(!open));
    document.body.classList.toggle('is-locked', open);
  }
  window.addEventListener('resize', function () { if (window.innerWidth >= 1024) setMenu(false); });

  /* ---------- clicks (delegated) ---------- */
  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t || !t.closest) return;

    var langBtn = t.closest('.lang__btn');
    var lang = $('#lang');
    if (langBtn && lang) {
      e.stopPropagation();
      var open = lang.classList.toggle('is-open');
      langBtn.setAttribute('aria-expanded', String(open));
      return;
    }
    /* Пункты меню — обычные ссылки на ту же страницу в /ru/ или /en/:
       достаточно закрыть список и не мешать переходу. */
    if (lang) lang.classList.remove('is-open');

    if (t.closest('#burgerBtn')) { setMenu(true); return; }
    if (t.closest('#mobileMenu [data-close]')) { setMenu(false); return; }

    var mmBtn = t.closest('#mobileMenu .mm__btn');
    if (mmBtn) {
      var expanded = mmBtn.getAttribute('aria-expanded') === 'true';
      mmBtn.setAttribute('aria-expanded', String(!expanded));
      return;
    }

    /* Заглушки вроде HEMIS не должны прыгать наверх страницы. */
    var stub = t.closest('a[href="#"]');
    if (stub && stub.closest('#siteHeader, #mobileMenu')) e.preventDefault();
  });
})();
