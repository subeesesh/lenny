import pytest
from fastapi.testclient import TestClient

from app.agent.artifact import artifact_type
from app.agent.context import topic_of
from app.agent.essay import MAX_WORDS, MIN_WORDS, word_count, write_essay
from app.security.sanitize import MAX_BYTES, ArtifactRejected, check_size, sanitize_html
from tests.fakes import FakeProvider, ask, new_session, use

XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<SCRIPT SRC=https://evil.example/x.js></SCRIPT>",
    '<img src="x" onerror="alert(1)">',
    '<img src="https://evil.example/pixel.png">',
    '<body onload="alert(1)">',
    '<svg onload="alert(1)"><circle r="1"/></svg>',
    '<a href="javascript:alert(1)">click</a>',
    '<a href="JaVaScRiPt:alert(1)">click</a>',
    '<a href="&#106;avascript:alert(1)">click</a>',
    '<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">click</a>',
    '<iframe src="https://evil.example"></iframe>',
    '<object data="https://evil.example/x.swf"></object>',
    '<embed src="https://evil.example/x.swf">',
    '<form action="https://evil.example"><input name="q"><button>Go</button></form>',
    '<link rel="stylesheet" href="https://evil.example/x.css">',
    '<meta http-equiv="refresh" content="0;url=https://evil.example">',
    "<style>body{background:url(https://evil.example/x.png)}</style>",
    '<div style="background:url(https://evil.example/x.png)">x</div>',
    '<div style="width:expression(alert(1))">x</div>',
    '<p onclick="alert(1)" onmouseover="alert(1)">x</p>',
    '<base href="https://evil.example/">',
    '<math><mtext><table><mglyph><style><img src=x onerror=alert(1)>',
]
FORBIDDEN = [
    "<script", "onerror", "onload", "onclick", "onmouseover", "javascript:", "<iframe", "<object", "<embed",
    "<form", "<input", "<button", "<link", "<meta", "<style", "<base", "url(", "expression(", "evil.example",
    "data:text/html",
]


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_xss_payload_is_stripped(payload: str) -> None:
    clean = sanitize_html(f"<h1>Title</h1><p>Safe text</p>{payload}")
    assert "<h1>Title</h1>" in clean and "Safe text" in clean
    for bad in FORBIDDEN:
        assert bad not in clean.lower(), f"{bad!r} survived: {clean}"


def test_sanitizer_keeps_allowed_markup() -> None:
    html = (
        '<h2 style="color:#333">Head</h2><table><tr><th scope="col">A</th></tr><tr><td colspan="2">1</td></tr></table>'
        '<section><ul><li><strong>b</strong> <em>i</em></li></ul></section>'
        '<img src="data:image/png;base64,iVBORw0KGgo=" alt="dot"><a href="https://www.lennysnewsletter.com">link</a>'
    )
    clean = sanitize_html(html)
    for kept in ['style="color:#333"', "<table>", 'colspan="2"', "<section>", "<strong>", 'src="data:image/png', 'href="https://www.lennysnewsletter.com"']:
        assert kept in clean
    assert 'rel="noopener noreferrer"' in clean


def test_size_cap() -> None:
    check_size("x" * MAX_BYTES)
    with pytest.raises(ArtifactRejected, match="200 KB"):
        check_size("x" * (MAX_BYTES + 1))
    with pytest.raises(ArtifactRejected):
        sanitize_html("<p>" + "x" * MAX_BYTES + "</p>")


def test_nothing_left_after_sanitizing_is_rejected() -> None:
    with pytest.raises(ArtifactRejected):
        sanitize_html("<script>alert(1)</script>")


def essay(words: int) -> str:
    return "# Title\n\n" + " ".join(["word"] * (words - 1))


async def test_essay_retry_triggered_when_too_short() -> None:
    provider = FakeProvider([essay(600)], [essay(1250)])
    text, words, retried = await write_essay(provider, "ship30", [{"role": "user", "content": "write"}])
    assert (words, retried) == (1250, True)
    assert len(provider.calls) == 2
    retry_messages = provider.calls[1][1]
    assert retry_messages[-2] == {"role": "assistant", "content": essay(600)}
    assert retry_messages[-1]["content"].startswith("The essay has 600 words and must end up between 1,125 and 1,375 words. Add about 650 words")
    assert retry_messages[-1]["content"].endswith("Return the full essay, nothing else.")


