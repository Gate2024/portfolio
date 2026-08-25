/* ════════════════════════════════════════════════════════════════
   NARAYAN ADHUDE PORTFOLIO — MAIN JS
════════════════════════════════════════════════════════════════ */

/* ── Theme Toggle ────────────────────────────────────────────── */
(function initTheme() {
  const root = document.documentElement;
  const toggle = document.getElementById('themeToggle');
  if (!toggle) return;

  function updateToggle() {
    const dark = root.getAttribute('data-theme') === 'dark';
    const icon = toggle.querySelector('i');
    const label = toggle.querySelector('.theme-toggle-label');
    toggle.setAttribute('aria-pressed', String(dark));
    toggle.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
    toggle.setAttribute('title', dark ? 'Switch to light mode' : 'Switch to dark mode');
    if (icon) icon.className = dark ? 'fas fa-sun' : 'fas fa-moon';
    if (label) label.textContent = dark ? 'Day' : 'Night';
  }

  toggle.addEventListener('click', () => {
    const dark = root.getAttribute('data-theme') === 'dark';
    root.setAttribute('data-theme', dark ? 'light' : 'dark');
    try { localStorage.setItem('portfolio-theme', dark ? 'light' : 'dark'); } catch (e) {}
    updateToggle();
  });

  updateToggle();
})();

/* ── Loader ──────────────────────────────────────────────────── */
window.addEventListener('load', () => {
  setTimeout(() => {
    document.getElementById('loader')?.classList.add('hidden');
  }, 2200);
});

/* ── Custom Cursor ───────────────────────────────────────────── */
(function initCursor() {
  const cursor = document.getElementById('cursor');
  const follower = document.getElementById('cursor-follower');
  if (!cursor || !follower) return;
  if (window.innerWidth <= 768) return;

  let mx = 0, my = 0, fx = 0, fy = 0;

  document.addEventListener('mousemove', e => {
    mx = e.clientX; my = e.clientY;
    cursor.style.left = mx + 'px';
    cursor.style.top  = my + 'px';
  });

  function animateFollower() {
    fx += (mx - fx) * 0.12;
    fy += (my - fy) * 0.12;
    follower.style.left = fx + 'px';
    follower.style.top  = fy + 'px';
    requestAnimationFrame(animateFollower);
  }
  animateFollower();

  document.querySelectorAll('a, button, .skill-tab, .proj-filter, .cert-tab, .project-card-inner').forEach(el => {
    el.addEventListener('mouseenter', () => {
      cursor.style.transform = 'translate(-50%,-50%) scale(2)';
      cursor.style.opacity   = '0.5';
      follower.style.transform = 'translate(-50%,-50%) scale(1.5)';
    });
    el.addEventListener('mouseleave', () => {
      cursor.style.transform = 'translate(-50%,-50%) scale(1)';
      cursor.style.opacity   = '1';
      follower.style.transform = 'translate(-50%,-50%) scale(1)';
    });
  });
})();

/* ── Scroll Progress Bar ─────────────────────────────────────── */
(function initScrollProgress() {
  const bar = document.getElementById('scroll-progress');
  if (!bar) return;
  window.addEventListener('scroll', () => {
    const scrollTop  = document.documentElement.scrollTop;
    const docHeight  = document.documentElement.scrollHeight - document.documentElement.clientHeight;
    bar.style.width  = Math.round((scrollTop / docHeight) * 100) + '%';
  }, { passive: true });
})();

/* ── Navbar Scroll Behaviour ─────────────────────────────────── */
(function initNavbar() {
  const nav = document.getElementById('navbar');
  if (!nav) return;

  const links = nav.querySelectorAll('.nav-link');
  const sections = document.querySelectorAll('section[id]');

  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 50);

    // Active link highlight
    let current = '';
    sections.forEach(sec => {
      if (window.scrollY >= sec.offsetTop - 120) current = sec.id;
    });
    links.forEach(link => {
      link.classList.remove('active');
      if (link.getAttribute('href') === '#' + current) link.classList.add('active');
    });
  }, { passive: true });

  // Close mobile menu on link click
  links.forEach(link => {
    link.addEventListener('click', () => {
      const collapse = document.getElementById('navMenu');
      if (collapse && collapse.classList.contains('show')) {
        collapse.classList.remove('show');
      }
    });
  });
})();

/* ── Back to Top ─────────────────────────────────────────────── */
(function initBackToTop() {
  const btn = document.getElementById('back-to-top');
  if (!btn) return;
  window.addEventListener('scroll', () => {
    btn.classList.toggle('visible', window.scrollY > 400);
  }, { passive: true });
  btn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
})();

