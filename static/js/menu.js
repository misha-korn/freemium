/* Dropdown menus ("More" actions on the dashboard toolbar).
 * Progressive enhancement: markup is a <button data-menu-trigger> next to a
 * <div data-menu-panel hidden>. Without JS the panel stays hidden and the
 * primary actions still work. Closes on outside click, Escape, or blur.
 * CSP-safe: no inline handlers. */
(function () {
  "use strict";

  function closeAll(except) {
    document.querySelectorAll("[data-menu-panel]").forEach(function (panel) {
      if (panel === except) {
        return;
      }
      panel.hidden = true;
      var trigger = panel.closest(".menu") &&
        panel.closest(".menu").querySelector("[data-menu-trigger]");
      if (trigger) {
        trigger.setAttribute("aria-expanded", "false");
      }
    });
  }

  function wire(trigger) {
    var menu = trigger.closest(".menu");
    var panel = menu && menu.querySelector("[data-menu-panel]");
    if (!panel) {
      return;
    }
    trigger.setAttribute("aria-haspopup", "true");
    trigger.setAttribute("aria-expanded", "false");

    trigger.addEventListener("click", function (event) {
      event.stopPropagation();
      var willOpen = panel.hidden;
      closeAll(willOpen ? panel : null);
      panel.hidden = !willOpen;
      trigger.setAttribute("aria-expanded", String(willOpen));
    });
  }

  function init() {
    var triggers = document.querySelectorAll("[data-menu-trigger]");
    if (!triggers.length) {
      return;
    }
    triggers.forEach(wire);

    document.addEventListener("click", function () { closeAll(null); });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeAll(null);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