async def test_essay_retry_shortens_when_too_long_and_happens_only_once() -> None:
    provider = FakeProvider([essay(2000)], [essay(1500)], [essay(1250)])
    _, words, retried = await write_essay(provider, "ship30", [{"role": "user", "content": "write"}])
    assert (words, retried) == (1500, True)
    assert len(provider.calls) == 2
    assert "Cut about 750 words" in provider.calls[1][1][-1]["content"]


async def test_essay_in_range_is_not_retried() -> None:
    provider = FakeProvider([essay(1200)])
    _, words, retried = await write_essay(provider, "ship30", [{"role": "user", "content": "write"}])
    assert (words, retried, len(provider.calls)) == (1200, False, 1)
    assert MIN_WORDS <= words <= MAX_WORDS


def test_word_count_ignores_markdown_symbols() -> None:
    assert word_count("# A title\n\n- **bold** point [1]\n\n## Next") == 6


@pytest.mark.parametrize(
    ("content", "expected"),
    [("Make an HTML one-pager on pricing", "html"), ("Make a one-pager on hiring", "html"),
     ("Make a markdown doc on onboarding", "markdown"), ("Turn this into a document", "markdown")],
)
def test_artifact_type(content: str, expected: str) -> None:
    assert artifact_type(content) == expected


def test_essay_endpoint_saves_markdown_artifact_with_sources(client: TestClient) -> None:
    use(client, provider=FakeProvider([essay(1250)]))
    sid = new_session(client)
    events = ask(client, sid, "Write a Ship 30 essay on retention")
    assert [e for e, _ in events] == ["status", "status", "citations", "token", "artifact", "done"]
    artifact = events[4][1]
    assert artifact["type"] == "markdown" and artifact["title"] == "Title"
    saved = client.get(f"/api/v1/artifacts/{artifact['id']}", params={"session_id": sid}).json()
    assert "## Sources" in saved["content"]
    assert "1. [Cy Guest — Gamma episode (00:01:05)](https://www.youtube.com/watch?v=x&t=65s)" in saved["content"]
    assert saved["message_id"] == events[-1][1]["message_id"]
    assert "1,250 words" in events[3][1]["text"]


def test_artifact_endpoint_sanitizes_html_and_is_session_scoped(client: TestClient) -> None:
    html = '```html\n<h1>Retention</h1><p onclick="x()">Compounds [1]</p><script>alert(1)</script>\n```'
    use(client, provider=FakeProvider([html]))
    sid, other = new_session(client), new_session(client)
    events = ask(client, sid, "Make an HTML one-pager about retention")
    artifact = events[4][1]
    assert (artifact["type"], artifact["title"]) == ("html", "Retention")
    saved = client.get(f"/api/v1/artifacts/{artifact['id']}", params={"session_id": sid}).json()
    assert saved["content"] == "<h1>Retention</h1><p>Compounds [1]</p>"
    res = client.get(f"/api/v1/artifacts/{artifact['id']}", params={"session_id": other})
    assert res.status_code == 404 and res.json()["error"]["code"] == "not_found"
    assert client.get(f"/api/v1/artifacts/{artifact['id']}").status_code == 422
    assert client.get(f"/api/v1/sessions/{sid}").json()["artifacts"][0]["id"] == artifact["id"]


def test_oversized_artifact_is_rejected_and_chat_continues(client: TestClient) -> None:
    use(client, provider=FakeProvider(["# Big\n\n" + "x" * (MAX_BYTES + 10)]))
    events = ask(client, new_session(client), "Make a markdown doc about retention")
    assert [e for e, _ in events] == ["status", "status", "citations", "token", "done"]
    assert "limit is 200 KB" in events[3][1]["text"]


@pytest.mark.parametrize(
    ("content", "topic"),
    [
        ("Make an HTML one-pager on how to run user interviews", "how to run user interviews"),
        ("Write a Ship 30 essay about finding product-market fit.", "finding product-market fit"),
        ("Please create a markdown doc covering pricing experiments", "pricing experiments"),
        ("Pricing experiments that worked", "Pricing experiments that worked"),
    ],
)
def test_topic_of_strips_request_phrasing(content: str, topic: str) -> None:
    assert topic_of(content) == topic


def test_essay_retrieves_on_topic_not_request(client: TestClient) -> None:
    retriever, _ = use(client, provider=FakeProvider([essay(1250)]))
    ask(client, new_session(client), "Write a Ship 30 essay on retention loops")
    assert retriever.calls == [("retention loops", None)]
