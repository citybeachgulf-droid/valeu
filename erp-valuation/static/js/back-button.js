(() => {
  const ICON_SYMBOL = '\u21A9';
  const DEFAULT_LABEL = '\u0631\u062c\u0648\u0639';

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
        cursor: pointer;
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
        .global-back-button {
          display: none !important;
        }
      }
    `;

    document.head.appendChild(style);
  };

  const getBody = () => document.body || document.documentElement;

  const attachHandler = (button) => {
    if (!button || button.dataset.backBound === 'true') {
      return;
    }

    button.dataset.backBound = 'true';

    button.addEventListener('click', (event) => {
      event.preventDefault();

      const body = getBody();
      const fallback = body ? body.getAttribute('data-back-button-fallback') : null;

      const referrer = document.referrer;
      if (referrer) {
        try {
          const refUrl = new URL(referrer, window.location.href);
          if (
            refUrl.origin === window.location.origin &&
            refUrl.href !== window.location.href
          ) {
            window.location.href = refUrl.href;
            return;
          }
        } catch (_err) {
          /* ignore invalid URLs */
        }
      }

      if (window.history.length > 1) {
        window.history.back();
        return;
      }

      if (fallback) {
        window.location.href = fallback;
      }
    });
  };

  const ensureButton = () => {
    const body = getBody();
    if (!body) {
      return;
    }

    const toggle = (body.getAttribute('data-back-button') || 'on').toLowerCase();
    if (toggle === 'off') {
      return;
    }

    let container = document.querySelector('.global-back-button');
    if (!container) {
      container = document.createElement('div');
      container.className = 'global-back-button';

      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'global-back-button__button';

      const icon = document.createElement('span');
      icon.className = 'global-back-button__icon';
      icon.setAttribute('aria-hidden', 'true');
      icon.textContent = ICON_SYMBOL;

      const labelText = body.getAttribute('data-back-button-label') || DEFAULT_LABEL;

      const label = document.createElement('span');
      label.className = 'global-back-button__text';
      label.textContent = labelText;

      button.setAttribute('aria-label', labelText);
      button.append(icon, label);
      container.appendChild(button);
      body.appendChild(container);

      attachHandler(button);
      return;
    }

    const existingButton = container.querySelector('button');
    if (existingButton) {
      const labelText = body.getAttribute('data-back-button-label') || DEFAULT_LABEL;
      existingButton.setAttribute('aria-label', labelText);

      const textNode = existingButton.querySelector('.global-back-button__text');
      if (textNode) {
        textNode.textContent = labelText;
      } else {
        const label = document.createElement('span');
        label.className = 'global-back-button__text';
        label.textContent = labelText;
        existingButton.appendChild(label);
      }

      attachHandler(existingButton);
    }
  };

  ready(() => {
    ensureStyle();
    ensureButton();
  });
})();
