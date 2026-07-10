(function () {
  var POLL_ROOMS_MS = 4000;
  var POLL_MSG_MS = 2500;
  var currentSubject = null;
  var sinceId = 0;
  var roomsTimer = null;
  var msgTimer = null;
  var appointmentTimer = null;
  var maxUsers = 5;
  var userLevels = null;
  var userRole = null;
  var lastAppointmentUiKey = null;
  var creatableSubjects = [];
  var subjects = [
    ["german", "Deutsch"],
    ["math", "Mathe"],
    ["english", "Englisch"],
    ["biology", "Biologie"],
    ["pgw", "PGW"],
    ["spanish", "Spanisch"],
    ["art", "Kunst"],
  ];

  function $(id) {
    return document.getElementById(id);
  }

  function esc(s) {
    if (s == null) return "";
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function api(path, opts) {
    var cfg = window.APP_CONFIG || {};
    var basePath = typeof cfg.resolveApiUrl === "function" ? cfg.resolveApiUrl(path) : path;
    opts = opts || {};
    opts.credentials = "include";
    opts.headers = opts.headers || {};
    if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    return fetch(basePath, opts).then(function (r) {
      return r.json().then(function (data) {
        return { ok: r.ok, status: r.status, data: data };
      });
    });
  }

  function stopMsgPoll() {
    if (msgTimer) {
      clearInterval(msgTimer);
      msgTimer = null;
    }
  }

  function stopAppointmentPoll() {
    if (appointmentTimer) {
      clearInterval(appointmentTimer);
      appointmentTimer = null;
    }
  }

  function stopRoomsPoll() {
    if (roomsTimer) {
      clearInterval(roomsTimer);
      roomsTimer = null;
    }
  }

  function setLobbyError(text) {
    var el = $("lobby-error");
    if (el) el.textContent = text || "";
  }

  function renderLobby(rooms) {
    var host = $("room-cards");
    if (!host) return;
    host.innerHTML = "";
    rooms.forEach(function (room) {
      var card = document.createElement("article");
      card.className =
        "room-card" + (room.full || room.can_join === false ? " room-card-full" : "");

      var h = document.createElement("h3");
      h.textContent = room.label;
      card.appendChild(h);

      var meta = document.createElement("p");
      meta.className = "room-meta";
      var np =
        room.count_non_pro != null ? room.count_non_pro : room.count || 0;
      var total = room.count != null ? room.count : 0;
      var extra = total > np ? " · " + total + " online (inkl. Pro)" : "";
      meta.textContent =
        np +
        " / " +
        (room.max || 5) +
        " ohne Pro" +
        extra +
        (room.has_pro === false && total > 0
          ? " — noch kein Pro online"
          : room.has_pro === false
            ? " — mind. 1× Pro nötig für Beitritt"
            : "");
      card.appendChild(meta);

      var ul = document.createElement("ul");
      ul.className = "room-members";
      room.members.forEach(function (m) {
        var li = document.createElement("li");
        var lv =
          m.level === "pro" ? "Pro" : m.level === "medium" ? "Mittel" : "Noob";
        li.textContent = m.username + " (" + lv + ")";
        ul.appendChild(li);
      });
      card.appendChild(ul);
      if (room.appointment) {
        var app = document.createElement("p");
        app.className = "room-appointment";
        app.textContent =
          "Termin: " +
          room.appointment +
          (room.location ? " · Ort: " + room.location : "");
        card.appendChild(app);
      }

      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-block";
      if (room.you_in) {
        btn.textContent = "Chat fortsetzen";
      } else if (room.can_join === false) {
        btn.textContent =
          room.join_block === "full"
            ? "Raum voll"
            : room.join_block === "started"
              ? "Raum geschlossen"
            : room.join_block === "need_pro"
              ? "Warte auf Pro"
              : "Beitreten nicht möglich";
        btn.disabled = true;
      } else if (room.full) {
        btn.textContent = "Raum voll";
        btn.disabled = true;
      } else {
        btn.textContent = "Beitreten";
      }
      btn.addEventListener("click", function () {
        if (!btn.disabled) openSubject(room.subject);
      });
      card.appendChild(btn);

      host.appendChild(card);
    });
  }

  function loadRooms() {
    return api("/api/chat/rooms", { method: "GET" }).then(function (res) {
      if (res.status === 401) {
        window.location.replace("/login.html?next=/chat.html&flash=needlogin");
        return;
      }
      if (!res.ok || !res.data.rooms) return;
      maxUsers = res.data.rooms[0] && res.data.rooms[0].max ? res.data.rooms[0].max : 5;
      var lbl = $("max-users-label");
      if (lbl) lbl.textContent = String(maxUsers);
      creatableSubjects = res.data.creatable || [];
      renderLobby(res.data.rooms);
      showCreateRoomButton();
    });
  }

  function appendMessages(items, scrollBottom) {
    var box = $("chat-messages");
    if (!box) return;
    var atBottom =
      scrollBottom ||
      box.scrollHeight - box.scrollTop - box.clientHeight < 80;
    items.forEach(function (m) {
      var wrap = document.createElement("div");
      wrap.className = "chat-msg" + (m.user_id === window.__uid ? " chat-msg-own" : "");
      wrap.setAttribute("data-id", m.id);
      var head = document.createElement("div");
      head.className = "chat-msg-head";
      head.innerHTML =
        "<strong>" +
        esc(m.username) +
        "</strong> <span class=\"chat-msg-time\">" +
        esc(m.created_at) +
        "</span>";
      var body = document.createElement("div");
      body.className = "chat-msg-body";
      body.textContent = m.body;
      wrap.appendChild(head);
      wrap.appendChild(body);
      if (m.user_id !== window.__uid) {
        var reportBtn = document.createElement("button");
        reportBtn.className = "btn btn-ghost btn-small";
        reportBtn.textContent = "Melden";
        reportBtn.onclick = function () {
          reportMessage(m.id);
        };
        wrap.appendChild(reportBtn);
      }
      if (userRole === "teacher" || userRole === "admin" || userRole === "dev") {
        var deleteBtn = document.createElement("button");
        deleteBtn.className = "btn btn-ghost btn-small";
        deleteBtn.textContent = "Löschen";
        deleteBtn.onclick = function() { deleteMessage(m.id); };
        wrap.appendChild(deleteBtn);
      }
      box.appendChild(wrap);
      if (m.id > sinceId) sinceId = m.id;
    });
    if (atBottom) box.scrollTop = box.scrollHeight;
  }

  function fetchMessages() {
    if (!currentSubject) return;
    var q = "?subject=" + encodeURIComponent(currentSubject) + "&since=" + sinceId;
    var beforeSince = sinceId;
    api("/api/chat/messages" + q, { method: "GET" }).then(function (res) {
      if (res.status === 403) {
        leaveRoomUi(true);
        if (res.data && res.data.error === "need_pro") {
          setLobbyError(
            "Im Raum ist gerade kein Pro online. Ohne mindestens einen Pro kann der Chat nicht genutzt werden."
          );
        } else {
          setLobbyError("Du warst nicht mehr im Raum. Bitte erneut beitreten.");
        }
        return;
      }
      if (res.data && res.data.error === "appointment_ended") {
        clearMessagesUi();
        loadAppointment();
        return;
      }
      if (!res.ok || !res.data.messages) {
        return;
      }
      if (res.data.messages.length)
        appendMessages(res.data.messages, beforeSince === 0);
    });
  }

  function openSubject(subject) {
    setLobbyError("");
    api("/api/chat/join", { method: "POST", body: { subject: subject } }).then(function (res) {
      if (res.status === 409) {
        setLobbyError("Dieser Raum ist voll (" + maxUsers + " Plätze ohne Pro). Versuch es gleich nochmal.");
        loadRooms();
        return;
      }
      if (res.status === 403 && res.data && res.data.error === "need_pro") {
        setLobbyError(
          "Beitreten nicht möglich: Es muss schon mindestens ein Pro im Raum sein. Bitte warten oder selbst als Pro beitreten."
        );
        loadRooms();
        return;
      }
      if (!res.ok) {
        setLobbyError("Beitreten fehlgeschlagen.");
        return;
      }
      currentSubject = subject;
      sinceId = 0;
      $("chat-messages").innerHTML = "";
      $("lobby").classList.add("hidden");
      $("chat-panel").classList.remove("hidden");
      var labels = {
        german: "Deutsch",
        math: "Mathe",
        english: "Englisch",
        biology: "Biologie",
        pgw: "PGW",
        spanish: "Spanisch",
        art: "Kunst",
      };
      $("chat-title").textContent = "Chat: " + (labels[subject] || subject);
      stopRoomsPoll();
      stopMsgPoll();
      stopAppointmentPoll();
      lastAppointmentUiKey = null;
      fetchMessages();
      loadAppointment();
      msgTimer = setInterval(fetchMessages, POLL_MSG_MS);
      appointmentTimer = setInterval(loadAppointment, 8000);
      $("chat-input").focus();
    });
  }

  function leaveRoomUi(silent) {
    stopMsgPoll();
    stopAppointmentPoll();
    lastAppointmentUiKey = null;
    currentSubject = null;
    sinceId = 0;
    clearMessagesUi();
    $("chat-panel").classList.add("hidden");
    $("lobby").classList.remove("hidden");
    if (!silent) setLobbyError("");
    stopRoomsPoll();
    roomsTimer = setInterval(loadRooms, POLL_ROOMS_MS);
    loadRooms();
  }

  function leaveRoomNetwork() {
    if (!currentSubject) return;
    var sub = currentSubject;
    return api("/api/chat/leave", { method: "POST", body: { subject: sub } }).then(function () {
      leaveRoomUi(false);
    });
  }

  function sendMessage(e) {
    e.preventDefault();
    var input = $("chat-input");
    if (!input || !currentSubject) return;
    var body = (input.value || "").trim();
    if (!body) return;
    input.value = "";
    api("/api/chat/send", {
      method: "POST",
      body: { subject: currentSubject, body: body },
    }).then(function (res) {
      if (!res.ok) {
        if (!(res.data && res.data.error === "appointment_ended")) {
          input.value = body;
        }
        if (res.status === 403 && res.data && res.data.error === "need_pro") {
          leaveRoomUi(true);
          setLobbyError(
            "Es ist kein Pro mehr im Raum. Der Chat ist für dich vorerst beendet — bitte erneut beitreten, wenn ein Pro da ist."
          );
        } else if (res.data && res.data.error === "appointment_ended") {
          clearMessagesUi();
          loadAppointment();
          setLobbyError("Der Termin ist beendet. Der Chat wurde geleert.");
        }
        return;
      }
      fetchMessages();
    });
  }

  function reportMessage(id) {
    var reason = window.prompt("Warum möchtest du diese Nachricht melden? (optional)", "");
    if (reason === null) return;
    reason = (reason || "").trim();
    if (reason.length > 300) {
      setLobbyError("Der Meldegrund darf höchstens 300 Zeichen lang sein.");
      return;
    }
    api("/api/chat/report-message", {
      method: "POST",
      body: { message_id: id, reason: reason },
    }).then(function (res) {
      if (res.ok) {
        setLobbyError("Nachricht wurde gemeldet.");
      } else if (res.data && res.data.error === "already_reported") {
        setLobbyError("Du hast diese Nachricht schon gemeldet.");
      } else {
        setLobbyError("Melden fehlgeschlagen.");
      }
    });
  }

  function deleteMessage(id) {
    if (!confirm("Nachricht wirklich löschen?")) return;
    api("/api/admin/delete_message/" + id, { method: "DELETE" }).then(function (res) {
      if (res.ok) {
        var msg = document.querySelector('.chat-msg[data-id="' + id + '"]');
        if (msg) msg.remove();
      } else {
        alert("Fehler beim Löschen: " + (res.data.error || "Unbekannt"));
      }
    });
  }

  function stableAppointmentKey(data, hasProRight) {
    var yr = null;
    if (hasProRight && data && data.your_rating) {
      yr = {
        r: data.your_rating.rating,
        c: data.your_rating.comment || "",
      };
    }
    var rid = null;
    if (hasProRight && data && data.ended && data.ratings) {
      rid = data.ratings.map(function (x) {
        return [x.username, x.rating, x.comment || ""];
      });
    }
    return JSON.stringify({
      appointment: data && data.appointment ? data.appointment : null,
      location: data && data.location ? data.location : null,
      started: !!(data && data.started),
      ended: !!(data && data.ended),
      yr: yr,
      pro: !!hasProRight,
      rid: rid,
    });
  }

  function ratingSelectOptions(yourRating) {
    var opts = "";
    var current = yourRating && yourRating.rating ? parseInt(yourRating.rating, 10) : 5;
    for (var s = 1; s <= 5; s++) {
      opts +=
        '<option value="' +
        s +
        '"' +
        (s === current ? " selected" : "") +
        ">" +
        s +
        "</option>";
    }
    return opts;
  }

  function updateAppointmentUi(data) {
    var container = $("chat-appointment");
    if (!container) return;
    if (data && data.ended) {
      clearMessagesUi();
    }
    var content = "";
    if (data && data.appointment) {
      content +=
        '<p class="chat-appointment-text"><strong>Termin:</strong> ' +
        esc(data.appointment) +
        "</p>";
      content +=
        '<p class="chat-appointment-text"><strong>Ort:</strong> ' +
        esc(data.location || "") +
        "</p>";
    } else {
      content += '<p class="chat-appointment-text">Kein Termin gesetzt.</p>';
    }

    var hasProRight =
      currentSubject &&
      userLevels &&
      userLevels["level_" + currentSubject] === "pro";

    var stableKey = stableAppointmentKey(data, hasProRight);
    if (stableKey === lastAppointmentUiKey) {
      var statsEl = $("chat-rating-stats");
      if (
        statsEl &&
        data &&
        data.ended &&
        hasProRight &&
        data.rating_count != null
      ) {
        statsEl.textContent =
          "Bewertungen: " +
          data.rating_count +
          (data.rating_avg != null ? " (Ø " + data.rating_avg.toFixed(1) + ")" : "");
      }
      return;
    }
    lastAppointmentUiKey = stableKey;

    if (data && data.ended) {
      content += '<p class="chat-appointment-text"><strong>Termin beendet.</strong></p>';
      if (hasProRight && data.rating_count != null) {
        content +=
          '<p class="chat-appointment-text muted" id="chat-rating-stats">Bewertungen: ' +
          data.rating_count +
          (data.rating_avg != null ? " (Ø " + data.rating_avg.toFixed(1) + ")" : "") +
          "</p>";
        content += '<ul class="chat-ratings-pro-list" id="chat-ratings-pro-list"></ul>';
      }
      if (hasProRight) {
        content +=
          '<div class="chat-rating-box">' +
          '<label for="rating-value">Bewertung (1–5):</label>' +
          '<select id="rating-value" class="chat-rating-input">' +
          ratingSelectOptions(data.your_rating) +
          "</select>" +
          '<label for="rating-comment">Kommentar <span id="rating-comment-hint" class="muted"></span></label>' +
          '<textarea id="rating-comment" class="chat-rating-textarea" rows="3" placeholder="Wie war das Treffen?"></textarea>' +
          '<button type="button" class="btn btn-secondary btn-small" id="btn-submit-rating">Bewertung speichern</button>' +
          "</div>";
      }
    } else {
      if (data && data.started) {
        content += '<p class="chat-appointment-text"><strong>Termin läuft. Raum geschlossen.</strong></p>';
      }
      if (hasProRight && data && data.appointment && !data.started) {
        content +=
          '<button type="button" class="btn btn-secondary btn-small" id="btn-start-appointment">Termin starten</button>';
      }
      if (hasProRight && data && data.appointment && data.started) {
        content +=
          '<button type="button" class="btn btn-secondary btn-small" id="btn-end-appointment">Termin beenden</button>';
      }
      if (hasProRight && !(data && data.started)) {
        content +=
          '<button type="button" class="btn btn-secondary btn-small" id="btn-set-appointment">Termin festlegen</button>';
      }
    }

    container.innerHTML = content;

    var listUl = $("chat-ratings-pro-list");
    if (listUl && data && data.ratings) {
      listUl.innerHTML = "";
      if (!data.ratings.length) {
        var li0 = document.createElement("li");
        li0.className = "muted";
        li0.textContent = "Noch keine Bewertungen.";
        listUl.appendChild(li0);
      } else {
        data.ratings.forEach(function (rv) {
          var li = document.createElement("li");
          var strong = document.createElement("strong");
          strong.textContent = rv.username;
          li.appendChild(strong);
          var mid = document.createTextNode(" — " + rv.rating + "/5");
          li.appendChild(mid);
          if (rv.comment) {
            var span = document.createElement("span");
            span.className = "muted";
            span.textContent = " — " + rv.comment;
            li.appendChild(span);
          }
          listUl.appendChild(li);
        });
      }
    }

    var ta = $("rating-comment");
    if (ta && data && data.your_rating && data.your_rating.comment) {
      ta.value = data.your_rating.comment;
    }

    function updateRatingCommentHint() {
      var sel = $("rating-value");
      var hint = $("rating-comment-hint");
      if (!sel || !hint) return;
      var r = parseInt(sel.value, 10);
      var need = r >= 1 && r < 4;
      hint.textContent = need
        ? "(Pflicht bei 1–3 Sternen)"
        : "(optional bei 4–5 Sternen)";
    }
    var selRate = $("rating-value");
    if (selRate) {
      selRate.addEventListener("change", updateRatingCommentHint);
      updateRatingCommentHint();
    }

    var setBtn = $("btn-set-appointment");
    if (setBtn) {
      setBtn.addEventListener("click", setAppointment);
    }
    var endBtn = $("btn-end-appointment");
    if (endBtn) {
      endBtn.addEventListener("click", endAppointment);
    }
    var startBtn = $("btn-start-appointment");
    if (startBtn) {
      startBtn.addEventListener("click", startAppointment);
    }
    var submitBtn = $("btn-submit-rating");
    if (submitBtn) {
      submitBtn.addEventListener("click", submitRating);
    }
  }

  function loadAppointment() {
    if (!currentSubject) return;
    api("/api/chat/appointment?subject=" + encodeURIComponent(currentSubject), {
      method: "GET",
    }).then(function (res) {
      if (!res.ok || !res.data) return;
      updateAppointmentUi(res.data);
    });
  }

  function setAppointment() {
    if (!currentSubject) return;
    var appointment = prompt(
      "Gib den Termin ein (Format: YYYY-MM-DD HH:MM):",
      ""
    );
    if (appointment === null) return;
    appointment = (appointment || "").trim();
    if (!appointment) {
      setLobbyError("Termin darf nicht leer sein.");
      return;
    }
    var location = prompt("Gib den Ort ein:", "");
    if (location === null) return;
    location = (location || "").trim();
    if (!location) {
      setLobbyError("Ort darf nicht leer sein.");
      return;
    }
    api("/api/chat/appointment", {
      method: "POST",
      body: { subject: currentSubject, appointment: appointment, location: location },
    }).then(function (res) {
      if (!res.ok) {
        if (res.data && res.data.error === "invalid_datetime") {
          setLobbyError("Ungueltiges Datum. Bitte Format YYYY-MM-DD HH:MM verwenden.");
        } else if (
          res.data &&
          (res.data.error === "empty_location" ||
            res.data.error === "invalid_location")
        ) {
          setLobbyError("Bitte einen Ort eingeben.");
        } else {
          setLobbyError("Termin speichern fehlgeschlagen.");
        }
        return;
      }
      loadAppointment();
    });
  }

  function clearMessagesUi() {
    sinceId = 0;
    var box = $("chat-messages");
    if (box) box.innerHTML = "";
  }

  function endAppointment() {
    if (!currentSubject) return;
    api("/api/chat/appointment/end", {
      method: "POST",
      body: { subject: currentSubject },
    }).then(function (res) {
      if (!res.ok) {
        setLobbyError("Termin beenden fehlgeschlagen.");
        return;
      }
      clearMessagesUi();
      loadAppointment();
    });
  }

  function startAppointment() {
    if (!currentSubject) return;
    api("/api/chat/appointment/start", {
      method: "POST",
      body: { subject: currentSubject },
    }).then(function (res) {
      if (!res.ok) {
        setLobbyError("Termin starten fehlgeschlagen.");
        return;
      }
      loadAppointment();
      loadRooms();
    });
  }

  function submitRating() {
    if (!currentSubject) return;
    var rating = parseInt($("rating-value").value, 10);
    var comment = ($("rating-comment").value || "").trim();
    if (rating >= 1 && rating < 4 && !comment) {
      setLobbyError("Bei weniger als 4 Sternen bitte einen Kommentar eintragen.");
      return;
    }
    api("/api/chat/appointment/rate", {
      method: "POST",
      body: {
        subject: currentSubject,
        rating: rating,
        comment: comment,
      },
    }).then(function (res) {
      if (!res.ok) {
        if (res.data && res.data.error === "need_comment") {
          setLobbyError("Bei weniger als 4 Sternen ist ein Kommentar verpflichtend.");
        } else {
          setLobbyError("Bewertung konnte nicht gespeichert werden.");
        }
        return;
      }
      loadAppointment();
    });
  }

  function showCreateRoomButton() {
    if (!userLevels) return;
    var btn = $("btn-create-room");
    if (!btn) return;
    btn.style.display = creatableSubjects.length ? "inline-flex" : "none";
  }

  function canCreateSubject(subject) {
    if (!userLevels) return false;
    return userLevels["level_" + subject] === "pro";
  }

  function chooseProSubject() {
    var choices = [];
    creatableSubjects.forEach(function (room) {
      if (canCreateSubject(room.subject)) choices.push(room.label + "|" + room.subject);
    });
    if (!choices.length) return null;
    if (choices.length === 1) return choices[0].split("|")[1];
    var text = "Wähle ein Fach:\n" + choices.map(function (c, idx) {
      return (idx + 1) + ". " + c.split("|")[0];
    }).join("\n") + "\nGib die Zahl ein.";
    var choice = prompt(text);
    if (!choice) return null;
    var idx = parseInt(choice, 10) - 1;
    if (idx < 0 || idx >= choices.length) return null;
    return choices[idx].split("|")[1];
  }

  function bindNavName() {
    return fetch("/api/me", { credentials: "same-origin" }).then(function (r) {
      if (r.status === 401) {
        window.location.replace("/login.html?next=/chat.html&flash=needlogin");
        return null;
      }
      return r.json();
    }).then(function (data) {
      if (!data || !data.username) return;
      window.__uid = data.user_id;
      userLevels = data;
      var nav = $("nav-username");
      if (nav) nav.textContent = data.username;
      if (data.role === "teacher" || data.role === "admin" || data.role === "dev") {
        var adm = $("nav-admin");
        if (adm) adm.classList.remove("hidden");
      }
      showCreateRoomButton();
    });
  }

  $("btn-create-room").addEventListener("click", function () {
    var subject = chooseProSubject();
    if (!subject) {
      setLobbyError("Wähle zuerst ein Pro-Fach aus, um einen Raum zu erstellen.");
      return;
    }
    openSubject(subject);
  });

  $("btn-leave").addEventListener("click", function () {
    leaveRoomNetwork();
  });

  $("chat-send-form").addEventListener("submit", sendMessage);

  window.addEventListener("pagehide", function () {
    if (!currentSubject) return;
    var blob = new Blob([JSON.stringify({ subject: currentSubject })], {
      type: "application/json",
    });
    navigator.sendBeacon("/api/chat/leave", blob);
  });

  bindNavName().then(function () {
    return loadRooms();
  }).then(function () {
    roomsTimer = setInterval(loadRooms, POLL_ROOMS_MS);
  });

  fetch("/api/me", { credentials: "same-origin" }).then(function (r) {
    return r.json();
  }).then(function (data) {
    userRole = data.role;
  }).catch(function () {
    // ignore
  });
})();
