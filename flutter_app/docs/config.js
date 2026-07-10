(function () {
  var cfg = window.APP_CONFIG || {};
  var defaultApiBase = "https://lerngruppen-finder.onrender.com";
  cfg.apiBaseUrl = cfg.apiBaseUrl || defaultApiBase;

  function normalizeBase(value) {
    if (!value) return "";
    return String(value).replace(/\/$/, "");
  }

  cfg.apiBaseUrl = normalizeBase(cfg.apiBaseUrl || defaultApiBase);

  cfg.resolveApiUrl = function (path) {
    if (!path) return cfg.apiBaseUrl || "";
    if (/^https?:\/\//.test(path)) return path;
    if (!cfg.apiBaseUrl) return path;
    return cfg.apiBaseUrl + path;
  };

  cfg.resolveSitePath = function (path) {
    if (!path) return path;
    if (/^https?:\/\//.test(path)) return path;
    if (path.charAt(0) === "/") return "." + path;
    return path;
  };

  var originalFetch = window.fetch;
  if (originalFetch) {
    window.fetch = function (input, init) {
      if (typeof input === "string" && input.charAt(0) === "/") {
        input = cfg.resolveApiUrl(input);
      }
      return originalFetch.call(this, input, init);
    };
  }

  function rewriteDom() {
    var nodes = Array.prototype.slice.call(document.querySelectorAll("a[href^='/'], link[href^='/'], script[src^='/'], img[src^='/'], form[action^='/']"));
    nodes.forEach(function (node) {
      if (node.tagName === "FORM") {
        var action = node.getAttribute("action");
        if (action && action.charAt(0) === "/") {
          node.setAttribute("action", cfg.resolveSitePath(action));
        }
      } else {
        var attr = node.tagName === "LINK" || node.tagName === "SCRIPT" || node.tagName === "IMG" ? "href" : "src";
        var value = node.getAttribute(attr);
        if (value && value.charAt(0) === "/") {
          node.setAttribute(attr, cfg.resolveSitePath(value));
        }
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", rewriteDom);
  } else {
    rewriteDom();
  }

  window.APP_CONFIG = cfg;
})();
