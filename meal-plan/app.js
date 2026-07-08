// The Shared Table — favourites (localStorage) + recipe-grid filters.
(function () {
  const KEY = 'tst-favs';

  function loadFavs() {
    try { return new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); }
    catch (_) { return new Set(); }
  }
  const favs = loadFavs();
  const saveFavs = () => localStorage.setItem(KEY, JSON.stringify([...favs]));

  const idFromHref = (href) => (href && href.includes('#')) ? href.split('#')[1] : '';

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

  // Hearts on index cards
  document.querySelectorAll('#cards .card').forEach((card) => {
    const id = idFromHref(card.getAttribute('href'));
    if (id) card.appendChild(heartBtn(id));
  });

  // Hearts on recipe pages
  document.querySelectorAll('article.recipe[id]').forEach((article) => {
    article.appendChild(heartBtn(article.id));
  });

  // Filters (index page only)
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
