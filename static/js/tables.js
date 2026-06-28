/* Sortable tables (positions, transactions, dividends).
 * Opt-in: add class "table--sortable" to a <table> and data-sort="num|text" to
 * the <th> headers that should sort. A cell's sort key is data-sort-value if
 * present, else its text. Progressive enhancement — without JS the table is a
 * plain, server-ordered table. CSP-safe: no inline handlers. */
(function () {
  "use strict";

  var ARROW = { none: "↕", ascending: "↑", descending: "↓" };

  function cellKey(row, index, kind) {
    var cell = row.children[index];
    if (!cell) {
      return kind === "num" ? -Infinity : "";
    }
    var raw = cell.getAttribute("data-sort-value");
    if (raw === null) {
      raw = cell.textContent.trim();
    }
    if (kind === "num") {
      var n = parseFloat(String(raw).replace(/[^0-9.+-]/g, ""));
      return isNaN(n) ? -Infinity : n;
    }
    return String(raw).toLowerCase();
  }

  function sortBy(table, index, kind, dir) {
    var tbody = table.tBodies[0];
    if (!tbody) {
      return;
    }
    var rows = Array.prototype.slice.call(tbody.rows);
    var factor = dir === "ascending" ? 1 : -1;
    rows.sort(function (a, b) {
      var ka = cellKey(a, index, kind);
      var kb = cellKey(b, index, kind);
      if (ka < kb) { return -1 * factor; }
      if (ka > kb) { return 1 * factor; }
      return 0;
    });
    rows.forEach(function (row) { tbody.appendChild(row); });
  }

  function decorate(th) {
    var ind = document.createElement("span");
    ind.className = "sort-ind";
    ind.setAttribute("aria-hidden", "true");
    ind.textContent = ARROW.none;
    th.appendChild(ind);
    th.classList.add("sortable");
    th.setAttribute("aria-sort", "none");
    return ind;
  }

  function wire(table) {
    var headers = table.querySelectorAll("thead th[data-sort]");
    headers.forEach(function (th, i) {
      var index = Array.prototype.indexOf.call(th.parentNode.children, th);
      var kind = th.getAttribute("data-sort") || "text";
      var ind = decorate(th);

      function activate() {
        var current = th.getAttribute("aria-sort");
        var dir = current === "ascending" ? "descending" : "ascending";
        headers.forEach(function (other) {
          other.setAttribute("aria-sort", "none");
          var oi = other.querySelector(".sort-ind");
          if (oi) { oi.textContent = ARROW.none; }
        });
        th.setAttribute("aria-sort", dir);
        ind.textContent = ARROW[dir];
        sortBy(table, index, kind, dir);
      }

      th.tabIndex = 0;
      th.setAttribute("role", "button");
      th.addEventListener("click", activate);
      th.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          activate();
        }
      });
    });
  }

  function init() {
    document.querySelectorAll("table.table--sortable").forEach(wire);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
