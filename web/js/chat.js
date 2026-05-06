(function () {
  var POLL_ROOMS_MS = 4000;
  var POLL_MSG_MS = 2500;
  var currentSubject = null;
  var sinceId = 0;
  var roomsTimer = null;
  var msgTimer = null;
  var maxUsers = 5;
  var userLevels = null;
  var userRole = null;

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
    opts = opts || {};
    opts.credentials = "same-origin";
    opts.headers = opts.headers || {};
    if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    return fetch(path, opts).then(function (r) {
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
      card.className = "room-card" + (room.full ? " room-card-full" : "");

      var h = document.createElement("h3");
      h.textContent = room.label;
      card.appendChild(h);

      var meta = document.createElement("p");
      meta.className = "room-meta";
      meta.textContent =
        room.count + " / " + room.max + " online" + (room.full ? " (voll)" : "");
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
        app.textContent = "Termin: " + room.appointment;
        card.appendChild(app);
      }

      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-block";
      if (room.you_in) {
        btn.textContent = "Chat fortsetzen";
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
      renderLobby(res.data.rooms);
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
      if (userRole === 'admin') {
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
        setLobbyError("Du warst nicht mehr im Raum. Bitte erneut beitreten.");
        return;
      }
      if (!res.ok || !res.data.messages) {
        loadAppointment();
        return;
      }
      if (res.data.messages.length)
        appendMessages(res.data.messages, beforeSince === 0);
      loadAppointment();
    });
  }

  function openSubject(subject) {
    setLobbyError("");
    api("/api/chat/join", { method: "POST", body: { subject: subject } }).then(function (res) {
      if (res.status === 409) {
        setLobbyError("Dieser Raum ist voll (" + maxUsers + " Nutzer). Versuch es gleich nochmal.");
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
      var labels = { german: "Deutsch", math: "Mathe", english: "Englisch" };
      $("chat-title").textContent = "Chat: " + (labels[subject] || subject);
      stopRoomsPoll();
      stopMsgPoll();
      fetchMessages();
      loadAppointment();
      msgTimer = setInterval(fetchMessages, POLL_MSG_MS);
      $("chat-input").focus();
    });
  }

  function leaveRoomUi(silent) {
    stopMsgPoll();
    currentSubject = null;
    sinceId = 0;
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
        input.value = body;
        return;
      }
      fetchMessages();
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

  function updateAppointmentUi(data) {
    var container = $("chat-appointment");
    if (!container) return;
    var content = "";
    if (data && data.appointment) {
      content +=
        '<p class="chat-appointment-text"><strong>Termin:</strong> ' +
        esc(data.appointment) +
        "</p>";
    } else {
      content += '<p class="chat-appointment-text">Kein Termin gesetzt.</p>';
    }

    var hasProRight =
      currentSubject &&
      userLevels &&
      userLevels["level_" + currentSubject] === "pro";

    if (data && data.ended) {
      content += '<p class="chat-appointment-text"><strong>Termin beendet.</strong></p>';
      if (data.rating_count) {
        content +=
          '<p class="chat-appointment-text">Bewertungen: ' +
          data.rating_count +
          (data.rating_avg ? " (Ø " + data.rating_avg.toFixed(1) + ")" : "") +
          '</p>';
      }
      if (data.your_rating) {
        content +=
          '<p class="chat-appointment-text">Danke für deine Bewertung: ' +
          esc(String(data.your_rating.rating)) +
          '/5</p>';
        if (data.your_rating.comment) {
          content +=
            '<p class="chat-appointment-text">Kommentar: ' +
            esc(data.your_rating.comment) +
            "</p>";
        }
      } else {
        content +=
          '<div class="chat-rating-box">' +
          '<label for="rating-value">Bewertung:</label>' +
          '<select id="rating-value" class="chat-rating-input">' +
          '<option value="1">1</option>' +
          '<option value="2">2</option>' +
          '<option value="3">3</option>' +
          '<option value="4">4</option>' +
          '<option value="5" selected>5</option>' +
          '</select>' +
          '<label for="rating-comment">Kommentar (optional):</label>' +
          '<textarea id="rating-comment" class="chat-rating-textarea" rows="2" placeholder="Wie war das Treffen?"></textarea>' +
          '<button type="button" class="btn btn-secondary btn-small" id="btn-submit-rating">Bewerten</button>' +
          '</div>';
      }
    } else {
      if (hasProRight && data && data.appointment) {
        content +=
          '<button type="button" class="btn btn-secondary btn-small" id="btn-end-appointment">Termin beenden</button>';
      }
      if (hasProRight) {
        content +=
          '<button type="button" class="btn btn-secondary btn-small" id="btn-set-appointment">Termin festlegen</button>';
      }
    }

    container.innerHTML = content;

    var setBtn = $("btn-set-appointment");
    if (setBtn) {
      setBtn.addEventListener("click", setAppointment);
    }
    var endBtn = $("btn-end-appointment");
    if (endBtn) {
      endBtn.addEventListener("click", endAppointment);
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
      "Gib den Termin ein (Ort, Datum und Uhrzeit):",
      ""
    );
    if (appointment === null) return;
    appointment = (appointment || "").trim();
    if (!appointment) {
      setLobbyError("Termin darf nicht leer sein.");
      return;
    }
    api("/api/chat/appointment", {
      method: "POST",
      body: { subject: currentSubject, appointment: appointment },
    }).then(function (res) {
      if (!res.ok) {
        setLobbyError("Termin speichern fehlgeschlagen.");
        return;
      }
      loadAppointment();
    });
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
      loadAppointment();
    });
  }

  function submitRating() {
    if (!currentSubject) return;
    var rating = parseInt($("rating-value").value, 10);
    var comment = $("rating-comment").value || "";
    api("/api/chat/appointment/rate", {
      method: "POST",
      body: {
        subject: currentSubject,
        rating: rating,
        comment: comment,
      },
    }).then(function (res) {
      if (!res.ok) {
        setLobbyError("Bewertung konnte nicht gespeichert werden.");
        return;
      }
      loadAppointment();
    });
  }

  function showCreateRoomButton() {
    if (!userLevels) return;
    var proSubjects = [];
    if (userLevels.level_german === "pro") proSubjects.push("german");
    if (userLevels.level_math === "pro") proSubjects.push("math");
    if (userLevels.level_english === "pro") proSubjects.push("english");
    var btn = $("btn-create-room");
    if (!btn) return;
    btn.style.display = proSubjects.length ? "inline-flex" : "none";
  }

  function chooseProSubject() {
    var choices = [];
    if (userLevels.level_german === "pro") choices.push("Deutsch|german");
    if (userLevels.level_math === "pro") choices.push("Mathe|math");
    if (userLevels.level_english === "pro") choices.push("Englisch|english");
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
      if (data.role === "admin") {
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
