// Zeigt oben rechts im Header das von der Schule (bzw. von Devs) hinterlegte
// Logo an. Holt sich die URL aus /api/me (school_logo_url) und haengt ein
// <img class="school-logo"> ans Ende der Navigation. Ist nichts gesetzt oder
// der Nutzer nicht eingeloggt, passiert nichts.
(function () {
  var cfg = window.APP_CONFIG || {};
  var apiUrl = typeof cfg.resolveApiUrl === "function"
    ? cfg.resolveApiUrl("/api/me")
    : "/api/me";

  fetch(apiUrl, { credentials: "include" })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (data) {
      if (!data) return;
      var url = data.school_logo_url;
      if (!url) return;
      var header = document.querySelector(".site-header");
      if (!header || header.querySelector(".school-logo")) return;
      var img = document.createElement("img");
      img.className = "school-logo";
      img.src = url;
      img.alt = (data.school || "Schule") + " Logo";
      // Kaputte URL: Element wieder entfernen, statt ein defektes Bild zu zeigen.
      img.addEventListener("error", function () { img.remove(); });
      var nav = header.querySelector("nav");
      (nav || header).appendChild(img);
    })
    .catch(function () {});
})();
