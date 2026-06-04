/* Portfolio allocation donut charts (Stage 3).
 * Each <canvas data-source="..."> points at a {{ ...|json_script }} element
 * holding {labels, values(percent)}. Renders a doughnut and colours the
 * server-rendered legend swatches to match. No-ops safely if Chart.js failed
 * to load or there is no data, so the page never breaks on a missing CDN. */
(function () {
  "use strict";

  // Distinct, accessible-ish palette; cycles if an axis has many slices.
  var PALETTE = [
    "#0d9488", "#0ea5e9", "#6366f1", "#f59e0b",
    "#f43f5e", "#10b981", "#8b5cf6", "#ec4899",
    "#14b8a6", "#64748b",
  ];

  function colorAt(i) {
    return PALETTE[i % PALETTE.length];
  }

  function paintLegend(domId, colors) {
    var legend = document.querySelector('[data-legend-for="' + domId + '"]');
    if (!legend) {
      return;
    }
    legend.querySelectorAll("[data-i]").forEach(function (swatch) {
      var i = Number(swatch.getAttribute("data-i"));
      swatch.style.backgroundColor = colorAt(i);
    });
  }

  function renderDonut(canvas) {
    var dataEl = document.getElementById(canvas.dataset.source);
    if (!dataEl || typeof window.Chart === "undefined") {
      return;
    }

    var payload;
    try {
      payload = JSON.parse(dataEl.textContent);
    } catch (err) {
      return;
    }
    var labels = (payload && payload.labels) || [];
    var values = (payload && payload.values) || [];
    if (!labels.length) {
      return;
    }

    var colors = labels.map(function (_, i) { return colorAt(i); });

    new window.Chart(canvas, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderColor: "#ffffff",
          borderWidth: 2,
          hoverOffset: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return " " + ctx.label + ": " + Number(ctx.parsed).toFixed(1) + "%";
              },
            },
          },
        },
      },
    });

    paintLegend(canvas.id, colors);
  }

  function init() {
    document.querySelectorAll("canvas[data-source]").forEach(renderDonut);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