/* ── AOS Animations ──────────────────────────────────────────── */
if (typeof AOS !== 'undefined') {
  AOS.init({
    duration: 800,
    easing: 'ease-out-cubic',
    once: true,
    offset: 60,
  });
}

/* ── Typed.js ────────────────────────────────────────────────── */
(function initTyped() {
  const el = document.getElementById('typed-text');
  if (!el || typeof Typed === 'undefined') return;
  new Typed('#typed-text', {
    strings: [
      'AI/ML Engineer',
      'Full Stack Developer',
      'Python Developer',
      'Software Engineer',
      'Data Science Enthusiast',
    ],
    typeSpeed: 60,
    backSpeed: 35,
    backDelay: 1800,
    loop: true,
    cursorChar: '|',
  });
})();

/* ── Particles.js ────────────────────────────────────────────── */
(function initParticles() {
  const container = document.getElementById('particles-js');
  if (typeof particlesJS === 'undefined' || !container) return;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const coarsePointer = window.matchMedia('(pointer: coarse)').matches;
  particlesJS('particles-js', {
    particles: {
      number: { value: reducedMotion ? 35 : 55, density: { enable: true, value_area: 900 } },
      color:  { value: ['#4F46E5', '#06B6D4', '#7C3AED'] },
      shape:  { type: 'circle' },
      opacity: { value: 0.3, random: true, anim: { enable: !reducedMotion, speed: 0.8, opacity_min: 0.05 } },
      size:   { value: 3, random: true, anim: { enable: !reducedMotion, speed: 2, size_min: 0.5 } },
      line_linked: {
        enable: true, distance: 150,
        color: '#818CF8', opacity: 0.15, width: 1,
      },
      move: {
        enable: true, speed: reducedMotion ? 0.25 : 1.2, direction: 'none',
        random: true, straight: false, out_mode: 'out', bounce: false,
      },
    },
    interactivity: {
      detect_on: 'canvas',
      events: {
        onhover: { enable: !coarsePointer, mode: 'grab' },
        onclick: { enable: false, mode: 'push' },
        resize:  true,
      },
      modes: {
        grab:  { distance: reducedMotion ? 110 : 140, line_linked: { opacity: reducedMotion ? 0.25 : 0.4 } },
      },
    },
    retina_detect: true,
  });

  if (coarsePointer) return;

  const pjs = window.pJSDom?.[window.pJSDom.length - 1]?.pJS;
  const particleCanvas = pjs?.canvas?.el;
  if (!pjs || !particleCanvas) return;

  // A pointer-transparent overlay is used only for bounded ripple drawing.
  const effectCanvas = document.createElement('canvas');
  effectCanvas.setAttribute('aria-hidden', 'true');
  effectCanvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;z-index:1;pointer-events:none;';
  container.appendChild(effectCanvas);
  const effectContext = effectCanvas.getContext('2d');
  if (!effectContext) return;

  const hoverRadius = reducedMotion ? 105 : 145;
  const grabRadius = reducedMotion ? 90 : 115;
  const clusterRadius = reducedMotion ? 145 : 220;
  const maxHoverDisplacement = reducedMotion ? 2 : 9;
  const maxGrabDisplacement = reducedMotion ? 80 : Math.max(pjs.canvas.w || 320, pjs.canvas.h || 240);
  const maxNeighborDisplacement = reducedMotion ? 8 : 42;
  const particleStates = new Map();
  const dragCluster = new Map();
  const ripples = [];
  const pointer = {
    active: false,
    dragging: false,
    x: 0,
    y: 0,
    startX: 0,
    startY: 0,
    previousX: 0,
    previousY: 0,
    movementX: 0,
    movementY: 0,
    grabbed: null,
    grabOffsetX: 0,
    grabOffsetY: 0,
  };

  function canvasPoint(event) {
    const rect = particleCanvas.getBoundingClientRect();
    const width = pjs.canvas.w || rect.width;
    const height = pjs.canvas.h || rect.height;
    return {
      x: (event.clientX - rect.left) * (width / rect.width),
      y: (event.clientY - rect.top) * (height / rect.height),
    };
  }

  function resizeEffectCanvas() {
    const rect = container.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    effectCanvas.width = Math.max(1, Math.round(rect.width * ratio));
    effectCanvas.height = Math.max(1, Math.round(rect.height * ratio));
    effectContext.setTransform(ratio, 0, 0, ratio, 0, 0);
  }

  function setPointer(event) {
    const point = canvasPoint(event);
    pointer.previousX = pointer.x;
    pointer.previousY = pointer.y;
    pointer.x = point.x;
    pointer.y = point.y;
    pointer.movementX += pointer.x - pointer.previousX;
    pointer.movementY += pointer.y - pointer.previousY;
    pointer.active = true;
  }

  function findGrabTarget() {
    let target = null;
    let nearestDistance = grabRadius;
    pjs.particles.array.forEach(particle => {
      const distance = Math.hypot(particle.x - pointer.x, particle.y - pointer.y);
      if (distance <= nearestDistance) {
        target = particle;
        nearestDistance = distance;
      }
    });
    return target;
  }

  function beginDrag() {
    const target = findGrabTarget();
    if (!target) return false;

    pointer.grabbed = target;
    pointer.grabOffsetX = pointer.x - target.x;
    pointer.grabOffsetY = pointer.y - target.y;
    dragCluster.clear();
    pjs.particles.array.forEach(particle => {
      const distance = Math.hypot(particle.x - target.x, particle.y - target.y);
      if (distance > clusterRadius) return;
      const weight = Math.pow(1 - distance / clusterRadius, 2);
      const state = particleStates.get(particle) || { x: 0, y: 0, vx: 0, vy: 0, dragTargetX: 0, dragTargetY: 0 };
      const spread = distance ? (reducedMotion ? 4 : 14) * (1 - distance / clusterRadius) : 0;
      state.dragTargetX = distance ? ((particle.x - target.x) / distance) * spread : 0;
      state.dragTargetY = distance ? ((particle.y - target.y) / distance) * spread : 0;
      state.clusterWeight = weight;
      particleStates.set(particle, state);
      dragCluster.set(particle, weight);
    });
    return true;
  }

  function addClickResponse() {
    if (reducedMotion) return;
    ripples.push({ x: pointer.x, y: pointer.y, age: 0 });
    if (ripples.length > 4) ripples.shift();

    pjs.particles.array.forEach(particle => {
      const dx = particle.x - pointer.x;
      const dy = particle.y - pointer.y;
      const distance = Math.hypot(dx, dy);
      if (!distance || distance > hoverRadius * 1.15) return;
      const state = particleStates.get(particle) || { x: 0, y: 0, vx: 0, vy: 0, dragTargetX: 0, dragTargetY: 0 };
      const influence = 1 - distance / (hoverRadius * 1.15);
      state.vx += (dx / distance) * influence * 2.4;
      state.vy += (dy / distance) * influence * 2.4;
      state.dragTargetX += (dx / distance) * influence * 8;
      state.dragTargetY += (dy / distance) * influence * 8;
      particleStates.set(particle, state);
    });
  }

  function drawRipples() {
    const rect = container.getBoundingClientRect();
    effectContext.clearRect(0, 0, rect.width, rect.height);
    const dark = document.documentElement.getAttribute('data-theme') === 'dark';
    const color = dark ? '#A5B4FC' : '#4F46E5';

    for (let i = ripples.length - 1; i >= 0; i -= 1) {
      const ripple = ripples[i];
      ripple.age += reducedMotion ? 0.08 : 0.035;
      if (ripple.age >= 1) {
        ripples.splice(i, 1);
        continue;
      }
      const progress = ripple.age;
      const radiusNow = 10 + progress * (reducedMotion ? 45 : 105);
      const alpha = (1 - progress) * (dark ? 0.55 : 0.4);
      effectContext.beginPath();
      effectContext.arc(ripple.x, ripple.y, radiusNow, 0, Math.PI * 2);
      effectContext.strokeStyle = color;
      effectContext.globalAlpha = alpha;
      effectContext.lineWidth = 2;
      effectContext.stroke();
      effectContext.beginPath();
      effectContext.arc(ripple.x, ripple.y, Math.max(2, radiusNow * 0.12), 0, Math.PI * 2);
      effectContext.fillStyle = dark ? '#67E8F9' : '#06B6D4';
      effectContext.fill();
    }
    effectContext.globalAlpha = 1;
  }

  function animateInteraction() {
    const particles = pjs.particles.array;
    const movementX = pointer.movementX;
    const movementY = pointer.movementY;
    pointer.movementX = 0;
    pointer.movementY = 0;

    particles.forEach(particle => {
      const state = particleStates.get(particle) || { x: 0, y: 0, vx: 0, vy: 0, dragTargetX: 0, dragTargetY: 0 };
      particle.x -= state.x;
      particle.y -= state.y;

      const dx = particle.x - pointer.x;
      const dy = particle.y - pointer.y;
      const distance = Math.hypot(dx, dy);
      const influence = pointer.active && distance < hoverRadius ? 1 - distance / hoverRadius : 0;
      const hoverX = influence && distance ? (dx / distance) * maxHoverDisplacement * influence : 0;
      const hoverY = influence && distance ? (dy / distance) * maxHoverDisplacement * influence : 0;

      if (pointer.dragging && dragCluster.has(particle)) {
        const weight = dragCluster.get(particle);
        if (particle === pointer.grabbed) {
          const desiredX = Math.max(0, Math.min(pjs.canvas.w, pointer.x - pointer.grabOffsetX));
          const desiredY = Math.max(0, Math.min(pjs.canvas.h, pointer.y - pointer.grabOffsetY));
          state.dragTargetX = desiredX - particle.x;
          state.dragTargetY = desiredY - particle.y;
        } else {
          state.dragTargetX += movementX * weight;
          state.dragTargetY += movementY * weight;
        }
      } else if (!pointer.dragging) {
        state.dragTargetX *= 0.9;
        state.dragTargetY *= 0.9;
      }

      state.vx *= pointer.dragging ? 0.84 : 0.9;
      state.vy *= pointer.dragging ? 0.84 : 0.9;
      state.x += state.vx;
      state.y += state.vy;
      const maxOffset = particle === pointer.grabbed ? maxGrabDisplacement : maxNeighborDisplacement;
      const targetX = Math.max(-maxOffset, Math.min(maxOffset, hoverX + state.dragTargetX));
      const targetY = Math.max(-maxOffset, Math.min(maxOffset, hoverY + state.dragTargetY));
      state.x += (targetX - state.x) * (reducedMotion ? 0.2 : 0.28);
      state.y += (targetY - state.y) * (reducedMotion ? 0.2 : 0.28);
      state.x = Math.max(-maxOffset, Math.min(maxOffset, state.x));
      state.y = Math.max(-maxOffset, Math.min(maxOffset, state.y));

      particle.x += state.x;
      particle.y += state.y;
      if (Math.abs(state.x) < 0.01 && Math.abs(state.y) < 0.01 && Math.abs(state.dragTargetX) < 0.01 && Math.abs(state.dragTargetY) < 0.01 && !influence && !state.vx && !state.vy && !dragCluster.has(particle)) {
        particleStates.delete(particle);
      } else {
        particleStates.set(particle, state);
      }
    });

    drawRipples();
    window.requestAnimationFrame(animateInteraction);
  }

  particleCanvas.addEventListener('pointerenter', event => setPointer(event));
  particleCanvas.addEventListener('pointermove', event => setPointer(event));
  particleCanvas.addEventListener('pointerleave', () => { if (!pointer.dragging) pointer.active = false; });
  particleCanvas.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    const point = canvasPoint(event);
    pointer.x = point.x;
    pointer.y = point.y;
    pointer.startX = point.x;
    pointer.startY = point.y;
    pointer.previousX = point.x;
    pointer.previousY = point.y;
    pointer.movementX = 0;
    pointer.movementY = 0;
    pointer.active = beginDrag();
    pointer.dragging = pointer.active;
    if (!pointer.dragging) return;
    particleCanvas.setPointerCapture?.(event.pointerId);
  });
  particleCanvas.addEventListener('pointerup', event => {
    if (!pointer.dragging) return;
    const moved = Math.hypot(pointer.x - pointer.startX, pointer.y - pointer.startY);
    pointer.dragging = false;
    if (moved < 6) addClickResponse();
    pointer.grabbed = null;
    dragCluster.clear();
    particleCanvas.releasePointerCapture?.(event.pointerId);
  });
  particleCanvas.addEventListener('pointercancel', () => {
    pointer.dragging = false;
    pointer.grabbed = null;
    dragCluster.clear();
    pointer.active = false;
  });
  window.addEventListener('resize', resizeEffectCanvas, { passive: true });
  resizeEffectCanvas();
  window.requestAnimationFrame(animateInteraction);
})();

