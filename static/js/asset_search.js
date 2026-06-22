// Ticker autocomplete for the asset form. As the user types a ticker, query the
// market provider (MOEX / Finnhub) via /alerts/search/ and offer suggestions in
// a native <datalist>. Picking one fills the Name field when it's empty.
(function () {
  "use strict";

  var url = window.SYMBOL_SEARCH_URL;
  var ticker = document.getElementById("id_ticker");
  var market = document.getElementById("id_market");
  var nameField = document.getElementById("id_name");
  var list = document.getElementById("ticker-suggestions");
  if (!url || !ticker || !list) return;

  var nameByTicker = {};
  var timer = null;

  function fetchSuggestions() {
    var q = ticker.value.trim();
    var m = market ? market.value : "";
    if (q.length < 1) {
      list.innerHTML = "";
      return;
    }
    fetch(
      url + "?q=" + encodeURIComponent(q) + "&market=" + encodeURIComponent(m),
      { headers: { "X-Requested-With": "XMLHttpRequest" } }
    )
      .then(function (r) {
        return r.ok ? r.json() : { results: [] };
      })
      .then(function (data) {
        list.innerHTML = "";
        nameByTicker = {};
        (data.results || []).forEach(function (item) {
          var opt = document.createElement("option");
          opt.value = item.ticker;
          opt.label = item.name;
          list.appendChild(opt);
          nameByTicker[String(item.ticker).toUpperCase()] = item.name;
        });
      })
      .catch(function () {
        /* network/parse error — leave suggestions as-is */
      });
  }

  ticker.addEventListener("input", function () {
    // If the current value exactly matches a suggestion and Name is empty, fill it.
    var picked = nameByTicker[ticker.value.trim().toUpperCase()];
    if (picked && nameField && !nameField.value) {
      nameField.value = picked;
    }
    clearTimeout(timer);
    timer = setTimeout(fetchSuggestions, 300);
  });

  if (market) {
    market.addEventListener("change", fetchSuggestions);
  }
})();
