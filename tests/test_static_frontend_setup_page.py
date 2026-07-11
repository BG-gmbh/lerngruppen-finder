from pathlib import Path


def test_setup_page_uses_shared_form_handler_for_setup_requests():
    repo_root = Path(__file__).resolve().parents[1]
    html_path = repo_root / "flutter_app" / "docs" / "setup.html"
    config_path = repo_root / "flutter_app" / "docs" / "js" / "config.js"
    form_handler_path = repo_root / "flutter_app" / "docs" / "js" / "form-handler.js"

    html = html_path.read_text(encoding="utf-8")
    config_js = config_path.read_text(encoding="utf-8")
    form_handler_js = form_handler_path.read_text(encoding="utf-8")

    assert '<script src="/js/config.js"></script>' in html
    assert '<script src="/js/form-handler.js"></script>' in html
    assert 'action="/setup"' in html
    # config.js loest API-Aufrufe standardmaessig same-origin auf (relative URLs),
    # damit /setup an den ausliefernden Host geht statt an eine feste Domain.
    assert 'resolveApiUrl' in config_js
    assert 'var defaultApiBase = "";' in config_js
    assert 'function normalizeAction' in form_handler_js
