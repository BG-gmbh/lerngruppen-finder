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
    })
    .catch(function () {
      user.classList.add("hidden");
      guest.classList.remove("hidden");
    });
})();
