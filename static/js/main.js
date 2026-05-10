/* ════════════════════════════════════════════════════════════════
   NARAYAN ADHUDE PORTFOLIO — MAIN JS
════════════════════════════════════════════════════════════════ */

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
AOS.init({
  duration: 800,
  easing: 'ease-out-cubic',
  once: true,
  offset: 60,
});

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
  if (typeof particlesJS === 'undefined' || !document.getElementById('particles-js')) return;
  particlesJS('particles-js', {
    particles: {
      number: { value: 55, density: { enable: true, value_area: 900 } },
      color:  { value: ['#4F46E5', '#06B6D4', '#7C3AED'] },
      shape:  { type: 'circle' },
      opacity: { value: 0.3, random: true, anim: { enable: true, speed: 0.8, opacity_min: 0.05 } },
      size:   { value: 3, random: true, anim: { enable: true, speed: 2, size_min: 0.5 } },
      line_linked: {
        enable: true, distance: 150,
        color: '#818CF8', opacity: 0.15, width: 1,
      },
      move: {
        enable: true, speed: 1.2, direction: 'none',
        random: true, straight: false, out_mode: 'out', bounce: false,
      },
    },
    interactivity: {
      detect_on: 'canvas',
      events: {
        onhover: { enable: true, mode: 'grab' },
        onclick: { enable: true, mode: 'push' },
        resize:  true,
      },
      modes: {
        grab:  { distance: 140, line_linked: { opacity: 0.4 } },
        push:  { particles_nb: 3 },
      },
    },
    retina_detect: true,
  });
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
