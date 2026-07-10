from pathlib import Path


def test_setup_page_uses_shared_form_handler_for_setup_requests():
    repo_root = Path(__file__).resolve().parents[1]
    html_path = repo_root / "flutter_app" / "docs" / "setup.html"
    config_path = repo_root / "flutter_app" / "docs" / "config.js"
    form_handler_path = repo_root / "flutter_app" / "docs" / "js" / "form-handler.js"

    html = html_path.read_text(encoding="utf-8")
    config_js = config_path.read_text(encoding="utf-8")
    form_handler_js = form_handler_path.read_text(encoding="utf-8")

    assert '<script src="/js/config.js"></script>' in html
    assert '<script src="/js/form-handler.js"></script>' in html
    assert 'action="/setup"' in html
    assert 'https://api.group-ly.tech' in config_js
    assert 'function normalizeAction' in form_handler_js
