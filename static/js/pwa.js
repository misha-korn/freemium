/* Register the service worker for installability + an offline fallback.
 * No-ops where service workers aren't supported, so nothing breaks. */
(function () {
  "use strict";
  if (!("serviceWorker" in navigator)) {
    return;
  }
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/sw.js").catch(function () {
      /* Registration failures are non-fatal — the app still works online. */
    });
  });
})();
