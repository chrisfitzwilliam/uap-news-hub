document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('sky-nav-root');
  if (!root) return;

  const currentPath = window.location.pathname;
  const links = root.querySelectorAll('.sky-nav-link');
  links.forEach(link => {
    const href = link.getAttribute('href');
    const pathOnly = href.split('?')[0].split('#')[0];
    
    let isActive = false;
    if (pathOnly.endsWith('/')) {
      if (currentPath === '/' || currentPath.endsWith('/index.html')) {
        isActive = true;
      }
    } else {
      const filename = pathOnly.split('/').pop();
      if (filename && currentPath.includes(filename)) {
        isActive = true;
      }
    }
    
    if (isActive) {
      link.classList.add('is-active');
    }
  });

  const onScroll = () => {
    const s = window.scrollY > 24;
    if (s) {
      root.classList.add('is-scrolled');
    } else {
      root.classList.remove('is-scrolled');
    }
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  root.querySelectorAll('[data-magnetic]').forEach((el) => {
    const inner = el.querySelector('[data-mag-inner]') || el;
    const move = (e) => {
      const r = el.getBoundingClientRect();
      const dx = (e.clientX - (r.left + r.width / 2)) * 0.32;
      const dy = (e.clientY - (r.top + r.height / 2)) * 0.4;
      el.style.transform = `translate(${dx}px, ${dy}px)`;
      inner.style.transform = `translate(${dx * 0.4}px, ${dy * 0.4}px)`;
    };
    const leave = () => { el.style.transform = ''; inner.style.transform = ''; };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerleave', leave);
  });

  // Initialize starfield if present
  const starfieldCanvas = document.getElementById('sky-home-canvas') || document.getElementById('sky-yt-canvas');
  if (starfieldCanvas) {
    import('./starfield.js').then(({ initStarfield }) => {
      initStarfield(starfieldCanvas, { density: 1, shooting: true });
    }).catch(err => console.error('Failed to load starfield.js', err));
  }
});
