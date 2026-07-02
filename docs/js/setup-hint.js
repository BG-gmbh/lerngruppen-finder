(function () {
  fetch("/api/setup-status")
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      var el = document.getElementById("setup-hint");
      if (!el) return;
      if (data && data.setup_needed) {
        el.classList.remove("hidden");
        el.removeAttribute("aria-disabled");
      } else if (el.tagName === "A") {
        el.setAttribute("aria-disabled", "true");
        el.title = "Nur verfügbar, wenn kein Admin existiert.";
      }
    })
    .catch(function () {});
})();
