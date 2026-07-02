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
      } else {
        el.classList.add("hidden");
      }
    })
    .catch(function () {});
})();
