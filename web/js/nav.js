(function () {
  var guest = document.getElementById("nav-guest");
  var user = document.getElementById("nav-user");
  if (!guest || !user) return;

  fetch("/api/me", { credentials: "same-origin" })
    .then(function (r) {
      if (!r.ok) throw new Error();
      return r.json();
    })
    .then(function (data) {
      guest.classList.add("hidden");
      user.classList.remove("hidden");
      var nameEl = document.getElementById("nav-username");
      if (nameEl && data.username) nameEl.textContent = data.username;
      var adminEl = document.getElementById("nav-admin");
      if (adminEl) {
        if (data.role === "teacher" || data.role === "admin" || data.role === "dev") {
          adminEl.classList.remove("hidden");
        }
        else adminEl.classList.add("hidden");
      }
    })
    .catch(function () {
      user.classList.add("hidden");
      guest.classList.remove("hidden");
    });
})();