/* ── Counter Animation ───────────────────────────────────────── */
(function initCounters() {
  const counters = document.querySelectorAll('.counter');
  if (!counters.length) return;

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      const target = parseInt(el.dataset.target, 10) || 0;
      let current = 0;
      const increment = Math.ceil(target / 50);
      const timer = setInterval(() => {
        current = Math.min(current + increment, target);
        el.textContent = current + (el.dataset.suffix || '+');
        if (current >= target) clearInterval(timer);
      }, 35);
      observer.unobserve(el);
    });
  }, { threshold: 0.5 });

  counters.forEach(c => observer.observe(c));
})();

/* ── Skill Bar Animation ─────────────────────────────────────── */
(function initSkillBars() {
  const bars = document.querySelectorAll('.skill-bar-fill');
  if (!bars.length) return;

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const fill = entry.target;
      const wrap = fill.closest('.skill-bar-wrap');
      const bar  = fill.closest('.skill-bar');
      const pct  = bar?.dataset.width || '0';
      setTimeout(() => { fill.style.width = pct + '%'; }, 200);
      observer.unobserve(fill);
    });
  }, { threshold: 0.3 });

  bars.forEach(b => observer.observe(b));
})();

/* ── Skills Filter Tabs ──────────────────────────────────────── */
(function initSkillsFilter() {
  const tabs  = document.querySelectorAll('.skill-tab');
  const cards = document.querySelectorAll('.skill-card');
  if (!tabs.length) return;

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const cat = tab.dataset.cat;
      cards.forEach(card => {
        const match = cat === 'all' || card.dataset.category === cat;
        card.classList.toggle('hidden', !match);
        if (match) {
          // Re-trigger skill bar animation
          const fill = card.querySelector('.skill-bar-fill');
          const bar  = card.querySelector('.skill-bar');
          if (fill && bar) {
            fill.style.width = '0%';
            setTimeout(() => { fill.style.width = (bar.dataset.width || 0) + '%'; }, 50);
          }
        }
      });
    });
  });
})();

