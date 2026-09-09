// slugify(title) -> URL slug matching SLUG_RE in scripts/build_news.py.
// Uzbek Latin apostrophes are dropped (oʻquv -> oquv); Cyrillic is transliterated
// so a Russian or Uzbek-Cyrillic title still yields a usable slug.
const APOSTROPHES = /[ʻʼ’‘'`´ʹ]/g;
const CYR = {
  а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'yo', ж: 'j', з: 'z', и: 'i', й: 'y', к: 'k',
  л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u', ф: 'f', х: 'x', ц: 'ts',
  ч: 'ch', ш: 'sh', щ: 'sh', ъ: '', ы: 'i', ь: '', э: 'e', ю: 'yu', я: 'ya',
  ў: 'o', қ: 'q', ғ: 'g', ҳ: 'h',
};
export const SLUG_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;
export const SLUG_MAX = 80;

export function slugify(title) {
  let s = (title || '').toLowerCase().replace(APOSTROPHES, '');
  s = s.replace(/[а-яёўқғҳ]/g, (ch) => CYR[ch] ?? '');
  s = s.normalize('NFKD').replace(/[̀-ͯ]/g, '');
  s = s.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  if (s.length > SLUG_MAX) s = s.slice(0, SLUG_MAX).replace(/-+$/g, '');
  return s;
}

export function isValidSlug(s) {
  return typeof s === 'string' && s.length <= SLUG_MAX && SLUG_RE.test(s);
}
