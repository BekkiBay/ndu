/* Видео-фон hero на главной (из Макета 3): при prefers-reduced-motion
   остаётся постер, вне экрана видео ставится на паузу. */
(function () {
  'use strict';
  var video = document.querySelector('.hero__video');
  if (!video) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    video.removeAttribute('autoplay');
    video.pause();
  } else if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) { video.play().catch(function () {}); }
      else { video.pause(); }
    }, { threshold: 0.05 }).observe(video);
  }

  /* ---------- «Yaqinlashayotgan tadbirlar»: появление карточек при прокрутке (Макет 2) ---------- */
  var reveals = Array.prototype.slice.call(document.querySelectorAll('.nd-events .reveal'));
  if (reveals.length && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('is-visible'); io.unobserve(en.target); } });
    }, { threshold: 0.15 });
    reveals.forEach(function (r) { io.observe(r); });
  } else {
    reveals.forEach(function (r) { r.classList.add('is-visible'); });
  }
})();
