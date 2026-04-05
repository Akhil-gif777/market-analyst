// transitions.js — Animation helpers using Motion library (global `Motion` from CDN)
// Falls back gracefully if Motion is unavailable.

const M = window.Motion;

/**
 * Animate the tab indicator to slide under the active tab.
 */
export function moveTabIndicator(indicator, tab) {
  if (!indicator || !tab) return;
  const rect = tab.getBoundingClientRect();
  const parentRect = tab.parentElement.getBoundingClientRect();
  const left = rect.left - parentRect.left;
  const width = rect.width;

  if (M && M.animate) {
    M.animate(indicator, { left: `${left}px`, width: `${width}px` }, {
      duration: 0.35,
      easing: M.spring ? M.spring(0.35) : 'ease-out',
    });
  } else {
    indicator.style.left = `${left}px`;
    indicator.style.width = `${width}px`;
  }
}

/**
 * Animate a panel entering (fade in + slide up).
 */
export function animatePanelIn(panel) {
  if (!panel) return;
  if (M && M.animate) {
    M.animate(panel,
      { opacity: [0, 1], transform: ['translateY(12px)', 'translateY(0)'] },
      { duration: 0.3, easing: M.spring ? M.spring(0.3) : 'ease-out' }
    );
  }
}

/**
 * Animate a number counting from old value to new value.
 */
export function animateNumber(el, from, to, opts = {}) {
  const { prefix = '', suffix = '', decimals = 2, duration = 0.4 } = opts;

  const format = (val) => `${prefix}${val.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}${suffix}`;

  if (!M || !M.animate || from === to) {
    el.textContent = format(to);
    return;
  }

  const obj = { val: from };
  M.animate(obj, { val: to }, {
    duration,
    easing: M.spring ? M.spring(0.4) : 'ease-out',
    onUpdate: () => {
      el.textContent = format(obj.val);
    },
  });

  // Flash color based on direction
  if (to > from) {
    el.classList.add('value-flash-green');
    setTimeout(() => el.classList.remove('value-flash-green'), 600);
  } else if (to < from) {
    el.classList.add('value-flash-red');
    setTimeout(() => el.classList.remove('value-flash-red'), 600);
  }
}

/**
 * Apply staggered fade-in to elements.
 */
export function staggerIn(elements, delayMs = 30) {
  if (!elements || !elements.length) return;

  for (let i = 0; i < elements.length; i++) {
    const el = elements[i];
    el.style.opacity = '0';
    el.style.transform = 'translateY(8px)';

    if (M && M.animate) {
      M.animate(el,
        { opacity: [0, 1], transform: ['translateY(8px)', 'translateY(0)'] },
        { delay: i * (delayMs / 1000), duration: 0.3, easing: 'ease-out' }
      );
    } else {
      setTimeout(() => {
        el.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        el.style.opacity = '1';
        el.style.transform = 'translateY(0)';
      }, i * delayMs);
    }
  }
}

/**
 * Animate a score bar filling from 0 to the given percentage.
 */
export function animateScoreBar(fillEl, pct) {
  if (!fillEl) return;
  fillEl.style.width = '0%';

  if (M && M.animate) {
    M.animate(fillEl, { width: `${pct}%` }, {
      duration: 0.6,
      easing: M.spring ? M.spring(0.6) : 'ease-out',
    });
  } else {
    setTimeout(() => {
      fillEl.style.transition = 'width 0.6s ease';
      fillEl.style.width = `${pct}%`;
    }, 50);
  }
}

/**
 * Animate expand/collapse of an element's height.
 */
export function animateExpand(el, open) {
  if (!el) return;

  if (open) {
    el.style.display = 'block';
    const height = el.scrollHeight;
    el.style.height = '0px';
    el.style.overflow = 'hidden';

    if (M && M.animate) {
      M.animate(el, { height: `${height}px`, opacity: [0, 1] }, {
        duration: 0.35,
        easing: M.spring ? M.spring(0.3) : 'ease-out',
      }).then(() => { el.style.height = 'auto'; el.style.overflow = ''; });
    } else {
      el.style.transition = 'height 0.35s ease, opacity 0.35s ease';
      el.style.height = `${height}px`;
      el.style.opacity = '1';
      setTimeout(() => { el.style.height = 'auto'; el.style.overflow = ''; }, 350);
    }
  } else {
    const height = el.scrollHeight;
    el.style.height = `${height}px`;
    el.style.overflow = 'hidden';

    if (M && M.animate) {
      M.animate(el, { height: '0px', opacity: 0 }, { duration: 0.25, easing: 'ease-in' })
        .then(() => { el.style.display = 'none'; el.style.height = ''; el.style.overflow = ''; });
    } else {
      el.style.transition = 'height 0.25s ease, opacity 0.25s ease';
      el.style.height = '0px';
      el.style.opacity = '0';
      setTimeout(() => { el.style.display = 'none'; el.style.height = ''; el.style.overflow = ''; }, 250);
    }
  }
}

/**
 * Set up scroll-triggered reveal for .reveal elements.
 */
export function initScrollReveals() {
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    }
  }, { threshold: 0.1 });

  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
}

/**
 * Show the top progress bar (indeterminate).
 */
export function showProgressBar() {
  const bar = document.getElementById('progress-bar');
  if (bar) { bar.classList.add('active'); bar.classList.remove('complete'); }
}

/**
 * Complete and hide the top progress bar with a flash effect.
 */
export function hideProgressBar() {
  const bar = document.getElementById('progress-bar');
  if (!bar) return;
  bar.classList.add('complete');
  setTimeout(() => { bar.classList.remove('active', 'complete'); }, 500);
}

/**
 * Stagger tabs in on page load.
 */
export function staggerTabs(tabs) {
  if (!tabs) return;
  for (let i = 0; i < tabs.length; i++) {
    const tab = tabs[i];
    tab.style.opacity = '0';
    if (M && M.animate) {
      M.animate(tab,
        { opacity: [0, 1], transform: ['translateY(-4px)', 'translateY(0)'] },
        { delay: i * 0.05, duration: 0.3, easing: 'ease-out' }
      );
    } else {
      setTimeout(() => { tab.style.opacity = '1'; }, i * 50);
    }
  }
}
