(() => {
  const entries = Array.isArray(window.COMPENDIUM_INDEX) ? window.COMPENDIUM_INDEX : [];

  const body = document.body;
  const sidebar = document.getElementById('sidebar');
  const menuButton = document.querySelector('[data-menu-toggle]');
  const overlay = document.querySelector('[data-overlay]');
  const input = document.getElementById('compendium-search');
  const results = document.getElementById('search-results');

  const setMenu = open => {
    body.classList.toggle('menu-open', open);
    if (menuButton) menuButton.setAttribute('aria-expanded', String(open));
    if (sidebar) sidebar.setAttribute('aria-hidden', String(!open && matchMedia('(max-width: 760px)').matches));
  };

  menuButton?.addEventListener('click', () => setMenu(!body.classList.contains('menu-open')));
  overlay?.addEventListener('click', () => setMenu(false));
  addEventListener('resize', () => {
    if (innerWidth > 760) {
      body.classList.remove('menu-open');
      sidebar?.setAttribute('aria-hidden', 'false');
    }
  });

  const closeResults = () => {
    results?.classList.remove('open');
    input?.setAttribute('aria-expanded', 'false');
  };

  const renderResults = query => {
    if (!results || !input) return;
    const value = query.trim().toLowerCase();
    if (!value) {
      closeResults();
      results.replaceChildren();
      return;
    }
    const found = entries.filter(entry => `${entry.title} ${entry.note} ${entry.tags}`.toLowerCase().includes(value)).slice(0, 7);
    results.replaceChildren();
    if (!found.length) {
      const empty = document.createElement('div');
      empty.className = 'search-empty';
      empty.textContent = 'No matching entries in the current save.';
      results.append(empty);
    } else {
      for (const entry of found) {
        const link = document.createElement('a');
        link.href = entry.url;
        const title = document.createElement('strong');
        title.textContent = entry.title;
        const note = document.createElement('small');
        note.textContent = entry.note;
        link.append(title, note);
        results.append(link);
      }
    }
    results.classList.add('open');
    input.setAttribute('aria-expanded', 'true');
  };

  input?.addEventListener('input', event => renderResults(event.target.value));
  input?.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      input.value = '';
      closeResults();
      input.blur();
    }
    if (event.key === 'Enter') {
      const first = results?.querySelector('a');
      if (first) location.href = first.href;
    }
  });

  document.addEventListener('click', event => {
    if (!event.target.closest('.search')) closeResults();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      setMenu(false);
      closeResults();
    }
    const target = event.target;
    const typing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target?.isContentEditable;
    if (!typing && (event.key === '/' || (event.ctrlKey && event.key.toLowerCase() === 'k'))) {
      event.preventDefault();
      input?.focus();
    }
  });
})();
