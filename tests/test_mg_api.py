"""API tests are optional for the standalone pipeline installation."""
import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient
from moneygraph.api import create_app
from moneygraph.pipeline import run

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory):
    directory = tmp_path_factory.mktemp("api")
    run(ROOT / "data", directory, quiet=True)
    return directory / "dashboard.json"


def test_dataset_preserves_identifiers(snapshot):
    with TestClient(create_app(snapshot)) as client:
        response = client.get("/api/v1/dataset")
        assert response.status_code == 200
        data = response.json()
        ids = {node["gid"] for node in data["nodes"]}
        assert "100000003684369100" in ids
        assert len(ids) == 2248
        assert all(edge["src"] in ids and edge["dst"] in ids for edge in data["edges"])
        assert len(data["clusters"]) == 91
        assert client.post("/api/v1/dataset").status_code == 405
        assert client.get("/api/v1/missing").status_code == 404


@pytest.mark.parametrize("contents", [None, "{invalid", '{"schema_version": 1}', '{"nodes": NaN}'])
def test_missing_or_corrupt_data_returns_503(tmp_path, contents):
    path = tmp_path / "data.json"
    if contents is not None:
        path.write_text(contents)
    with TestClient(create_app(path)) as client:
        response = client.get("/api/v1/dataset")
        assert response.status_code == 503
        assert "./run.sh" in response.json()["detail"]


def test_dangling_edges_rejected(snapshot, tmp_path):
    payload = json.loads(snapshot.read_text())
    payload["edges"][0]["src"] = "missing"
    path = tmp_path / "data.json"
    path.write_text(json.dumps(payload))
    with TestClient(create_app(path)) as client:
        assert client.get("/api/v1/dataset").status_code == 503


def test_static_frontend(snapshot, tmp_path):
    (tmp_path / "index.html").write_text("<html>MoneyGraph</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/app.js").write_text("// application")
    with TestClient(create_app(snapshot, tmp_path)) as client:
        assert "MoneyGraph" in client.get("/").text
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/assets/../../pyproject.toml").status_code == 404
