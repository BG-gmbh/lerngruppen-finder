// Blockierendes Popup: erscheint, wenn eine Admin-Person das Passwort
// zurueckgesetzt und "Passwort dauerhaft" NICHT angehakt hat. Der Nutzer
// muss dann ein eigenes neues Passwort setzen, bevor er weitermachen kann.
(function () {
  var cfg = window.APP_CONFIG || {};
  var apiUrl = typeof cfg.resolveApiUrl === "function"
    ? cfg.resolveApiUrl("/api/me")
    : "/api/me";

  function postUrl(path) {
    return typeof cfg.resolveApiUrl === "function" ? cfg.resolveApiUrl(path) : path;
  }

  function field(form, labelText, inputName) {
    var wrap = document.createElement("div");
    wrap.className = "modal-field";
    var label = document.createElement("label");
    label.textContent = labelText;
    var input = document.createElement("input");
    input.type = "password";
    input.className = "modal-input";
    input.name = inputName;
    input.required = true;
    input.minLength = 6;
    input.autocomplete = inputName === "current_password" ? "current-password" : "new-password";
    label.appendChild(input);
    wrap.appendChild(label);
    form.appendChild(wrap);
    return input;
  }

  function showModal() {
    if (document.getElementById("mcp-backdrop")) return;
    var backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.id = "mcp-backdrop";

    var card = document.createElement("div");
    card.className = "modal-card";

    var title = document.createElement("h2");
    title.className = "modal-title";
    title.textContent = "Neues Passwort erforderlich";
    card.appendChild(title);

    var hint = document.createElement("p");
    hint.className = "modal-hint";
    hint.textContent = "Dein Passwort wurde von einer Admin-Person zurückgesetzt. Bitte setze jetzt ein eigenes neues Passwort, um fortzufahren.";
    card.appendChild(hint);

    var error = document.createElement("p");
    error.className = "modal-error";
    card.appendChild(error);

    var form = document.createElement("form");
    var curInput = field(form, "Aktuelles Passwort (von der Admin-Person erhalten)", "current_password");
    var newInput = field(form, "Neues Passwort (mind. 6 Zeichen)", "new_password");
    var newInput2 = field(form, "Neues Passwort bestätigen", "new_password_confirm");

    var actions = document.createElement("div");
    actions.className = "modal-actions";
    var submitBtn = document.createElement("button");
    submitBtn.type = "submit";
    submitBtn.className = "btn btn-primary";
    submitBtn.textContent = "Passwort setzen";
    actions.appendChild(submitBtn);
    form.appendChild(actions);

    var ERROR_MESSAGES = {
      pwd_current_wrong: "Das aktuelle Passwort ist falsch.",
      shortpass: "Das neue Passwort muss mindestens 6 Zeichen lang sein.",
      mismatch: "Die Passwörter stimmen nicht überein.",
      pwd_incomplete: "Bitte alle Felder ausfüllen.",
    };

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      error.textContent = "";
      if (newInput.value.length < 6) {
        error.textContent = ERROR_MESSAGES.shortpass;
        return;
      }
      if (newInput.value !== newInput2.value) {
        error.textContent = ERROR_MESSAGES.mismatch;
        return;
      }
      submitBtn.disabled = true;
      fetch(postUrl("/api/must-change-password"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_password: curInput.value,
          new_password: newInput.value,
          new_password_confirm: newInput2.value,
        }),
      })
        .then(function (r) {
          return r.json().then(function (d) { return { ok: r.ok, d: d }; });
        })
        .then(function (res) {
          submitBtn.disabled = false;
          if (!res.ok) {
            error.textContent = ERROR_MESSAGES[res.d && res.d.error] || "Passwort konnte nicht gesetzt werden.";
            return;
          }
          backdrop.remove();
        })
        .catch(function () {
          submitBtn.disabled = false;
          error.textContent = "Netzwerkfehler. Bitte erneut versuchen.";
        });
    });

    card.appendChild(form);
    backdrop.appendChild(card);
    document.body.appendChild(backdrop);
  }

  fetch(apiUrl, { credentials: "include" })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (data) {
      if (data && data.must_change_password) showModal();
    })
    .catch(function () {});
})();
