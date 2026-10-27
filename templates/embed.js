/* doplatkyliekov.sk – vloženie kalkulačky doplatkov do iného webu.
   Použitie: <div data-doplatky></div><script src="https://doplatkyliekov.sk/vlozit/embed.js" async></script>
   Voliteľne data-tema="svetla" | "tmava". Výška okna sa nastaví podľa obsahu. Bez cookies. */
(function () {
  var src = (document.currentScript && document.currentScript.src) || 'https://doplatkyliekov.sk/vlozit/embed.js';
  var origin = new URL(src).origin, n = 0;
  function mount() {
    var nodes = document.querySelectorAll('[data-doplatky]:not([data-doplatky-ok])');
    for (var i = 0; i < nodes.length; i++) {
      var box = nodes[i], t = { svetla: 'light', tmava: 'dark' }[box.getAttribute('data-tema')] || '';
      var id = 'd' + (++n) + Math.random().toString(36).slice(2, 6), f = document.createElement('iframe');
      f.src = origin + '/vlozit/okno/?id=' + id + (t ? '&t=' + t : '');
      f.title = 'Porovnanie doplatkov za lieky – doplatkyliekov.sk';
      f.loading = 'lazy';
      f.setAttribute('data-id', id);
      f.style.cssText = 'width:100%;max-width:640px;height:300px;border:0;display:block;color-scheme:normal';
      box.setAttribute('data-doplatky-ok', '');
      box.appendChild(f);
    }
  }
  window.addEventListener('message', function (e) {
    if (e.origin !== origin || !e.data || typeof e.data.doplatkyH !== 'number') return;
    var f = document.querySelector('iframe[data-id="' + String(e.data.id).replace(/[^a-z0-9]/gi, '') + '"]');
    if (f) f.style.height = Math.min(Math.max(e.data.doplatkyH, 200), 1600) + 'px';
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
