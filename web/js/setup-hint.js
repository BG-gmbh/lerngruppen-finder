(function () {
  fetch("/api/setup-status")
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      if (!data || !data.setup_needed) return;
      var el = document.getElementById("setup-hint");
      if (el) el.classList.remove("hidden");
    })
    .catch(function () {});
})();
