// The Shared Table — favourites, recipe-grid filters, and weekly-plan helpers.
(function () {
  const FAV_KEY = 'tst-favs';
  const PLAN_KEY = 'tst-plan';
  const DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
  const DAY_NAMES = { mon: 'Monday', tue: 'Tuesday', wed: 'Wednesday', thu: 'Thursday', fri: 'Friday', sat: 'Saturday', sun: 'Sunday' };
  const SLOT_FOR_PREFIX = { b: 'breakfast', l: 'lunch', d: 'dinner', t: 'treat' };

  // ---------- shared storage ----------
  function loadFavs() {
    try { return new Set(JSON.parse(localStorage.getItem(FAV_KEY) || '[]')); }
    catch (_) { return new Set(); }
  }
  const favs = loadFavs();
  const saveFavs = () => localStorage.setItem(FAV_KEY, JSON.stringify([...favs]));

  function loadPlan() {
    try { return JSON.parse(localStorage.getItem(PLAN_KEY) || '{}') || {}; }
    catch (_) { return {}; }
  }
  function savePlan(plan) { localStorage.setItem(PLAN_KEY, JSON.stringify(plan)); }

  // Exposed for planner.html
  window.tstPlan = { loadPlan, savePlan, DAYS, DAY_NAMES, SLOT_FOR_PREFIX };

  const idFromHref = (href) => (href && href.includes('#')) ? href.split('#')[1] : '';

  // ---------- toast ----------
  let toastEl = null, toastTimer = null;
  function toast(html) {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'toast';
      document.body.appendChild(toastEl);
    }
    toastEl.innerHTML = html;
    toastEl.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove('show'), 3500);
  }

  // ---------- favourites ----------
  function renderBtn(btn) {
    const on = favs.has(btn.dataset.id);
    btn.classList.toggle('on', on);
    btn.textContent = on ? '♥' : '♡';
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    btn.title = on ? 'Remove from favourites' : 'Add to favourites';
  }

  function heartBtn(id) {
    const btn = document.createElement('button');
    btn.className = 'fav-btn';
    btn.type = 'button';
    btn.dataset.id = id;
    btn.setAttribute('aria-label', 'Favourite this recipe');
    renderBtn(btn);
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      favs.has(id) ? favs.delete(id) : favs.add(id);
      saveFavs();
      document.querySelectorAll('.fav-btn[data-id="' + id + '"]').forEach(renderBtn);
      applyFilter();
    });
    return btn;
  }

  document.querySelectorAll('#cards .card').forEach((card) => {
    const id = idFromHref(card.getAttribute('href'));
    if (id) card.appendChild(heartBtn(id));
  });

  // ---------- recipe pages: heart + add-to-plan ----------
  document.querySelectorAll('article.recipe[id]').forEach((article) => {
    article.appendChild(heartBtn(article.id));

    const slot = SLOT_FOR_PREFIX[article.id.charAt(0)];
    if (!slot) return;
    const planBtn = document.createElement('button');
    planBtn.className = 'plan-btn';
    planBtn.type = 'button';
    planBtn.textContent = '📅 Plan';
    planBtn.title = 'Add this recipe to your weekly plan';
    planBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const existing = article.querySelector('.plan-pop');
      document.querySelectorAll('.plan-pop').forEach((p) => p.remove());
      if (existing) return;
      const pop = document.createElement('div');
      pop.className = 'plan-pop';
      pop.innerHTML = '<h5>Add to which day?</h5>';
      const grid = document.createElement('div');
      grid.className = 'pop-days';
      DAYS.forEach((day) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.textContent = DAY_NAMES[day].slice(0, 3);
        b.addEventListener('click', () => {
          const plan = loadPlan();
          plan[day] = plan[day] || {};
          plan[day][slot] = article.id;
          savePlan(plan);
          pop.remove();
          toast('Added to ' + DAY_NAMES[day] + ' ' + slot + ' ✓ &nbsp;<a href="planner.html">Open planner →</a>');
        });
        grid.appendChild(b);
      });
      pop.appendChild(grid);
      article.appendChild(pop);
    });
    article.appendChild(planBtn);
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.plan-pop') && !e.target.closest('.plan-btn')) {
      document.querySelectorAll('.plan-pop').forEach((p) => p.remove());
    }
  });

  // ---------- filters (index page) ----------
  let current = 'all';
  const filterBox = document.getElementById('filters');

  function applyFilter() {
    const cards = document.querySelectorAll('#cards .card');
    if (!cards.length) return;
    let shown = 0;
    cards.forEach((card) => {
      const cats = (card.dataset.cat || '').split(' ');
      const id = idFromHref(card.getAttribute('href'));
      const show = current === 'all' || (current === 'fav' ? favs.has(id) : cats.includes(current));
      card.style.display = show ? '' : 'none';
      if (show) shown++;
    });
    const empty = document.getElementById('fav-empty');
    if (empty) empty.style.display = (current === 'fav' && shown === 0) ? '' : 'none';
  }

  if (filterBox) {
    filterBox.addEventListener('click', (e) => {
      const btn = e.target.closest('.filter-btn');
      if (!btn) return;
      filterBox.querySelectorAll('.filter-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      current = btn.dataset.filter;
      applyFilter();
    });
  }
})();
