// Появления секций и карточек при входе во вьюпорт (fade-up, одноразово).
const SELECTOR = "[data-reveal], [data-reveal-children]";
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
// Блок считается вошедшим, когда во вьюпорте его пятнадцатая с небольшим часть.
const THRESHOLD = 0.15;
// Наблюдатель смотрит на вьюпорт, укороченный снизу на 10% (rootMargin ниже).
const ROOT_SHARE = 0.9;

function reveal(el) {
  if (el.hasAttribute("data-reveal-children")) {
    [...el.children].forEach((child, i) => {
      child.style.transitionDelay = `${i * 70}ms`;
      child.classList.add("is-visible");
    });
  } else {
    el.classList.add("is-visible");
  }
}

const targets = document.querySelectorAll(SELECTOR);

if (reduceMotion) {
  targets.forEach(reveal);
} else {
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        reveal(entry.target);
        observer.unobserve(entry.target);
      }
    },
    { rootMargin: "0px 0px -10% 0px", threshold: THRESHOLD }
  );
  targets.forEach((el) => observe(el, observer));
}

// Порог задан долей самого блока, и блоку выше экрана он недостижим: витрина
// товара в одну колонку на телефоне выше 7000 px, её пятнадцатая часть не влезает
// во вьюпорт целиком — сетка не раскрывалась вообще, все карточки оставались
// прозрачными. Такой блок наблюдаем не целиком, а по карточке: каждая следит
// за собой и появляется, когда доходит очередь. Блоки, которым порог достижим
// (все остальные сетки сайта), работают как работали — их поведение не трогаем.
function observe(el, observer) {
  const height = el.getBoundingClientRect().height;
  const unreachable = height * THRESHOLD > innerHeight * ROOT_SHARE;
  if (unreachable && el.hasAttribute("data-reveal-children")) {
    for (const child of el.children) observer.observe(child);
    return;
  }
  observer.observe(el);
}
