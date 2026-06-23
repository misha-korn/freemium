/* Portfolio "value over time" chart.
 * Plots daily mark-to-market value against invested capital from stored
 * snapshots (Django {{ ...|json_script }}). No-ops safely if Chart.js failed to
 * load or there is no data, so the page never breaks on a missing CDN. */
(function () {
  "use strict";

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

    new window.Chart(canvas, {
      type: "line",
      data: {
        labels: points.map(function (p) { return p.date; }),
        datasets: [
          {
            label: "Market value (" + cur + ")",
            data: points.map(function (p) { return Number(p.market_value); }),
            borderColor: accent,
            backgroundColor: "rgba(13, 148, 136, 0.12)",
            fill: true,
            tension: 0.25,
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
          {
            label: "Invested (" + cur + ")",
            data: points.map(function (p) { return Number(p.invested); }),
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
          x: { grid: { color: grid }, ticks: { color: muted } },
          y: { grid: { color: grid }, ticks: { color: muted }, beginAtZero: false },
        },
      },
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
