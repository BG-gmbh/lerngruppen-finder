(function () {
  var supportedActions = ["/login", "/register", "/setup", "/profile", "/logout"];
  function getApiUrl(path) {
    var cfg = window.APP_CONFIG || {};
    if (typeof cfg.resolveApiUrl === "function") return cfg.resolveApiUrl(path);
    return path;
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form || form.tagName !== "FORM") return;
    var action = form.getAttribute("action") || "";
    if (supportedActions.indexOf(action) === -1) return;
    event.preventDefault();

    var method = (form.getAttribute("method") || "get").toUpperCase();
    var body = null;
    var headers = {};
    if (method === "GET") {
      body = null;
    } else if (form.enctype === "multipart/form-data") {
      body = new FormData(form);
    } else {
      body = new FormData(form);
    }

    fetch(getApiUrl(action), {
      method: method,
      credentials: "include",
      body: body,
      headers: headers,
    })
      .then(function (response) {
        var location = response.headers.get("Location");
        if (location) {
          window.location.assign(location);
          return;
        }
        if (response.redirected && response.url) {
          window.location.assign(response.url);
          return;
        }
        if (response.ok) {
          window.location.reload();
          return;
        }
        return response.text().then(function (text) {
          if (text) {
            document.open();
            document.write(text);
            document.close();
          }
        });
      })
      .catch(function () {
        window.location.reload();
      });
  });
})();
