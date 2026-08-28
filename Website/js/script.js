// Minimal interactions - keep premium calm feeling

document.addEventListener('DOMContentLoaded', () => {
  // Smooth scroll for nav links
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', (e) => {
      const href = a.getAttribute('href');
      if (href.length > 1) {
        const target = document.querySelector(href);
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    });
  });

  // Subtle parallax for hero visual
  const visual = document.querySelector('.hero-visual');
  const labels = document.querySelectorAll('.float-label');
  if (visual) {
    let ticking = false;
    window.addEventListener('scroll', () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          const rect = visual.getBoundingClientRect();
          const progress = Math.max(0, Math.min(1, 1 - rect.top / window.innerHeight));
          visual.style.transform = `translateY(${progress * 4}px)`;
          labels.forEach((el, i) => {
            const offset = ((i % 2 === 0) ? 1 : -1) * progress * 3;
            el.style.transform = `translateY(${offset}px)`;
          });
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });
  }

  // Sequential reveal for How It Works cards - vertical one after another
  const howCards = document.querySelectorAll('.how-card');
  if (howCards.length) {
    const cardObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          cardObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.22, rootMargin: '0px 0px -40px 0px' });

    howCards.forEach(card => cardObserver.observe(card));

    // fallback: if already in viewport on load, reveal with stagger
    setTimeout(() => {
      howCards.forEach((card, i) => {
        if (card.getBoundingClientRect().top < window.innerHeight * 0.92) {
          setTimeout(() => card.classList.add('visible'), i * 140);
        }
      });
    }, 320);
  }

  // Nav active state on scroll
  const sections = ['#how', '#roles', '#features'].map(s => document.querySelector(s)).filter(Boolean);
  const navLinks = document.querySelectorAll('.nav-link');
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = '#' + entry.target.id;
        navLinks.forEach(l => l.classList.toggle('active', l.getAttribute('href') === id));
        if (entry.target.id === 'how' || entry.target.id === 'roles') {
          // keep Home active when at top
        }
      }
    });
  }, { rootMargin: '-45% 0px -45% 0px', threshold: 0 });

  sections.forEach(s => observer.observe(s));

  // Mobile toggle
  const toggle = document.querySelector('.nav-toggle');
  const nav = document.querySelector('.nav-inner');
  if (toggle) {
    toggle.addEventListener('click', () => {
      nav.classList.toggle('open');
      const links = document.querySelector('.nav-links');
      if (links) {
        links.style.display = links.style.display === 'flex' ? '' : 'flex';
        links.style.position = 'absolute';
        links.style.top = '56px';
        links.style.left = '16px';
        links.style.right = '16px';
        links.style.background = 'rgba(17,18,20,0.96)';
        links.style.border = '1px solid #242629';
        links.style.borderRadius = '16px';
        links.style.flexDirection = 'column';
        links.style.padding = '14px';
        links.style.gap = '14px';
        links.style.backdropFilter = 'blur(16px)';
      }
    });
  }
});
