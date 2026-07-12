(function () {
  var cfg = window.APP_CONFIG || {};
  // Split-Deployment: das statische Frontend liegt auf Cloudflare Pages
  // (group-ly.tech), die API auf Cloudflare Containers (api.group-ly.tech).
  // In Produktion zeigen wir daher auf die API-Subdomain; lokal (localhost,
  // 127.0.0.1, Datei) bleibt es bei same-origin, damit die Entwicklung ohne
  // CORS laeuft. Ueberschreibbar via window.APP_CONFIG = { apiBaseUrl: "…" }.
  function detectApiBase() {
    try {
      var host = window.location.hostname || "";
    } catch (e) {
      return "";
    }
    if (/(^|\.)group-ly\.tech$/i.test(host) && host.indexOf("api.") !== 0) {
      return "https://api.group-ly.tech";
    }
    return "";
  }
  var defaultApiBase = detectApiBase();
  cfg.apiBaseUrl = cfg.apiBaseUrl || defaultApiBase;

  function normalizeBase(value) {
    if (!value) return "";
    return String(value).replace(/\/$/, "");
  }

  function normalizePath(value) {
    if (!value) return "";
    var text = String(value).trim();
    if (!text) return "";
    if (/^https?:\/\//.test(text)) return text;
    if (text.charAt(0) === "/") return text;
    if (text.charAt(0) === ".") {
      return "/" + text.replace(/^\.\/+/, "");
    }
    return "/" + text;
  }

  cfg.apiBaseUrl = normalizeBase(cfg.apiBaseUrl || defaultApiBase);

  cfg.resolveApiUrl = function (path) {
    var normalizedPath = normalizePath(path);
    if (!normalizedPath) return cfg.apiBaseUrl || "";
    if (/^https?:\/\//.test(normalizedPath)) return normalizedPath;
    if (!cfg.apiBaseUrl) return normalizedPath;
    return cfg.apiBaseUrl + normalizedPath;
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
    var nodes = Array.prototype.slice.call(document.querySelectorAll("a[href^='/'], link[href^='/'], script[src^='/'], img[src^='/']"));
    nodes.forEach(function (node) {
      var attr = node.tagName === "LINK" || node.tagName === "SCRIPT" || node.tagName === "IMG" ? "href" : "src";
      var value = node.getAttribute(attr);
      if (value && value.charAt(0) === "/") {
        node.setAttribute(attr, cfg.resolveSitePath(value));
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
