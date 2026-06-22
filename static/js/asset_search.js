// Ticker autocomplete for the asset form. As the user types, query the market
// provider (MOEX / Finnhub) via the search endpoint and show a custom dropdown
// of matching tickers that narrows as you type. Click or Enter to pick one — it
// fills the ticker and, when empty, the Name field. Results respect the selected
// Market and Asset type.
(function () {
  "use strict";

  var url = window.SYMBOL_SEARCH_URL;
  var ticker = document.getElementById("id_ticker");
  if (!url || !ticker) return;

  var market = document.getElementById("id_market");
  var atype = document.getElementById("id_asset_type");
  var nameField = document.getElementById("id_name");

  // Build a dropdown positioned under the ticker input.
  var field = ticker.closest(".field") || ticker.parentNode;
  field.style.position = "relative";
  var box = document.createElement("ul");
  box.className = "ac-list";
  box.setAttribute("role", "listbox");
  box.hidden = true;
  field.appendChild(box);

  var items = [];
  var active = -1;
  var timer = null;

  function close() {
    box.hidden = true;
    box.innerHTML = "";
    items = [];
    active = -1;
  }

  function choose(item) {
    ticker.value = item.ticker;
    if (nameField && !nameField.value) nameField.value = item.name || "";
    close();
  }

  function render() {
    box.innerHTML = "";
    if (!items.length) {
      box.hidden = true;
      return;
    }
    items.forEach(function (item, i) {
      var li = document.createElement("li");
      li.className = "ac-item" + (i === active ? " is-active" : "");
      li.setAttribute("role", "option");

      var t = document.createElement("span");
      t.className = "ac-ticker";
      t.textContent = item.ticker;
      var n = document.createElement("span");
      n.className = "ac-name";
      n.textContent = item.name || "";
      li.appendChild(t);
      li.appendChild(n);

      // mousedown (not click) so it fires before the input loses focus.
      li.addEventListener("mousedown", function (e) {
        e.preventDefault();
        choose(item);
      });
      box.appendChild(li);
    });
    box.hidden = false;
  }

  function load() {
    var q = ticker.value.trim();
    if (q.length < 1) {
      close();
      return;
    }
    var m = market ? market.value : "";
    var ty = atype ? atype.value : "";
    fetch(
      url +
        "?q=" + encodeURIComponent(q) +
        "&market=" + encodeURIComponent(m) +
        "&type=" + encodeURIComponent(ty),
      { headers: { "X-Requested-With": "XMLHttpRequest" } }
    )
      .then(function (r) {
        return r.ok ? r.json() : { results: [] };
      })
      .then(function (data) {
        items = data.results || [];
        active = -1;
        render();
      })
      .catch(close);
  }

  ticker.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(load, 250);
  });
  ticker.addEventListener("focus", function () {
    if (items.length) render();
    else if (ticker.value.trim()) load();
  });
  ticker.addEventListener("keydown", function (e) {
    if (box.hidden || !items.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      active = Math.min(active + 1, items.length - 1);
      render();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      active = Math.max(active - 1, 0);
      render();
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault();
      choose(items[active]);
    } else if (e.key === "Escape") {
      close();
    }
  });

  if (market) market.addEventListener("change", load);
  if (atype) atype.addEventListener("change", load);
  document.addEventListener("click", function (e) {
    if (!field.contains(e.target)) close();
  });
})();
