/* Theme toggle + language switcher (Stage 3.5).
 * The no-flash inline script in base.html already set data-theme before paint.
 * This script syncs the toggle button's icon/label, persists the user's choice,
 * and auto-submits the language <select>. All progressive enhancement — without
 * JS the page still renders (just no toggle, and language needs a manual submit). */
(function () {
  "use strict";

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function syncButton(theme) {
    var btn = document.getElementById("theme-toggle");
    if (!btn) {
      return;
    }
    var isDark = theme === "dark";
    btn.setAttribute("aria-pressed", String(isDark));
    var icon = btn.querySelector("[data-theme-icon]");
    if (icon) {
      icon.textContent = isDark ? "☀" : "☾";
    }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("theme", theme);
    } catch (e) {}
    syncButton(theme);
  }

  function init() {
    syncButton(currentTheme());

    var btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        applyTheme(currentTheme() === "dark" ? "light" : "dark");
      });
    }

    // Auto-submit the language switcher on change (no inline handler / CSP-safe).
    var langSelect = document.querySelector("[data-lang-switcher]");
    if (langSelect) {
      langSelect.addEventListener("change", function () {
        if (langSelect.form) {
          langSelect.form.submit();
        }
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
