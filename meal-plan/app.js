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
  function savePlan(plan) { localStorage.setItem(PLAN_KEY, JSON.stringify(plan)); famTouched('plan'); }

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

  // ---------- shopping list store & ingredient parser ----------
  const SHOP_KEY = 'tst-shop';
  function loadShop() {
    try { return JSON.parse(localStorage.getItem(SHOP_KEY) || '[]') || []; }
    catch (_) { return []; }
  }
  function saveShop(items) { localStorage.setItem(SHOP_KEY, JSON.stringify(items)); famTouched('shop'); }
  const normText = (t) => String(t).replace(/\s+/g, ' ').trim();

  // Categories: meat, veg, dairy, grain, frozen, pantry, other.
  // Keyword -> [canonical buyable name, category]. Matched longest-first, so
  // "garlic powder" wins over "garlic", "peanut butter" over "butter", etc.
  const ING_MAP = [
    // meat & fish
    ['chicken breast', 'chicken breast', 'meat'], ['chicken thigh', 'chicken thigh fillets', 'meat'],
    ['turkey mince', 'turkey mince (2% fat)', 'meat'], ['smoked salmon', 'smoked salmon', 'meat'],
    ['salmon', 'salmon fillets', 'meat'], ['prawn', 'raw king prawns', 'meat'],
    ['sirloin', 'sirloin steaks', 'meat'], ['steak', 'sirloin steaks', 'meat'],
    ['chicken', 'chicken breast', 'meat'],
    // fruit & veg
    ['cherry tomatoes', 'cherry tomatoes', 'veg'], ['tomato', 'tomatoes', 'veg'],
    ['spring onion', 'spring onions', 'veg'], ['red onion', 'red onions', 'veg'], ['onion', 'onions', 'veg'],
    ['garlic powder', 'garlic powder', 'pantry'], ['garlic', 'garlic', 'veg'],
    ['red pepper', 'peppers', 'veg'], ['yellow pepper', 'peppers', 'veg'], ['peppers (mixed', 'peppers', 'veg'], ['pepper', 'peppers', 'veg'],
    ['cucumber', 'cucumber', 'veg'], ['courgette', 'courgettes', 'veg'], ['carrot', 'carrots', 'veg'],
    ['tenderstem', 'Tenderstem broccoli', 'veg'], ['broccoli', 'broccoli', 'veg'],
    ['green beans', 'green beans', 'veg'], ['sugar snap', 'sugar snap peas', 'veg'],
    ['black beans', 'black beans (tin)', 'pantry'], ['chickpea', 'chickpeas (tin)', 'pantry'],
    ['little gem', 'Little Gem lettuce', 'veg'], ['lettuce', 'Little Gem lettuce', 'veg'],
    ['spinach', 'baby spinach', 'veg'], ['rocket', 'rocket', 'veg'], ['red cabbage', 'red cabbage', 'veg'],
    ['avocado', 'avocados', 'veg'], ['red chilli', 'fresh red chilli', 'veg'],
    ['ginger', 'fresh ginger', 'veg'],
    ['sweet potato', 'sweet potatoes', 'veg'], ['new potato', 'baby new potatoes', 'veg'],
    ['baby potato', 'baby new potatoes', 'veg'], ['baby new potato', 'baby new potatoes', 'veg'], ['potato', 'potatoes', 'veg'],
    ['lemon', 'lemons', 'veg'], ['lime', 'limes', 'veg'], ['apple', 'apples', 'veg'], ['banana', 'bananas', 'veg'],
    ['blueberr', 'blueberries', 'veg'], ['raspberr', 'raspberries', 'veg'], ['berries', 'berries (fresh or frozen)', 'veg'],
    ['dates', 'soft pitted dates', 'veg'], ['mushroom', 'mushrooms', 'veg'],
    ['parsley', 'fresh parsley', 'veg'], ['mint', 'fresh mint', 'veg'], ['dill', 'fresh dill', 'veg'],
    ['coriander', 'fresh coriander', 'veg'], ['basil', 'fresh basil', 'veg'],
    ['rosemary', 'fresh rosemary', 'veg'], ['thyme', 'fresh thyme', 'veg'], ['chives', 'fresh chives', 'veg'],
    // frozen
    ['edamame', 'frozen edamame', 'frozen'], ['peas', 'frozen peas', 'frozen'], ['sweetcorn', 'sweetcorn', 'frozen'],
    // dairy & eggs
    ['greek yogurt', 'Greek yogurt', 'dairy'], ['yogurt', 'Greek yogurt', 'dairy'],
    ['cottage cheese', 'cottage cheese', 'dairy'], ['halloumi', 'halloumi', 'dairy'],
    ['cheddar', 'cheddar', 'dairy'], ['parmesan', 'parmesan', 'dairy'],
    ['crème fraîche', 'half-fat crème fraîche', 'dairy'], ['creme fraiche', 'half-fat crème fraîche', 'dairy'],
    ['milk', 'milk', 'dairy'], ['peanut butter', 'peanut butter (100% nuts)', 'pantry'], ['butter', 'butter', 'dairy'],
    ['egg', 'eggs', 'dairy'],
    // bakery & grains
    ['pitta', 'wholemeal pittas', 'grain'], ['tortilla', 'wholemeal tortilla wraps', 'grain'], ['wrap', 'wholemeal tortilla wraps', 'grain'],
    ['bun', 'wholemeal buns', 'grain'], ['bread', 'wholemeal bread', 'grain'],
    ['rice', 'basmati rice', 'grain'], ['noodle', 'wholewheat noodles', 'grain'],
    ['spaghetti', 'wholemeal spaghetti', 'grain'], ['penne', 'wholemeal penne', 'grain'], ['pasta', 'wholemeal pasta', 'grain'],
    ['couscous', 'wholewheat couscous', 'grain'], ['oats', 'porridge oats', 'grain'],
    ['panko', 'panko breadcrumbs', 'grain'], ['breadcrumb', 'panko breadcrumbs', 'grain'],
    // store cupboard
    ['extra virgin olive oil', 'olive oil', 'pantry'], ['olive oil', 'olive oil', 'pantry'], ['oil', 'olive oil', 'pantry'],
    ['soy sauce', 'soy sauce', 'pantry'], ['soy', 'soy sauce', 'pantry'], ['honey', 'honey', 'pantry'],
    ['red wine vinegar', 'red wine vinegar', 'pantry'], ['wine vinegar', 'red wine vinegar', 'pantry'],
    ['balsamic', 'balsamic vinegar', 'pantry'], ['rice vinegar', 'rice vinegar', 'pantry'], ['vinegar', 'red wine vinegar', 'pantry'],
    ['dijon', 'Dijon mustard', 'pantry'], ['mustard', 'Dijon mustard', 'pantry'],
    ['sriracha', 'sriracha', 'pantry'], ['gherkin', 'gherkins', 'pantry'], ['olive', 'olives (jar)', 'pantry'],
    ['anchov', 'anchovy fillets', 'pantry'],
    ['peanuts', 'roasted peanuts', 'pantry'], ['sesame', 'sesame seeds', 'pantry'],
    ['mixed seeds', 'mixed seeds', 'pantry'], ['seeds', 'mixed seeds', 'pantry'],
    ['flaked almonds', 'flaked almonds', 'pantry'], ['almond', 'almonds', 'pantry'],
    ['pistachio', 'pistachios', 'pantry'], ['walnut', 'walnuts', 'pantry'], ['sultana', 'sultanas', 'pantry'],
    ['cocoa', 'cocoa powder', 'pantry'], ['chocolate chip', 'dark chocolate chips', 'pantry'],
    ['dark chocolate', 'dark chocolate (70%)', 'pantry'], ['chocolate', 'dark chocolate (70%)', 'pantry'],
    ['vanilla', 'vanilla extract', 'pantry'], ['baking powder', 'baking powder', 'pantry'],
    ['bicarbonate', 'bicarbonate of soda', 'pantry'], ['cornflour', 'cornflour', 'pantry'], ['flour', 'plain flour', 'pantry'],
    ['stock cube', 'stock cubes', 'pantry'], ['stock', 'stock cubes', 'pantry'],
    ['granola', 'granola', 'pantry'],
    ['smoked paprika', 'smoked paprika', 'pantry'], ['paprika', 'smoked paprika', 'pantry'],
    ['cumin', 'ground cumin', 'pantry'], ['cinnamon', 'ground cinnamon', 'pantry'],
    ['curry powder', 'mild curry powder', 'pantry'], ['turmeric', 'turmeric', 'pantry'],
    ['cayenne', 'cayenne pepper', 'pantry'], ['chilli flakes', 'chilli flakes', 'pantry'],
    ['oregano', 'dried oregano', 'pantry'], ['cajun', 'cajun spice mix', 'pantry'],
  ].sort((a, b) => b[0].length - a[0].length);

  const HERBS = ['parsley', 'mint', 'dill', 'coriander', 'basil', 'rosemary', 'thyme', 'chives'];

  // Fragments that are seasoning noise, not shopping items.
  function isSkippable(part) {
    const c = part.toLowerCase().replace(/^[\d\s½¼¾×x.]*(g|kg|ml|tsp|tbsp|pinch( of)?|handful( of)?)?\s*/i, '').trim();
    return /^((flaky |fine sea )?salt([ &,]+(coarse |black )?pepper)?|black pepper|pepper$|salt & black pepper|water)$/.test(c)
      || /^(to serve|to finish|optional.*)$/.test(c);
  }

  // "½ cucumber + 150g cherry tomatoes + ¼ red onion (salad)" ->
  // [{name:'cucumber',...}, {name:'cherry tomatoes',...}, {name:'red onions',...}]
  function parseIngredient(text) {
    const cleaned = normText(text).replace(/\([^)]*\)/g, '').replace(/\s+/g, ' ');
    const parts = cleaned.split(/\s*[+·]\s*/).map(normText).filter(Boolean);
    const out = [];
    parts.forEach((part) => {
      if (isSkippable(part)) return;
      const lower = part.toLowerCase();
      const hit = ING_MAP.find(([k]) => lower.includes(k));
      if (hit) {
        out.push({ name: hit[1], cat: hit[2], raw: part });
        // herb pairs like "parsley & dill" — pick up the extra herbs too
        HERBS.forEach((h) => {
          if (h !== hit[0] && !hit[1].toLowerCase().includes(h) && lower.includes(h)) {
            out.push({ name: 'fresh ' + h, cat: 'veg', raw: part });
          }
        });
      } else {
        const fallback = part.replace(/^[\d\s½¼¾×x.]*(g|kg|ml|l|tsp|tbsp)?\s*/i, '').trim();
        out.push({ name: fallback || part, cat: 'other', raw: part });
      }
    });
    return out;
  }

  // Merge parsed ingredients into the list: one line per buyable item,
  // recipe amounts collected underneath.
  function addToShop(entries) {
    const items = loadShop();
    let added = 0;
    entries.forEach((e) => {
      parseIngredient(e.t).forEach((ing) => {
        const existing = items.find((i) => !i.d && i.t.toLowerCase() === ing.name.toLowerCase());
        const detail = ing.raw + (e.f ? ' — ' + e.f : '');
        if (existing) {
          existing.n = (existing.n || 1) + 1;
          existing.a = existing.a || [];
          if (existing.a.indexOf(detail) === -1) existing.a.push(detail);
        } else {
          items.push({ t: ing.name, c: ing.cat, n: 1, d: false, f: e.f || '', a: [detail] });
        }
        added++;
      });
    });
    saveShop(items);
    return added;
  }

  window.tstShop = { load: loadShop, save: saveShop, add: addToShop };
  window.tstToast = toast;

  // ---------- recipe pages: ingredient "+" and "Add all" buttons ----------
  document.querySelectorAll('article.recipe[id]').forEach((article) => {
    const h2 = article.querySelector('h2');
    const recipeName = h2 ? normText(h2.textContent).split(' with ')[0].slice(0, 60) : '';
    const box = article.querySelector('.ingredients');
    if (!box) return;

    box.querySelectorAll('li').forEach((li) => {
      const btn = document.createElement('button');
      btn.className = 'add-ing';
      btn.type = 'button';
      btn.textContent = '+';
      btn.title = 'Add to shopping list';
      btn.setAttribute('aria-label', 'Add ingredient to shopping list');
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const clone = li.cloneNode(true);
        clone.querySelectorAll('button').forEach((b) => b.remove());
        addToShop([{ t: clone.textContent, f: recipeName }]);
        btn.classList.add('added');
        btn.textContent = '✓';
        setTimeout(() => { btn.classList.remove('added'); btn.textContent = '+'; }, 1500);
        toast('Added to shopping list ✓ &nbsp;<a href="shopping.html">View list →</a>');
      });
      li.appendChild(btn);
    });

    const h3 = box.querySelector('h3');
    if (h3) {
      const all = document.createElement('button');
      all.className = 'add-all-btn';
      all.type = 'button';
      all.textContent = '🛒 Add all';
      all.title = 'Add every ingredient to the shopping list';
      all.addEventListener('click', (e) => {
        e.preventDefault();
        const entries = [...box.querySelectorAll('li')].map((li) => {
          const clone = li.cloneNode(true);
          clone.querySelectorAll('button').forEach((b) => b.remove());
          return { t: clone.textContent, f: recipeName };
        });
        const n = addToShop(entries);
        toast(n + ' ingredients added ✓ &nbsp;<a href="shopping.html">View list →</a>');
      });
      h3.insertAdjacentElement('afterend', all);
    }
  });

  // ---------- family sync (Cloudflare KV via /api/family) ----------
  // Everyone using the same family code shares the shopping list and weekly
  // plan. Last write wins; a dirty flag protects unsynced local edits from
  // being overwritten by a pull.
  const FAM_KEY = 'tst-family';
  const STORE_KEYS = { shop: SHOP_KEY, plan: PLAN_KEY };
  const DIRTY = { shop: 'tst-dirty-shop', plan: 'tst-dirty-plan' };
  const EMPTY = { shop: '[]', plan: '{}' };
  const pushTimers = {};

  function famCode() { return (localStorage.getItem(FAM_KEY) || '').toUpperCase(); }

  function famTouched(key) {
    if (!famCode()) return;
    localStorage.setItem(DIRTY[key], '1');
    clearTimeout(pushTimers[key]);
    pushTimers[key] = setTimeout(() => famPush(key), 800);
  }

  async function famApi(body) {
    const res = await fetch('/api/family', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    return res.ok ? res.json() : null;
  }

  async function famPush(key) {
    const code = famCode();
    if (!code) return;
    try {
      const data = JSON.parse(localStorage.getItem(STORE_KEYS[key]) || EMPTY[key]);
      const j = await famApi({ code, key, action: 'put', data });
      if (j && j.ok) localStorage.removeItem(DIRTY[key]);
    } catch (_) { /* offline — dirty flag stays; retried on next change or pull */ }
  }

  async function famPull() {
    const code = famCode();
    if (!code) return false;
    let changed = false;
    for (const key of ['shop', 'plan']) {
      try {
        if (localStorage.getItem(DIRTY[key])) { await famPush(key); continue; }
        const j = await famApi({ code, key, action: 'get' });
        if (j && j.ok && j.data !== null && j.data !== undefined) {
          const remote = JSON.stringify(j.data);
          if (localStorage.getItem(STORE_KEYS[key]) !== remote) {
            localStorage.setItem(STORE_KEYS[key], remote);
            changed = true;
          }
        }
      } catch (_) { /* offline — keep local */ }
    }
    if (changed) window.dispatchEvent(new CustomEvent('tst-sync'));
    return changed;
  }

  window.tstFamily = {
    code: famCode,
    // Joining: take the server copy where one exists, otherwise seed the
    // family with whatever this device already has.
    async join(rawCode) {
      const code = String(rawCode || '').trim().toUpperCase();
      if (!/^[A-Z0-9-]{6,24}$/.test(code)) return { error: 'Code must be 6–24 letters, numbers or dashes.' };
      localStorage.setItem(FAM_KEY, code);
      for (const key of ['shop', 'plan']) {
        try {
          const j = await famApi({ code, key, action: 'get' });
          if (j && j.ok) {
            if (j.data === null || j.data === undefined) await famPush(key);
            else localStorage.setItem(STORE_KEYS[key], JSON.stringify(j.data));
          }
        } catch (_) { /* offline — will sync when back online */ }
      }
      window.dispatchEvent(new CustomEvent('tst-sync'));
      return { ok: true };
    },
    leave() {
      localStorage.removeItem(FAM_KEY);
      localStorage.removeItem(DIRTY.shop);
      localStorage.removeItem(DIRTY.plan);
    },
    pull: famPull,
  };

  if (famCode()) {
    famPull();
    window.addEventListener('pageshow', (e) => { if (e.persisted) famPull(); });
    document.addEventListener('visibilitychange', () => { if (!document.hidden) famPull(); });
  }

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
