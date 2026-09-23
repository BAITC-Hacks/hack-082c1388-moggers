"""Проверки локального эндпоинта ассистента.

Ключевое требование: страница остаётся самодостаточной, а сервер — надстройкой.
"""
import json
import socket
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from moneygraph import serve as serve_mod  # noqa: E402
from moneygraph.agent import Assistant  # noqa: E402
from moneygraph.pipeline import run  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def out_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("serve_out")
    run(ROOT / "data", out, quiet=True)
    return out


@pytest.fixture(scope="module")
def base_url(out_dir):
    serve_mod._Handler.assistant = Assistant(ROOT / "data", out_dir)
    serve_mod._Handler.viewer_path = out_dir / "viewer.html"
    port = _free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), serve_mod._Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def _get(url: str):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.read(), dict(r.headers)


def _post(url: str, payload: dict):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_health_reports_graph_and_llm_mode(base_url):
    status, body, _ = _get(base_url + "/health")
    data = json.loads(body)
    assert status == 200
    assert data["nodes"] == 2248
    assert isinstance(data["llm"], bool)


def test_viewer_is_served_from_the_same_origin(base_url):
    """Одинаковый origin убирает CORS целиком — это предпочтительный режим."""
    status, body, headers = _get(base_url + "/")
    assert status == 200
    assert b"<title>" in body[:2000]
    assert "text/html" in headers["Content-Type"]


def test_cors_header_allows_the_standalone_file(base_url):
    """Страница, открытая как file://, имеет origin null — без заголовка запрос не пройдёт."""
    _, _, headers = _get(base_url + "/health")
    assert headers.get("Access-Control-Allow-Origin") == "*"


def test_ask_returns_grounded_answer(base_url):
    status, data = _post(base_url + "/ask", {"question": "кого смотреть первым?"})
    assert status == 200
    assert data["answer"]
    assert data["tools_used"]


def test_ask_rejects_empty_question(base_url):
    status, data = _post(base_url + "/ask", {"question": "   "})
    assert status == 400 and "error" in data


def test_ask_rejects_broken_json(base_url):
    req = urllib.request.Request(base_url + "/ask", data=b"not json",
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=10)
        raise AssertionError("должен был вернуть 400")
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_unknown_route_is_404(base_url):
    try:
        _get(base_url + "/secrets")
        raise AssertionError("должен был вернуть 404")
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_server_binds_only_to_loopback():
    """Инструмент работает с данными расследования — наружу он смотреть не должен."""
    source = (ROOT / "src" / "moneygraph" / "serve.py").read_text(encoding="utf-8")
    assert '("127.0.0.1", port)' in source
    assert "0.0.0.0" not in source


def test_viewer_degrades_without_the_server(out_dir):
    """Главное требование: без сервера файл остаётся полноценным экраном просмотра."""
    html = (out_dir / "viewer.html").read_text(encoding="utf-8")
    assert "Ассистент недоступен" in html          # понятная подсказка вместо поломки
    assert "moneygraph-serve" in html              # и указание, что запустить
    assert "OPENAI_API_KEY" not in html            # ключ в браузер не попадает
    assert "api.openai.com" not in html            # страница не ходит во внешний API
