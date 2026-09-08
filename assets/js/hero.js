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
})();
