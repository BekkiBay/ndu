/* NavDU (nsuz.uz) — поведение интерфейса. Дизайн-система из копии udea.uz. */
(function () {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  /* ---------- header: scrolled state + scroll-to-top progress ---------- */
  const header = $('#siteHeader');
  const toTop = $('#toTop');
  function onScroll() {
    const y = window.scrollY || document.documentElement.scrollTop;
    header.classList.toggle('is-scrolled', y > 50);
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const p = max > 0 ? Math.min(100, Math.round((y / max) * 100)) : 0;
    toTop.style.setProperty('--progress', p + '%');
    toTop.classList.toggle('is-visible', y > 300);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  toTop.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

  /* ---------- герой: фоновое видео ---------- */
  const heroVideo = $('.hero__video');
  if (heroVideo) {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      // Движущийся фон отключён — остаётся постер.
      heroVideo.removeAttribute('autoplay');
      heroVideo.pause();
    } else if ('IntersectionObserver' in window) {
      // Не крутим видео, пока герой прокручен за пределы экрана.
      new IntersectionObserver(([e]) => {
        if (e.isIntersecting) heroVideo.play().catch(() => {});
        else heroVideo.pause();
      }, { threshold: 0.05 }).observe(heroVideo);
    }
  }

  /* ---------- language switcher (заглушка) ---------- */
  const lang = $('#lang');
  const langBtn = $('.lang__btn', lang);
  langBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = lang.classList.toggle('is-open');
    langBtn.setAttribute('aria-expanded', String(open));
  });
  $$('.lang__menu button', lang).forEach((b) => {
    b.addEventListener('click', () => {
      $$('.lang__menu button', lang).forEach((x) => x.classList.remove('is-active'));
      b.classList.add('is-active');
      $('.lang__label', lang).textContent = b.dataset.label;
      lang.classList.remove('is-open');
    });
  });
  document.addEventListener('click', () => lang.classList.remove('is-open'));

  /* ---------- mobile menu ---------- */
  const mobileMenu = $('#mobileMenu');
  const burger = $('#burgerBtn');
  function openMenu() {
    mobileMenu.classList.add('is-open');
    mobileMenu.setAttribute('aria-hidden', 'false');
    document.body.classList.add('is-locked');
  }
  function closeMenu() {
    mobileMenu.classList.remove('is-open');
    mobileMenu.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('is-locked');
  }
  burger.addEventListener('click', openMenu);
  $$('[data-close]', mobileMenu).forEach((el) => el.addEventListener('click', closeMenu));
  $$('.mm__btn', mobileMenu).forEach((btn) => {
    btn.addEventListener('click', () => {
      const expanded = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', String(!expanded));
    });
  });
  window.addEventListener('resize', () => { if (window.innerWidth >= 1024) closeMenu(); });

  /* ---------- count-up статистика ---------- */
  function countUp(el) {
    const target = parseFloat(el.dataset.target);
    const suffix = el.dataset.suffix || '';
    const duration = 1600;
    const start = performance.now();
    function frame(now) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(target * eased) + suffix;
      if (t < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  const statObserver = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (en.isIntersecting) { countUp(en.target); statObserver.unobserve(en.target); }
    });
  }, { threshold: .4 });
  $$('[data-target]').forEach((el) => statObserver.observe(el));

  /* ---------- reveal on scroll ---------- */
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (en.isIntersecting) { en.target.classList.add('in'); revealObserver.unobserve(en.target); }
    });
  }, { threshold: .08 });
  $$('.reveal').forEach((el) => revealObserver.observe(el));

  /* ---------- why-choose accordion ---------- */
  const accItems = $$('.acc__item');
  accItems.forEach((item) => {
    $('.acc__btn', item).addEventListener('click', () => {
      const isOpen = item.classList.contains('is-open');
      accItems.forEach((i) => i.classList.remove('is-open'));
      if (!isOpen) item.classList.add('is-open');
    });
  });

  /* ---------- ленты карточек (scroll-snap) ---------- */
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function makeStrip(root) {
    const track = $('.strip__track', root);
    const items = Array.from(track.children);
    const bar = $('.strip__bar i', root);
    const count = $('.strip__count b', root);
    if (!items.length) return;

    const step = () => (items[1] ? items[1].offsetLeft - items[0].offsetLeft : track.clientWidth);
    const maxScroll = () => Math.max(0, track.scrollWidth - track.clientWidth);

    function paint() {
      const max = maxScroll();
      const i = Math.min(items.length - 1, Math.round(track.scrollLeft / step()));
      if (count) count.textContent = String(i + 1).padStart(2, '0');
      if (bar) {
        bar.style.width = (track.clientWidth / track.scrollWidth * 100) + '%';
        bar.style.left = (max ? track.scrollLeft / track.scrollWidth * 100 : 0) + '%';
      }
    }
    function go(dir) {
      const max = maxScroll();
      let x = track.scrollLeft + dir * step();
      if (x > max + 2) x = 0;          // с конца — в начало
      else if (x < -2) x = max;        // с начала — в конец
      track.scrollTo({ left: x, behavior: reduceMotion ? 'auto' : 'smooth' });
    }

    $('.strip__btn--prev', root).addEventListener('click', () => { go(-1); restart(); });
    $('.strip__btn--next', root).addEventListener('click', () => { go(1); restart(); });
    track.addEventListener('scroll', paint, { passive: true });

    // автопрокрутка: пауза при наведении, касании и вне экрана
    const interval = reduceMotion ? 0 : parseInt(root.dataset.autoplay || '0', 10);
    let timer = null;
    let visible = true;
    function stop() { clearInterval(timer); timer = null; }
    function restart() {
      stop();
      if (interval && visible) timer = setInterval(() => go(1), interval);
    }
    root.addEventListener('mouseenter', stop);
    root.addEventListener('mouseleave', restart);
    track.addEventListener('pointerdown', stop);
    track.addEventListener('pointerup', restart);
    if ('IntersectionObserver' in window && interval) {
      new IntersectionObserver(([e]) => { visible = e.isIntersecting; restart(); }, { threshold: .2 }).observe(root);
    } else {
      restart();
    }

    window.addEventListener('resize', paint);
    window.addEventListener('load', paint);
    paint();
  }
  $$('.strip').forEach(makeStrip);

  /* ---------- testimonials (один слайд, точки) ---------- */
  const testiTrack = $('.testi__track');
  if (testiTrack) {
    const slides = Array.from(testiTrack.children);
    const dots = $$('.dots .dot');
    let cur = 0;
    function show(n) {
      cur = (n + slides.length) % slides.length;
      testiTrack.style.transform = 'translateX(-' + cur * 100 + '%)';
      dots.forEach((d, i) => d.classList.toggle('is-active', i === cur));
    }
    dots.forEach((d, i) => d.addEventListener('click', () => show(i)));
    let sx = null;
    const vp = $('.testi__viewport');
    vp.addEventListener('pointerdown', (e) => { sx = e.clientX; });
    vp.addEventListener('pointerup', (e) => {
      if (sx === null) return;
      const d = e.clientX - sx;
      if (d < -40) show(cur + 1); else if (d > 40) show(cur - 1);
      sx = null;
    });
    show(0);
  }

  /* ---------- grant popup + countdown ---------- */
  const modal = $('#grantModal');
  if (modal) {
    const deadline = new Date(modal.dataset.deadline || '2026-09-08T23:59:00+05:00').getTime();
    const cells = { d: $('[data-t="d"]', modal), h: $('[data-t="h"]', modal), m: $('[data-t="m"]', modal), s: $('[data-t="s"]', modal) };
    const hasTimer = !!(cells.d && cells.h && cells.m && cells.s);
    const pad = (n) => String(n).padStart(2, '0');
    function tick() {
      if (!hasTimer) return;
      let diff = Math.max(0, deadline - Date.now());
      const d = Math.floor(diff / 864e5); diff -= d * 864e5;
      const h = Math.floor(diff / 36e5); diff -= h * 36e5;
      const m = Math.floor(diff / 6e4); diff -= m * 6e4;
      const s = Math.floor(diff / 1e3);
      cells.d.textContent = pad(d); cells.h.textContent = pad(h); cells.m.textContent = pad(m); cells.s.textContent = pad(s);
    }
    tick();
    const clock = hasTimer ? setInterval(tick, 1000) : 0;
    function closeModal() {
      modal.classList.remove('is-open');
      document.body.classList.remove('is-locked');
      clearInterval(clock);
    }
    $$('[data-modal-close]', modal).forEach((el) => el.addEventListener('click', closeModal));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
    setTimeout(() => {
      modal.classList.add('is-open');
      document.body.classList.add('is-locked');
    }, 900);
  }

  /* ---------- пустые ссылки: не прыгать наверх ---------- */
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a[href="#"]');
    if (a) e.preventDefault();
  });
})();
