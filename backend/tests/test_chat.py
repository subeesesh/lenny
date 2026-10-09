import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.agent.router import route
from app.config import get_settings
from app.retrieval.search import Retrieval
from tests.fakes import FakeProvider, FakeRetriever, ask, new_session, timeout, unavailable, use

@pytest.mark.parametrize(
    ("content", "hint", "expected"),
    [
        ("What does Elena Verna say about growth loops?", None, "qa"),
        ("Write an essay on product-market fit", None, "essay"),
        ("Ship 30 style post about pricing", None, "essay"),
        ("Make a one-pager on onboarding", None, "artifact"),
        ("Turn this into a markdown doc", None, "artifact"),
        ("Give me an HTML summary", None, "artifact"),
        ("hello", None, "chat"),
        ("Hi there!", None, "chat"),
        ("What can you do?", None, "chat"),
        ("Hi, what do guests say about hiring PMs?", None, "qa"),
        ("What does the documentation say", None, "qa"),
        ("What does Lenny say about pricing?", "essay", "essay"),
        ("hello", "artifact", "artifact"),
    ],
)
def test_router_table(content: str, hint: str | None, expected: str) -> None:
    assert route(content, hint) == expected


def test_sse_order_and_message_persisted(client: TestClient) -> None:
    use(client)
    sid = new_session(client)
    events = ask(client, sid, "Why does retention compound for growth?")
    assert [e for e, _ in events] == ["status", "status", "citations", "token", "token", "done"]
    assert [d["stage"] for e, d in events if e == "status"] == ["retrieving", "generating"]
    citations = events[2][1]
    assert citations[0]["chunk_id"] == 1
    assert citations[0]["url"] == "https://www.youtube.com/watch?v=x&t=65s"
    done = events[-1][1]
    assert (done["provider"], done["model"]) == ("fake", "fake-1")

    session = client.get(f"/api/v1/sessions/{sid}").json()
    assert session["title"] == "Why does retention compound for growth?"
    user, assistant = session["messages"]
    assert (user["role"], assistant["role"]) == ("user", "assistant")
    assert assistant["content"] == "Hello world [1]"
    assert assistant["id"] == done["message_id"]
    assert assistant["citations"] == citations
    assert (assistant["provider"], assistant["model"], assistant["route"], assistant["status"]) == ("fake", "fake-1", "qa", "complete")
    assert isinstance(assistant["latency_ms"], int)


def test_title_is_first_question_truncated_to_60(client: TestClient) -> None:
    use(client)
    sid = new_session(client)
    ask(client, sid, "x" * 100)
    ask(client, sid, "a second question")
    assert client.get(f"/api/v1/sessions/{sid}").json()["title"] == "x" * 60


def test_session_isolation(client: TestClient) -> None:
    retriever, provider = use(client)
    a, b = new_session(client), new_session(client)
    ask(client, a, "Secret question in A")
    ask(client, b, "First question in B")
    ask(client, a, "Follow-up in A")

    messages_b = client.get(f"/api/v1/sessions/{b}").json()["messages"]
    assert [m["content"] for m in messages_b] == ["First question in B", "Hello world [1]"]
    assert retriever.calls[1] == ("First question in B", None)
    assert retriever.calls[2] == ("Follow-up in A", "Secret question in A")
    prompt_b = json.dumps(provider.calls[1][1])
    assert "Secret question in A" not in prompt_b
    assert "Secret question in A" in json.dumps(provider.calls[2][1])
    assert {s["id"] for s in client.get("/api/v1/sessions").json()} >= {a, b}


def test_refusal_streams_without_citations_or_llm(client: TestClient) -> None:
    _, provider = use(client, FakeRetriever(Retrieval(refusal="The transcripts don't cover this.", reason="retrieval_empty")))
    events = ask(client, new_session(client), "What's the weather in Paris?")
    assert [e for e, _ in events] == ["status", "citations", "token", "done"]
    assert events[1][1] == []
    assert events[2][1]["text"] == "The transcripts don't cover this."
    assert provider.calls == []


def test_chat_route_skips_retrieval(client: TestClient) -> None:
    retriever, provider = use(client)
    events = ask(client, new_session(client), "hello")
    assert [e for e, _ in events] == ["status", "citations", "token", "done"]
    assert retriever.calls == [] and provider.calls == []


@pytest.mark.parametrize(
    "body",
    [{"content": ""}, {"content": "   "}, {"content": "x" * 4001}, {"content": "hi", "route_hint": "poem"}, {}],
)
def test_message_validation_422(client: TestClient, body: dict[str, Any]) -> None:
    sid = new_session(client)
    res = client.post(f"/api/v1/sessions/{sid}/messages", json=body)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_unknown_session_404_and_bad_id_422(client: TestClient) -> None:
    res = client.post("/api/v1/sessions/00000000-0000-0000-0000-000000000000/messages", json={"content": "hi"})
    assert res.status_code == 404 and res.json()["error"]["code"] == "not_found"
    assert client.get("/api/v1/sessions/not-a-uuid").status_code == 422


@pytest.mark.parametrize(("failure", "code"), [(unavailable(), "provider_unavailable"), (timeout(), "provider_timeout")])
def test_provider_failure_streams_error_and_stores_error_status(client: TestClient, failure: Exception, code: str) -> None:
    _, provider = use(client, provider=FakeProvider([failure]))
    sid = new_session(client)
    events = ask(client, sid, "Why does retention compound?")
    assert [e for e, _ in events] == ["status", "status", "citations", "error"]
    error = events[-1][1]
    assert error["code"] == code and error["message"] and error["request_id"]
    assert len(provider.calls) == (2 if code == "provider_timeout" else 1)
    assistant = client.get(f"/api/v1/sessions/{sid}").json()["messages"][-1]
    assert assistant["status"] == "error"


def test_config_get_and_put(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def ollama_ok(base_url: str, model: str) -> tuple[bool, None]:
        return True, None

    monkeypatch.setattr("app.llm.providers.ollama_status", ollama_ok)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", SecretStr(""))
    config = client.get("/api/v1/config").json()
    assert config["active"] == {"provider": "ollama", "model": get_settings().ollama_model}
    cloud = next(p for p in config["providers"] if p["name"] == "anthropic")
    assert cloud["available"] is False and "ANTHROPIC_API_KEY" in cloud["reason"]

    res = client.put("/api/v1/config", json={"provider": "anthropic"})
    assert res.status_code == 400 and res.json()["error"]["code"] == "provider_not_configured"

    res = client.put("/api/v1/config", json={"provider": "ollama", "model": "qwen3:1.7b"})
    assert res.json()["active"] == {"provider": "ollama", "model": "qwen3:1.7b"}
    assert client.put("/api/v1/config", json={"provider": "gpt"}).status_code == 422
