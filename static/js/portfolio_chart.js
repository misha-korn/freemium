/* Portfolio "invested capital over time" chart.
 * Reads JSON embedded via Django's {{ ...|json_script }} and renders a line
 * chart with Chart.js. No-ops safely if Chart.js failed to load or there is no
 * data, so the page never breaks on a missing CDN. */
(function () {
  "use strict";

  function init() {
    var canvas = document.getElementById("portfolio-chart");
    var dataEl = document.getElementById("portfolio-chart-data");
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
    if (!points.length) {
      return;
    }

    var styles = getComputedStyle(document.documentElement);
    var accent = (styles.getPropertyValue("--color-accent-strong") || "#0a7a6f").trim();
    var grid = (styles.getPropertyValue("--color-border") || "#e6e8eb").trim();
    var muted = (styles.getPropertyValue("--color-text-muted") || "#6b7280").trim();

    new window.Chart(canvas, {
      type: "line",
      data: {
        labels: points.map(function (p) { return p.date; }),
        datasets: [{
          label: "Invested (" + (payload.base_currency || "") + ")",
          data: points.map(function (p) { return Number(p.invested); }),
          borderColor: accent,
          backgroundColor: "rgba(13, 148, 136, 0.12)",
          fill: true,
          tension: 0.25,
          borderWidth: 2,
          pointRadius: 3,
          pointHoverRadius: 5,
        }],
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
          y: { grid: { color: grid }, ticks: { color: muted }, beginAtZero: true },
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