/* ── Projects Filter ─────────────────────────────────────────── */
(function initProjectFilter() {
  const filters = document.querySelectorAll('.proj-filter');
  const cards   = document.querySelectorAll('.project-card');
  if (!filters.length) return;

  filters.forEach(f => {
    f.addEventListener('click', () => {
      filters.forEach(x => x.classList.remove('active'));
      f.classList.add('active');
      const filter = f.dataset.filter;
      cards.forEach((card, i) => {
        const match = filter === 'all' || card.dataset.category === filter;
        card.classList.toggle('hidden', !match);
        if (match) {
          card.style.animationDelay = (i % 3 * 0.1) + 's';
        }
      });
    });
  });
})();

/* ── Certifications Filter ───────────────────────────────────── */
(function initCertFilter() {
  const tabs  = document.querySelectorAll('.cert-tab');
  const cards = document.querySelectorAll('.cert-card');
  if (!tabs.length) return;

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const cat = tab.dataset.certcat;
      cards.forEach(card => {
        const match = cat === 'all' || card.dataset.certcat === cat;
        card.classList.toggle('hidden', !match);
      });
    });
  });
})();

/* ── Contact Form AJAX ───────────────────────────────────────── */
(function initContactForm() {
  const form    = document.getElementById('contactForm');
  const alertEl = document.getElementById('form-alert');
  const btn     = document.getElementById('submitBtn');
  if (!form) return;

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const text    = btn.querySelector('.btn-text');
    const loading = btn.querySelector('.btn-loading');

    // Show loading
    text?.classList.add('d-none');
    loading?.classList.remove('d-none');
    btn.disabled = true;

    const formData = new FormData(form);

    try {
      const res  = await fetch('/contact', { method: 'POST', body: formData });
      const data = await res.json();

      alertEl.textContent = data.message;
      alertEl.className   = 'form-alert ' + (data.success ? 'success' : 'error');
      alertEl.classList.remove('d-none');

      if (data.success) {
        form.reset();
        setTimeout(() => alertEl.classList.add('d-none'), 6000);
      }
    } catch {
      alertEl.textContent = 'Something went wrong. Please try again.';
      alertEl.className   = 'form-alert error';
      alertEl.classList.remove('d-none');
    }

    text?.classList.remove('d-none');
    loading?.classList.add('d-none');
    btn.disabled = false;
  });
})();

/* ── Smooth Scroll for anchor links ─────────────────────────── */
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', e => {
    const target = document.querySelector(anchor.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

/* ── Staggered card reveal on scroll ────────────────────────── */
(function initStagger() {
  const groups = [
    '.ach-card', '.service-card', '.cert-card-inner'
  ];
  groups.forEach(sel => {
    document.querySelectorAll(sel).forEach((el, i) => {
      el.style.transitionDelay = (i % 4 * 0.06) + 's';
    });
  });
})();

/* ── Flash message auto-dismiss ─────────────────────────────── */
document.querySelectorAll('.alert-dismissible').forEach(alert => {
  setTimeout(() => {
    if (typeof bootstrap !== 'undefined') {
      bootstrap.Alert.getOrCreateInstance(alert)?.close();
    }
  }, 4500);
});
