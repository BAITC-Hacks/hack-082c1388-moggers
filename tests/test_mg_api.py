"""Web API contracts, including identifiers larger than JavaScript's safe integer."""
from fastapi.testclient import TestClient
import pytest

from moneygraph import api
from moneygraph.agent.session import Answer
from moneygraph.pipeline import run


@pytest.fixture(scope="module", autouse=True)
def generated_dataset(tmp_path_factory):
    original = api.OUT
    api.OUT = tmp_path_factory.mktemp("web_out")
    run(api.ROOT / 'data', api.OUT, quiet=True)
    api.dataset.cache_clear()
    yield
    api.OUT = original
    api.dataset.cache_clear()


def test_dataset_preserves_ids_and_complete_graph():
    with TestClient(api.app) as client:
        response = client.get('/api/v1/dataset')
    assert response.status_code == 200
    data = response.json()
    assert len(data['nodes']) == data['summary']['n_nodes'] == 2248
    assert len(data['edges']) == data['summary']['n_edges'] == 3119
    assert all(isinstance(n['gid'], str) for n in data['nodes'])
    assert any(n['gid'] == '100000003684369100' for n in data['nodes'])
    assert all(isinstance(e['src'], str) and isinstance(e['dst'], str) for e in data['edges'])
    assert all(isinstance(gid, str) for c in data['clusters'] for gid in c['top_gids'])
    assert 'NaN' not in response.text


def test_missing_dataset_is_actionable(monkeypatch):
    def missing():
        raise FileNotFoundError
    monkeypatch.setattr(api, 'dataset', missing)
    with TestClient(api.app) as client:
        response = client.get('/api/v1/dataset')
    assert response.status_code == 503
    assert 'pipeline' in response.json()['detail']


def test_ask_calls_assistant_and_rejects_invalid_input(monkeypatch):
    questions = []
    class FakeAssistant:
        def ask(self, question):
            questions.append(question)
            return Answer('Test answer', ['node_profile'], [], True)
    monkeypatch.setattr(api, 'assistant', FakeAssistant)
    with TestClient(api.app) as client:
        response = client.post('/ask', json={'question': '  test  '})
        assert response.status_code == 200
        assert response.json()['llm_used'] is True
        assert response.json()['tools_used'] == ['node_profile']
        assert client.post('/ask', json={'question': '   '}).status_code == 400
        assert client.post('/ask', json={'question': 'x' * 4001}).status_code == 422
    assert questions == ['test']


def test_secret_file_is_not_served():
    with TestClient(api.app) as client:
        assert client.get('/.env').status_code == 404
        assert client.get('/assistant').status_code == 200
