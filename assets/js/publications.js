/* Ilmiy nashrlar: поиск и фильтры каталога, поиск по содержанию сборника,
   вкладки и копирование цитаты. Без скрипта страницы полностью читаются:
   видны все публикации и всё содержание. */
(function () {
  'use strict';

  /* Поиск не должен зависеть от алфавита и апострофов: узбекские заголовки
     бывают и кириллицей, и латиницей, а «o‘», «o'» и «o`» пишут вперемешку.
     Обе стороны сравнения сводятся к латинице без апострофов. */
  var CYR = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'ғ': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'j', 'з': 'z',
    'и': 'i', 'й': 'y', 'к': 'k', 'қ': 'q', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
    'с': 's', 'т': 't', 'у': 'u', 'ў': 'o', 'ф': 'f', 'х': 'x', 'ҳ': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh',
    'щ': 'sh', 'ъ': '', 'ы': 'i', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya', 'і': 'i', 'ә': 'a', 'ө': 'o',
    'ү': 'u', 'ұ': 'u', 'ң': 'ng', 'һ': 'h'
  };
  function norm(text) {
    var s = String(text || '').toLowerCase().replace(/[‘’ʻʼ`´'"“”«»]/g, '');
    var out = '';
    for (var i = 0; i < s.length; i++) {
      var c = s.charAt(i);
      out += Object.prototype.hasOwnProperty.call(CYR, c) ? CYR[c] : c;
    }
    return out.replace(/\s+/g, ' ').trim();
  }
  function tokens(query) {
    var q = norm(query);
    return q ? q.split(' ') : [];
  }
  function matches(haystack, words) {
    for (var i = 0; i < words.length; i++) {
      if (haystack.indexOf(words[i]) < 0) return false;
    }
    return true;
  }
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }
  function pluralForm(n, forms) {
    var lang = (document.documentElement.lang || 'uz').slice(0, 2);
    if (lang === 'ru') {
      if (n % 10 === 1 && n % 100 !== 11) return forms[0];
      if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14)) return forms[1];
      return forms[2];
    }
    return n === 1 ? forms[0] : forms[1];
  }

  /* ---------------------------------------------------------- catalogue */
  function initCatalog(root) {
    var input = root.querySelector('[data-pub-q]');
    var year = root.querySelector('[data-pub-year]');
    var chips = root.querySelectorAll('[data-pub-type]');
    var count = root.querySelector('[data-pub-count]');
    var empty = root.querySelector('[data-pub-empty]');
    var abbr = root.getAttribute('data-page-abbr') || '';
    var forms = (root.getAttribute('data-count-forms') || '').split('|');
    var index = {};
    try {
      var raw = root.querySelector('[data-pub-index]');
      if (raw) index = JSON.parse(raw.textContent);
    } catch (e) { index = {}; }

    var items = Array.prototype.map.call(root.querySelectorAll('[data-pub-item]'), function (node) {
      var slug = node.getAttribute('data-slug');
      return {
        node: node,
        type: node.getAttribute('data-type'),
        year: node.getAttribute('data-year'),
        text: norm(node.getAttribute('data-q')),
        hits: node.querySelector('[data-pub-hits]'),
        href: node.querySelector('.pub-item-title a').getAttribute('href'),
        toc: (index[slug] || []).map(function (e) {
          return { title: e[0], by: e[1], page: e[2], href: e[3], head: norm(e[0]), text: norm(e[0] + ' ' + e[1]) };
        })
      };
    });
    var type = '';

    var moreTpl = root.getAttribute('data-hits-more') || '+{n}';

    function renderHits(item, found, query) {
      var list = item.hits.querySelector('ul');
      list.textContent = '';
      found.slice(0, 5).forEach(function (e) {
        var li = el('li');
        var a = el('a', null, e.title);
        a.href = e.href;
        a.target = '_blank';
        a.rel = 'noopener';
        li.appendChild(a);
        li.appendChild(el('small', null, (e.by ? e.by + ' · ' : '') + abbr + ' ' + e.page));
        list.appendChild(li);
      });
      if (found.length > 5) {
        // Остальные совпадения — на странице сборника, где содержание
        // откроется уже отфильтрованным по тому же запросу.
        var li = el('li', 'pub-hits-more');
        var a = el('a', null, moreTpl.replace('{n}', found.length - 5));
        a.href = item.href + '?q=' + encodeURIComponent(query);
        li.appendChild(a);
        list.appendChild(li);
      }
      item.hits.hidden = !found.length;
    }

    function apply() {
      var words = tokens(input ? input.value : '');
      var y = year ? year.value : '';
      var shown = 0;
      items.forEach(function (item) {
        var ok = (!type || item.type === type) && (!y || item.year === y);
        var found = [];
        if (ok && words.length) {
          found = item.toc.filter(function (e) { return matches(e.text, words); });
          // Сначала статьи, где запрос в заголовке, потом — где он только
          // в подписи автора (например, в названии его вуза).
          found.sort(function (a, b) { return matches(b.head, words) - matches(a.head, words); });
          ok = matches(item.text, words) || found.length > 0;
        }
        item.node.hidden = !ok;
        renderHits(item, ok ? found : [], input ? input.value.trim() : '');
        if (ok) shown++;
      });
      if (count) count.textContent = shown + ' ' + pluralForm(shown, forms);
      if (empty) empty.hidden = shown > 0;
      try {
        var url = new URL(window.location.href);
        if (input && input.value.trim()) url.searchParams.set('q', input.value.trim());
        else url.searchParams.delete('q');
        window.history.replaceState(null, '', url);
      } catch (e) { /* file:// и старые браузеры */ }
    }

    Array.prototype.forEach.call(chips, function (chip) {
      chip.addEventListener('click', function () {
        type = chip.getAttribute('data-pub-type');
        Array.prototype.forEach.call(chips, function (c) {
          var on = c === chip;
          c.classList.toggle('is-active', on);
          c.setAttribute('aria-pressed', String(on));
        });
        apply();
      });
    });
    if (year) year.addEventListener('change', apply);
    if (input) {
      input.addEventListener('input', apply);
      try {
        var q = new URL(window.location.href).searchParams.get('q');
        if (q) { input.value = q; apply(); }
      } catch (e) { /* ignore */ }
    }
  }

  /* ---------------------------------------------------------- table of contents */
  function initToc(root) {
    var list = root.querySelector('.pub-toc-list');
    var input = root.querySelector('[data-pub-toc-q]');
    var empty = root.querySelector('[data-pub-toc-empty]');
    if (!list) return;
    var rows = Array.prototype.map.call(list.children, function (li) {
      return { node: li, text: norm(li.getAttribute('data-q')) };
    });
    var more = null;
    var LIMIT = 15;
    if (rows.length > LIMIT) {
      list.classList.add('is-collapsed');
      more = el('button', 'pub-toc-more', root.getAttribute('data-more'));
      more.type = 'button';
      more.setAttribute('aria-expanded', 'false');
      more.addEventListener('click', function () {
        var collapsed = list.classList.toggle('is-collapsed');
        more.textContent = root.getAttribute(collapsed ? 'data-more' : 'data-less');
        more.setAttribute('aria-expanded', String(!collapsed));
        if (collapsed) root.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      list.parentNode.insertBefore(more, list.nextSibling);
    }
    if (!input) return;
    input.addEventListener('input', filter);
    try {
      var q = new URL(window.location.href).searchParams.get('q');
      if (q) { input.value = q; filter(); }
    } catch (e) { /* ignore */ }

    function filter() {
      var words = tokens(input.value);
      var shown = 0;
      rows.forEach(function (row) {
        var ok = !words.length || matches(row.text, words);
        row.node.hidden = !ok;
        if (ok) shown++;
      });
      // Пока идёт поиск, показываем все совпадения, а не первые пятнадцать.
      if (more) {
        list.classList.toggle('is-collapsed', !words.length && more.getAttribute('aria-expanded') !== 'true');
        more.hidden = words.length > 0;
      }
      if (empty) empty.hidden = shown > 0;
    }
  }

  /* ---------------------------------------------------------- citation */
  function initCite(root) {
    var tabs = root.querySelectorAll('[data-pub-cite-tab]');
    var copy = root.querySelector('[data-pub-copy]');
    Array.prototype.forEach.call(tabs, function (tab) {
      tab.addEventListener('click', function () {
        Array.prototype.forEach.call(tabs, function (t) {
          var on = t === tab;
          t.setAttribute('aria-selected', String(on));
          var pane = document.getElementById(t.getAttribute('aria-controls'));
          if (pane) pane.hidden = !on;
        });
      });
    });
    if (!copy) return;
    var label = copy.textContent;
    copy.addEventListener('click', function () {
      var pane = root.querySelector('.pub-cite-text:not([hidden])');
      if (!pane) return;
      var text = pane.textContent.trim();
      var done = function () {
        copy.textContent = copy.getAttribute('data-done');
        setTimeout(function () { copy.textContent = label; }, 2000);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done, function () { fallback(pane, done); });
      } else {
        fallback(pane, done);
      }
    });
  }
  function fallback(pane, done) {
    var range = document.createRange();
    range.selectNodeContents(pane);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    try { if (document.execCommand('copy')) done(); } catch (e) { /* выделение остаётся — можно скопировать вручную */ }
  }

  function init() {
    var catalog = document.querySelector('[data-pub-catalog]');
    if (catalog) initCatalog(catalog);
    var toc = document.querySelector('[data-pub-toc]');
    if (toc) initToc(toc);
    var cite = document.querySelector('[data-pub-cite]');
    if (cite) initCite(cite);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
