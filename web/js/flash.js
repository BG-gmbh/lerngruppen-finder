(function () {
  var params = new URLSearchParams(window.location.search);
  var code = params.get("flash");
  if (!code) return;

  var messages = {
    invalid: "Benutzername oder Passwort falsch.",
    shortuser: "Benutzername mindestens 3 Zeichen.",
    shortpass: "Passwort mindestens 6 Zeichen.",
    mismatch: "Passwörter stimmen nicht überein.",
    taken: "Dieser Benutzername ist schon vergeben.",
    logout: "Du bist ausgeloggt.",
    needlogin: "Bitte zuerst einloggen.",
    levels: "Bitte für jedes Fach Pro, Mittel oder Noob wählen.",
    saved: "Einstellungen gespeichert.",
    register_disabled: "Öffentliche Registrierung ist ausgeschaltet. Bitte Administrator oder Einladungscode.",
    admin_only: "Nur für Administratoren.",
    user_created: "Nutzer wurde angelegt.",
    setup_done: "Admin-Konto erstellt. Du bist eingeloggt.",
    bad_invite: "Ungültiger oder bereits benutzter Code.",
    redeem_ok: "Konto erstellt. Willkommen!",
  };

  var text = messages[code];
  if (!text) return;

  var ul = document.getElementById("flash-banner");
  if (!ul) return;

  var li = document.createElement("li");
  var cls =
    code === "saved" || code === "user_created" || code === "setup_done" || code === "redeem_ok"
      ? "flash-success"
      : code === "logout" || code === "register_disabled"
        ? "flash-info"
        : code === "needlogin"
          ? "flash-warning"
          : "flash-error";
  li.className = cls;
  li.textContent = text;
  ul.appendChild(li);

  try {
    var u = new URL(window.location.href);
    u.searchParams.delete("flash");
    window.history.replaceState({}, "", u.pathname + u.search);
  } catch (e) {}
})();
