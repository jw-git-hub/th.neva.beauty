// price-tabs.js — переключение разделов прайс-листа
const KEY_STEP = { ArrowRight: 1, ArrowLeft: -1 };

function activateTab(tabs, panels, tab) {
  tabs.forEach(t => {
    const on = t === tab;
    t.classList.toggle('is-active', on);
    t.setAttribute('aria-selected', String(on));
    t.tabIndex = on ? 0 : -1;
  });
  panels.forEach(p => p.classList.toggle('is-active', p.dataset.panel === tab.dataset.tab));
}

// Внутри группы табов стрелки заменяют Tab: фокус ходит по кругу.
function focusStep(tabs, current, step) {
  const next = tabs[(tabs.indexOf(current) + step + tabs.length) % tabs.length];
  next.focus();
  return next;
}

function setupPricelist(pricelist) {
  const tabs = [...pricelist.querySelectorAll('.pricelist__tab')];
  const panels = [...pricelist.querySelectorAll('.pricelist__panel')];
  tabs.forEach(tab => {
    tab.addEventListener('click', () => activateTab(tabs, panels, tab));
    tab.addEventListener('keydown', event => {
      const step = KEY_STEP[event.key];
      if (!step) return;
      event.preventDefault();
      activateTab(tabs, panels, focusStep(tabs, tab, step));
    });
  });
}

document.querySelectorAll('[data-pricelist]').forEach(setupPricelist);
