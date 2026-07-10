// Skyledger starfield — layered parallax stars, drift, twinkle, occasional shooting star.
// Usage (from a DC logic class):
//   const { initStarfield } = await import('./starfield.js');
//   this._sf = initStarfield(canvasEl, { density: 1, shooting: true });
//   // later: this._sf.destroy();

export function initStarfield(canvas, opts = {}) {
  const cfg = {
    density: opts.density ?? 1,        // multiplier on star count
    shooting: opts.shooting ?? true,   // occasional shooting stars
    parallax: opts.parallax ?? true,   // react to pointer
    hue: opts.hue ?? '0, 229, 255',    // cyan rgb for tinted stars
    maxDpr: opts.maxDpr ?? 2,
  };
  const ctx = canvas.getContext('2d');
  let W = 0, H = 0, dpr = 1;
  let layers = [];
  let shoots = [];
  let raf = null;
  let running = true;
  const pointer = { x: 0, y: 0, tx: 0, ty: 0 };

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, cfg.maxDpr);
    const rect = canvas.getBoundingClientRect();
    W = Math.max(1, Math.floor(rect.width));
    H = Math.max(1, Math.floor(rect.height));
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    build();
  }

  function build() {
    const area = W * H;
    // three depth layers, each a different parallax factor & size range
    const specs = [
      { count: area / 9000, sizeMin: 0.4, sizeMax: 1.0, speed: 0.006, par: 6,  alpha: 0.55 },
      { count: area / 14000, sizeMin: 0.7, sizeMax: 1.6, speed: 0.012, par: 14, alpha: 0.8 },
      { count: area / 26000, sizeMin: 1.1, sizeMax: 2.4, speed: 0.02, par: 26, alpha: 1.0 },
    ];
    layers = specs.map((s) => {
      const n = Math.max(6, Math.round(s.count * cfg.density));
      const stars = [];
      for (let i = 0; i < n; i++) {
        stars.push({
          x: Math.random() * W,
          y: Math.random() * H,
          r: s.sizeMin + Math.random() * (s.sizeMax - s.sizeMin),
          tw: Math.random() * Math.PI * 2,     // twinkle phase
          twS: 0.6 + Math.random() * 1.6,      // twinkle speed
          tinted: Math.random() < 0.12,        // some stars carry the cyan tint
          base: s.alpha * (0.5 + Math.random() * 0.5),
        });
      }
      return { ...s, stars };
    });
  }

  function maybeShoot(t) {
    if (!cfg.shooting) return;
    if (shoots.length === 0 && Math.random() < 0.004) {
      const fromLeft = Math.random() < 0.5;
      const y0 = Math.random() * H * 0.5;
      shoots.push({
        x: fromLeft ? -40 : W + 40,
        y: y0,
        vx: (fromLeft ? 1 : -1) * (6 + Math.random() * 4),
        vy: 2.2 + Math.random() * 1.5,
        life: 0,
        max: 60 + Math.random() * 30,
      });
    }
  }

  function frame(t) {
    if (!running) return;
    ctx.clearRect(0, 0, W, H);
    // ease pointer
    pointer.x += (pointer.tx - pointer.x) * 0.05;
    pointer.y += (pointer.ty - pointer.y) * 0.05;

    for (const layer of layers) {
      const px = cfg.parallax ? pointer.x * layer.par : 0;
      const py = cfg.parallax ? pointer.y * layer.par : 0;
      for (const s of layer.stars) {
        s.y += layer.speed;            // slow downward drift
        s.tw += 0.02 * s.twS;
        if (s.y > H + 2) { s.y = -2; s.x = Math.random() * W; }
        const twinkle = 0.6 + 0.4 * Math.sin(s.tw);
        const a = Math.min(1, s.base * twinkle);
        const x = s.x + px;
        const y = s.y + py;
        ctx.beginPath();
        ctx.arc(x, y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = s.tinted
          ? `rgba(${cfg.hue}, ${a})`
          : `rgba(244, 246, 250, ${a})`;
        ctx.fill();
        if (s.r > 1.6) {
          ctx.beginPath();
          ctx.arc(x, y, s.r * 2.4, 0, Math.PI * 2);
          ctx.fillStyle = s.tinted
            ? `rgba(${cfg.hue}, ${a * 0.12})`
            : `rgba(244, 246, 250, ${a * 0.08})`;
          ctx.fill();
        }
      }
    }

    // shooting stars
    maybeShoot(t);
    for (let i = shoots.length - 1; i >= 0; i--) {
      const sh = shoots[i];
      sh.x += sh.vx; sh.y += sh.vy; sh.life++;
      const tailX = sh.x - sh.vx * 6;
      const tailY = sh.y - sh.vy * 6;
      const grad = ctx.createLinearGradient(sh.x, sh.y, tailX, tailY);
      const la = Math.max(0, 1 - sh.life / sh.max);
      grad.addColorStop(0, `rgba(${cfg.hue}, ${0.9 * la})`);
      grad.addColorStop(1, 'rgba(0,229,255,0)');
      ctx.strokeStyle = grad;
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.moveTo(sh.x, sh.y);
      ctx.lineTo(tailX, tailY);
      ctx.stroke();
      if (sh.life > sh.max || sh.x < -60 || sh.x > W + 60 || sh.y > H + 60) shoots.splice(i, 1);
    }

    raf = requestAnimationFrame(frame);
  }

  function onMove(e) {
    const rect = canvas.getBoundingClientRect();
    const cx = (e.clientX - rect.left) / rect.width - 0.5;
    const cy = (e.clientY - rect.top) / rect.height - 0.5;
    pointer.tx = cx;
    pointer.ty = cy;
  }

  const ro = new ResizeObserver(resize);
  ro.observe(canvas);
  resize();
  if (cfg.parallax) window.addEventListener('pointermove', onMove, { passive: true });
  const onVis = () => { running = !document.hidden; if (running) raf = requestAnimationFrame(frame); };
  document.addEventListener('visibilitychange', onVis);
  raf = requestAnimationFrame(frame);

  return {
    destroy() {
      running = false;
      if (raf) cancelAnimationFrame(raf);
      ro.disconnect();
      window.removeEventListener('pointermove', onMove);
      document.removeEventListener('visibilitychange', onVis);
    },
  };
}
