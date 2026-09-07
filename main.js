(() => {
  'use strict';
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const header = document.querySelector('#site-header');
  const hero = document.querySelector('.hero');
  const video = document.querySelector('#hero-video');
  const videoControl = document.querySelector('#video-control');
  const dialog = document.querySelector('#campus-dialog');
  const dialogVideo = dialog.querySelector('video');
  const menuToggle = document.querySelector('.mobile-toggle');
  const mobileNav = document.querySelector('#mobile-nav');
  let userPaused = reducedMotion.matches;
  let heroVisible = true;

  function updateVideoControl() {
    const paused = video.paused;
    videoControl.setAttribute('aria-pressed', String(paused));
    videoControl.setAttribute('aria-label', paused ? 'Fon videosini davom ettirish' : 'Fon videosini to‘xtatish');
    videoControl.querySelector('use').setAttribute('href', paused ? '#i-play' : '#i-pause');
  }

  function syncVideo() {
    if (userPaused || !heroVisible || document.hidden || dialog.open) {
      video.pause();
    } else {
      video.play().catch(updateVideoControl);
    }
  }

  video.addEventListener('play', updateVideoControl);
  video.addEventListener('pause', updateVideoControl);
  videoControl.addEventListener('click', () => {
    userPaused = !video.paused;
    syncVideo();
  });
  document.addEventListener('visibilitychange', syncVideo);
  reducedMotion.addEventListener('change', () => {
    userPaused = reducedMotion.matches;
    syncVideo();
  });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(([entry]) => {
      heroVisible = entry.isIntersecting;
      syncVideo();
    }, { threshold: 0 }).observe(hero);
  }
  syncVideo();
  updateVideoControl();

  function updateHeader() {
    header.classList.toggle('scrolled', window.scrollY > 56);
  }
  window.addEventListener('scroll', updateHeader, { passive: true });
  updateHeader();

  function closeMenu() {
    mobileNav.hidden = true;
    menuToggle.setAttribute('aria-expanded', 'false');
    menuToggle.setAttribute('aria-label', 'Menyuni ochish');
    menuToggle.querySelector('use').setAttribute('href', '#i-menu');
  }
  menuToggle.addEventListener('click', () => {
    const willOpen = mobileNav.hidden;
    mobileNav.hidden = !willOpen;
    menuToggle.setAttribute('aria-expanded', String(willOpen));
    menuToggle.setAttribute('aria-label', willOpen ? 'Menyuni yopish' : 'Menyuni ochish');
    menuToggle.querySelector('use').setAttribute('href', willOpen ? '#i-close' : '#i-menu');
  });
  mobileNav.addEventListener('click', event => {
    if (event.target.closest('a')) closeMenu();
  });
  window.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !mobileNav.hidden) {
      closeMenu();
      menuToggle.focus();
    }
  });
  window.matchMedia('(min-width: 801px)').addEventListener('change', event => {
    if (event.matches) closeMenu();
  });

  document.querySelectorAll('[data-open-video]').forEach(button => {
    button.addEventListener('click', () => {
      dialog.showModal();
      video.pause();
      dialogVideo.currentTime = 0;
      dialogVideo.play().catch(() => {});
    });
  });
  document.querySelector('#close-dialog').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => {
    const rect = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
  });
  dialog.addEventListener('close', () => {
    dialogVideo.pause();
    syncVideo();
  });

  if (!reducedMotion.matches && 'IntersectionObserver' in window) {
    const revealObserver = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    }, { threshold: 0.06, rootMargin: '0px 0px 0px 0px' });
    document.querySelectorAll('.reveal').forEach(element => revealObserver.observe(element));
    document.body.classList.add('motion-ready');

    const countObserver = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const element = entry.target;
        countObserver.unobserve(element);
        const target = Number(element.dataset.count);
        const suffix = element.dataset.suffix || '';
        const start = performance.now();
        function tick(now) {
          const progress = Math.min(1, (now - start) / 1150);
          const value = Math.round(target * (1 - Math.pow(1 - progress, 3)));
          element.textContent = value.toLocaleString('fr-FR');
          if (suffix) {
            const span = document.createElement('span');
            span.textContent = suffix;
            element.append(span);
          }
          if (progress < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
      }
    }, { threshold: 0.5 });
    document.querySelectorAll('[data-count]').forEach(element => countObserver.observe(element));
  }
})();
