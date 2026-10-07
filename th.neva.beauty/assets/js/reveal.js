// Появления секций и карточек при входе во вьюпорт (fade-up, одноразово).
const SELECTOR = "[data-reveal], [data-reveal-children]";
const CHILDREN_ATTR = "data-reveal-children";
// Значение атрибута, с которым сетка раскрывается рядами, а не целиком.
const ROWS_MODE = "rows";
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
// Блок считается вошедшим, когда во вьюпорте его пятнадцатая с небольшим часть.
const THRESHOLD = 0.15;
// Наблюдатель смотрит на вьюпорт, укороченный снизу на 10% (rootMargin ниже).
const ROOT_SHARE = 0.9;
// Шаг каскада: каждая следующая карточка стартует на столько позже предыдущей.
const STAGGER_MS = 70;

function show(el, delayMs = 0) {
  if (delayMs) el.style.transitionDelay = `${delayMs}ms`;
  el.classList.add("is-visible");
}

function reveal(el) {
  if (!el.hasAttribute(CHILDREN_ATTR)) return show(el);
  [...el.children].forEach((child, index) => show(child, index * STAGGER_MS));
}

function revealBlocks(entries, observer) {
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    reveal(entry.target);
    observer.unobserve(entry.target);
  }
}

// Карточки одного ряда стоят на одной высоте и входят во вьюпорт одним пакетом,
// в порядке разметки. Каскад считается внутри ряда: первая карточка каждого ряда
// стартует сразу, а не ждёт своей очереди за всеми рядами выше.
function revealRows(entries, observer) {
  const shownInRow = new Map();
  for (const entry of entries) {
    if (!entry.isIntersecting) continue;
    const rowTop = Math.round(entry.boundingClientRect.top);
    const position = shownInRow.get(rowTop) ?? 0;
    shownInRow.set(rowTop, position + 1);
    show(entry.target, position * STAGGER_MS);
    observer.unobserve(entry.target);
  }
}

// Порог блочного наблюдателя задан долей самого блока, и чем блок выше, тем
// позже он появляется. Витрина товара на 1440 px — 2000 px высотой: её первый ряд
// оставался прозрачным, пока в экран не въезжало 380 px пустого места, а потом
// сетка раскрывалась целиком — с рядами за нижним краем и каскадом до 630 мс
// на карточку. На телефоне она выше 7000 px, и порог недостижим вовсе.
// Такие сетки наблюдаем по карточке: ряд появляется, как только показался его
// верхний край. Режим включается в разметке (data-reveal-children="rows") и сам —
// для любой сетки, которой порог недостижим. Остальные работают как работали.
function revealsByRows(el) {
  if (!el.hasAttribute(CHILDREN_ATTR)) return false;
  if (el.getAttribute(CHILDREN_ATTR) === ROWS_MODE) return true;
  return el.getBoundingClientRect().height * THRESHOLD > innerHeight * ROOT_SHARE;
}

function observe(el, blockObserver, rowObserver) {
  if (!revealsByRows(el)) return blockObserver.observe(el);
  for (const child of el.children) rowObserver.observe(child);
}

const targets = document.querySelectorAll(SELECTOR);

if (reduceMotion) {
  targets.forEach(reveal);
} else {
  const blockObserver = new IntersectionObserver(revealBlocks, {
    rootMargin: "0px 0px -10% 0px",
    threshold: THRESHOLD,
  });
  // Без порога и без укороченного вьюпорта: хватает первого пикселя карточки.
  const rowObserver = new IntersectionObserver(revealRows);
  targets.forEach((el) => observe(el, blockObserver, rowObserver));
}
