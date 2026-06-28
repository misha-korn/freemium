/* Portfolio "value over time" chart.
 * Plots daily mark-to-market value against invested capital from stored
 * snapshots (Django {{ ...|json_script }}). A segmented range control
 * (1M/3M/6M/1Y/All) filters the series client-side. No-ops safely if Chart.js
 * failed to load or there is no data, so the page never breaks on a missing CDN. */
(function () {
  "use strict";

  var RANGES = [
    { key: "1m", days: 30 },
    { key: "3m", days: 91 },
    { key: "6m", days: 182 },
    { key: "1y", days: 365 },
    { key: "all", days: null },
  ];

  function filterPoints(points, days) {
    if (!days) {
      return points.slice();
    }
    var last = new Date(points[points.length - 1].date);
    var cutoff = new Date(last);
    cutoff.setDate(cutoff.getDate() - days);
    return points.filter(function (p) { return new Date(p.date) >= cutoff; });
  }

  function init() {
    var canvas = document.getElementById("portfolio-value-chart");
    var dataEl = document.getElementById("portfolio-value-chart-data");
    if (!canvas || !dataEl || typeof window.Chart === "undefined") {
      return;
    }

    var payload;
    try {
      payload = JSON.parse(dataEl.textContent);
    } catch (err) {
      return;
    }
    var points = (payload && payload.points) || [];
    if (points.length < 2) {
      return;
    }

    var styles = getComputedStyle(document.documentElement);
    var accent = (styles.getPropertyValue("--color-accent-strong") || "#0a7a6f").trim();
    var grid = (styles.getPropertyValue("--color-border") || "#e6e8eb").trim();
    var muted = (styles.getPropertyValue("--color-text-muted") || "#6b7280").trim();
    var cur = payload.base_currency || "";

    var chart = new window.Chart(canvas, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Market value (" + cur + ")",
            data: [],
            borderColor: accent,
            backgroundColor: "rgba(13, 148, 136, 0.12)",
            fill: true,
            tension: 0.25,
            borderWidth: 2,
            pointRadius: 2,
            pointHoverRadius: 5,
          },
          {
            label: "Invested (" + cur + ")",
            data: [],
            borderColor: muted,
            backgroundColor: "transparent",
            borderDash: [5, 4],
            fill: false,
            tension: 0.25,
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { labels: { color: muted } },
          tooltip: { intersect: false },
        },
        scales: {
          x: { grid: { color: grid }, ticks: { color: muted, maxTicksLimit: 8 } },
          y: { grid: { color: grid }, ticks: { color: muted }, beginAtZero: false },
        },
      },
    });

    function applyRange(days) {
      var pts = filterPoints(points, days);
      if (pts.length < 2) {
        pts = points;
      }
      chart.data.labels = pts.map(function (p) { return p.date; });
      chart.data.datasets[0].data = pts.map(function (p) { return Number(p.market_value); });
      chart.data.datasets[1].data = pts.map(function (p) { return Number(p.invested); });
      chart.update();
    }

    // Wire the segmented range control, hiding ranges the data can't fill.
    var seg = document.querySelector('[data-range-for="portfolio-value-chart"]');
    if (seg) {
      var buttons = Array.prototype.slice.call(seg.querySelectorAll(".seg__btn"));
      buttons.forEach(function (btn) {
        var key = btn.getAttribute("data-range");
        var range = null;
        RANGES.forEach(function (r) { if (r.key === key) { range = r; } });
        if (range && range.days) {
          var count = filterPoints(points, range.days).length;
          if (count < 2 || count >= points.length) {
            btn.hidden = true;
            return;
          }
        }
        btn.addEventListener("click", function () {
          buttons.forEach(function (b) { b.classList.remove("is-active"); });
          btn.classList.add("is-active");
          applyRange(range ? range.days : null);
        });
      });
    }

    applyRange(null);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
