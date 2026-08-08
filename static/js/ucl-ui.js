// ===== UCL UI =====

// 1) Active link in navbar (desktop + mobile)
(function () {
  const currentPath = window.location.pathname.replace(/\/+$/, "") || "/";
  const links = document.querySelectorAll("a.nav-link");
  links.forEach(a => {
    const href = (a.getAttribute("href") || "").replace(/\/+$/, "") || "/";
    if (href === currentPath) a.classList.add("active");
  });
})();

// 2) Navbar scroll effect (slightly darker + smaller shadow)
(function () {
  const nav = document.querySelector(".ucl-nav");
  if (!nav) return;

  const onScroll = () => {
    const scrolled = window.scrollY > 8;
    nav.classList.toggle("ucl-nav-scrolled", scrolled);
  };

  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
})();

// 3) Reveal animations (lightweight)
(function () {
  const items = document.querySelectorAll(".ucl-reveal");
  if (!items.length) return;

  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) e.target.classList.add("is-visible");
    });
  }, { threshold: 0.12 });

  items.forEach(el => io.observe(el));
})();