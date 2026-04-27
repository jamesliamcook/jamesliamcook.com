// ── Mobile nav toggle ─────────────────────────────────────────
const toggle = document.querySelector('.nav-toggle');
const links  = document.querySelector('.nav-links');

if (toggle && links) {
  toggle.addEventListener('click', () => {
    const open = links.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open);
  });
  links.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => {
      links.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    });
  });
}

// ── Active nav highlight on mobile ────────────────────────────
// Mark the current page link as active (already done in HTML for desktop,
// but when the mobile menu opens it needs the same visual treatment)
const currentPath = window.location.pathname.split('/').pop() || 'index.html';
document.querySelectorAll('.nav-links a').forEach(a => {
  const href = a.getAttribute('href');
  if (href === currentPath || (currentPath === '' && href === 'index.html')) {
    a.classList.add('active');
  }
});

// ── Scroll-in animation ───────────────────────────────────────
const fadeEls = document.querySelectorAll(
  '.clip-row, .lzn-clip, .home-nav-item, .about-grid, .lzn-stats, .lzn-intro'
);

if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });

  fadeEls.forEach((el, i) => {
    el.classList.add('fade-in');
    // Stagger rows — cap at 10 so long lists don't delay forever
    el.style.transitionDelay = Math.min(i * 40, 400) + 'ms';
    observer.observe(el);
  });
}
