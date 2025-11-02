(() => {
  const DEFAULT_LABEL = '?????? ?????? ????????';
  const DEFAULT_ICON = '??';

  const ready = (fn) => {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn, { once: true });
    }
  };

  const ensureStyle = () => {
    if (document.getElementById('global-back-button-style')) {
      return;
    }

    const style = document.createElement('style');
    style.id = 'global-back-button-style';
    style.textContent = `
      .nav-back-button {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.35rem 0.9rem;
        border-radius: 999px;
        font-weight: 600;
        line-height: 1.2;
        text-decoration: none !important;
        transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease;
        border: 1px solid transparent;
        cursor: pointer;
      }

      .nav-back-button__icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 1rem;
        line-height: 1;
      }

      .nav-back-button__text {
        display: inline-flex;
        align-items: center;
        line-height: 1.2;
      }

      .nav-back-button:focus {
        outline: none;
        box-shadow: 0 0 0 0.2rem rgba(59, 130, 246, 0.25);
      }

      nav.navbar.navbar-dark .nav-back-button {
        color: #fff !important;
        border-color: rgba(255, 255, 255, 0.35);
        background-color: rgba(255, 255, 255, 0.08);
      }

      nav.navbar.navbar-dark .nav-back-button:hover {
        background-color: rgba(255, 255, 255, 0.18);
      }

      nav.navbar.navbar-light .nav-back-button {
        color: #0f172a !important;
        border-color: rgba(15, 23, 42, 0.15);
        background-color: rgba(255, 255, 255, 0.92);
        box-shadow: 0 4px 10px rgba(15, 23, 42, 0.08);
      }

      nav.navbar.navbar-light .nav-back-button:hover {
        background-color: #fff;
        border-color: rgba(15, 23, 42, 0.3);
      }

      .nav-back-button-wrapper {
        display: inline-flex;
        align-items: center;
        margin-inline-end: 0.75rem;
      }

      .nav-back-button-item {
        list-style: none;
        margin-inline: 0.25rem;
      }

      nav.sidebar .nav-back-button {
        width: 100%;
        justify-content: center;
        margin: 0.5rem 0;
        border: none;
        background: #ffb800;
        color: #1e1e2f !important;
        box-shadow: none;
      }

      nav.sidebar .nav-back-button:hover {
        background: #ffd464;
      }

      nav.sidebar .nav-back-button-item {
        margin: 0.25rem 1rem;
      }

      .global-back-button {
        position: fixed;
        top: 1.25rem;
        inset-inline-start: 1.25rem;
        z-index: 2147483000;
        pointer-events: none;
        display: flex;
      }

      .global-back-button__button {
        pointer-events: auto;
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.5rem 1rem;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.35);
        background: rgba(255, 255, 255, 0.92);
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.15);
        color: #0f172a;
        font-weight: 600;
        font-size: 1rem;
        transition: transform 0.15s ease, box-shadow 0.2s ease, background 0.2s ease;
        text-decoration: none;
      }

      .global-back-button__button:hover {
        transform: translateY(-1px);
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
        background: rgba(255, 255, 255, 0.98);
      }

      .global-back-button__button:active {
        transform: translateY(0);
        box-shadow: 0 6px 15px rgba(15, 23, 42, 0.18);
      }

      .global-back-button__icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 1.15rem;
        line-height: 1;
      }

      @media (max-width: 576px) {
        .global-back-button {
          top: 0.75rem;
          inset-inline-start: 0.75rem;
        }

        .global-back-button__button {
          padding: 0.45rem 0.85rem;
          gap: 0.3rem;
          font-size: 0.95rem;
        }
      }

      @media print {
        .global-back-button,
        .nav-back-button {
          display: none !important;
        }
      }
    `;

    document.head.appendChild(style);
  };

  const normalizePathname = (href) => {
    if (!href) {
      return null;
    }
    try {
      const url = new URL(href, window.location.origin);
      const pathname = url.pathname.endsWith('/') && url.pathname !== '/' ? url.pathname.slice(0, -1) : url.pathname;
      return pathname || '/';
    } catch (_err) {
      return href;
    }
  };

  const hasPagination = (nav) => !!(nav && nav.querySelector('.pagination'));

  const setAnchorContent = (anchor, label, icon) => {
    while (anchor.firstChild) {
      anchor.removeChild(anchor.firstChild);
    }

    const iconSpan = document.createElement('span');
    iconSpan.className = 'nav-back-button__icon';
    iconSpan.setAttribute('aria-hidden', 'true');
    iconSpan.textContent = icon;

    const textSpan = document.createElement('span');
    textSpan.className = 'nav-back-button__text';
    textSpan.textContent = label;

    anchor.append(iconSpan, textSpan);
  };

  const enhanceExistingAnchor = (anchor, label, icon) => {
    anchor.classList.add('nav-back-button');
    anchor.setAttribute('aria-label', label);
    anchor.setAttribute('title', label);
    anchor.dataset.globalBackButton = 'true';
    setAnchorContent(anchor, label, icon);
  };

  const createBackAnchor = (label, url, icon) => {
    const anchor = document.createElement('a');
    anchor.className = 'nav-back-button';
    anchor.href = url;
    anchor.setAttribute('role', 'button');
    anchor.setAttribute('aria-label', label);
    anchor.setAttribute('title', label);
    anchor.dataset.globalBackButton = 'true';
    setAnchorContent(anchor, label, icon);
    return anchor;
  };

  const attachToNav = (nav, label, url, icon) => {
    if (!nav || nav.dataset.backButtonInjected === 'true') {
      return false;
    }

    if (hasPagination(nav)) {
      return false;
    }

    const homePath = normalizePathname(url);

    if (homePath) {
      const anchors = Array.from(nav.querySelectorAll('a[href]'));
      const existing = anchors.find((a) => {
        const candidate = normalizePathname(a.getAttribute('href') || a.href);
        return candidate === homePath;
      });

      if (existing) {
        enhanceExistingAnchor(existing, label, icon);
        nav.dataset.backButtonInjected = 'true';
        return true;
      }
    }

    const anchor = createBackAnchor(label, url, icon);

    const placeholder = nav.querySelector('[data-back-button-anchor]');
    if (placeholder) {
      placeholder.appendChild(anchor);
      nav.dataset.backButtonInjected = 'true';
      return true;
    }

    const list = nav.querySelector('ul');
    if (list && list.tagName === 'UL' && !list.classList.contains('pagination')) {
      const listItem = document.createElement('li');
      listItem.className = 'nav-back-button-item';
      if (list.classList.contains('navbar-nav')) {
        listItem.classList.add('nav-item');
      }
      listItem.appendChild(anchor);
      list.insertBefore(listItem, list.firstElementChild);
      nav.dataset.backButtonInjected = 'true';
      return true;
    }

    const childContainer = Array.from(nav.children).find((child) => {
      if (!(child instanceof HTMLElement)) {
        return false;
      }
      if (child.classList && child.classList.contains('navbar-brand')) {
        return false;
      }
      return !!child.querySelector && !!child.querySelector('a');
    });

    if (childContainer && childContainer !== nav) {
      const wrapper = document.createElement('div');
      wrapper.className = 'nav-back-button-wrapper';
      wrapper.appendChild(anchor);
      childContainer.insertBefore(wrapper, childContainer.firstChild);
      nav.dataset.backButtonInjected = 'true';
      return true;
    }

    const wrapper = document.createElement('div');
    wrapper.className = 'nav-back-button-wrapper';
    wrapper.appendChild(anchor);
    nav.insertBefore(wrapper, nav.firstChild);
    nav.dataset.backButtonInjected = 'true';
    return true;
  };

  const ensureFloatingButton = (label, url, icon) => {
    const body = document.body || document.documentElement;
    if (!body) {
      return;
    }

    let container = document.querySelector('.global-back-button');
    let button;

    if (!container) {
      container = document.createElement('div');
      container.className = 'global-back-button';
      button = document.createElement('a');
      button.className = 'global-back-button__button';
      button.href = url;
      button.setAttribute('role', 'button');
      button.setAttribute('aria-label', label);
      button.title = label;

      const iconSpan = document.createElement('span');
      iconSpan.className = 'global-back-button__icon';
      iconSpan.setAttribute('aria-hidden', 'true');
      iconSpan.textContent = icon;

      const textSpan = document.createElement('span');
      textSpan.className = 'global-back-button__text';
      textSpan.textContent = label;

      button.append(iconSpan, textSpan);
      container.appendChild(button);
      body.appendChild(container);
      return;
    }

    button = container.querySelector('.global-back-button__button');
    if (!button) {
      button = document.createElement('a');
      button.className = 'global-back-button__button';
      container.appendChild(button);
    }

    button.href = url;
    button.setAttribute('role', 'button');
    button.setAttribute('aria-label', label);
    button.title = label;

    let iconSpan = button.querySelector('.global-back-button__icon');
    if (!iconSpan) {
      iconSpan = document.createElement('span');
      iconSpan.className = 'global-back-button__icon';
      iconSpan.setAttribute('aria-hidden', 'true');
      button.insertBefore(iconSpan, button.firstChild);
    }
    iconSpan.textContent = icon;

    let textSpan = button.querySelector('.global-back-button__text');
    if (!textSpan) {
      textSpan = document.createElement('span');
      textSpan.className = 'global-back-button__text';
      button.appendChild(textSpan);
    }
    textSpan.textContent = label;
  };

  ready(() => {
    const body = document.body || document.documentElement;
    if (!body) {
      return;
    }

    const toggle = (body.getAttribute('data-back-button') || 'on').toLowerCase();
    if (toggle === 'off') {
      return;
    }

    const url = body.getAttribute('data-back-button-fallback');
    if (!url) {
      return;
    }

    const label = (body.getAttribute('data-back-button-label') || '').trim() || DEFAULT_LABEL;
    const icon = (body.getAttribute('data-back-button-icon') || '').trim() || DEFAULT_ICON;

    ensureStyle();

    const navCandidates = Array.from(new Set([
      ...document.querySelectorAll('[data-back-button-target]'),
      ...document.querySelectorAll('nav.navbar'),
      ...document.querySelectorAll('nav.sidebar'),
      ...Array.from(document.querySelectorAll('body > nav')),
    ]));

    let injected = false;
    for (const nav of navCandidates) {
      if (!(nav instanceof HTMLElement)) {
        continue;
      }
      if (nav.dataset.backButtonTarget === 'ignore') {
        continue;
      }
      if (attachToNav(nav, label, url, icon)) {
        injected = true;
      }
    }

    if (!injected) {
      ensureFloatingButton(label, url, icon);
    } else {
      const floating = document.querySelector('.global-back-button');
      if (floating) {
        floating.remove();
      }
    }
  });
})();
