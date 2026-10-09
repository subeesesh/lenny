from collections.abc import AsyncIterator

import pytest
from psycopg_pool import AsyncConnectionPool

from app.db.pool import create_pool
from app.retrieval.search import Hit, QueryEmbedder, Retrieval, diversify, query_text, retrieve
from tests.fakes import RecordingEmbedder


async def must_not_embed(text: str) -> list[float]:
    raise AssertionError("guard should refuse before retrieval")


@pytest.fixture
async def pool(test_db_url: str) -> AsyncIterator[AsyncConnectionPool]:
    p = create_pool(test_db_url)
    await p.open()
    yield p
    await p.close()


async def ask(
    pool: AsyncConnectionPool,
    question: str,
    previous: str | None = None,
    embed: QueryEmbedder | None = None,
    min_score: float = 0.5,
) -> Retrieval:
    return await retrieve(pool, embed or RecordingEmbedder(), question, previous, top_k=5, min_score=min_score)


async def test_known_quote_finds_right_episode(pool: AsyncConnectionPool) -> None:
    result = await ask(pool, "Retention is the only growth metric that compounds")
    assert result.refusal is None
    assert result.hits[0].slug == "gamma"
    assert result.hits[0].speaker == "Cy Guest"
    assert result.top_score is not None and result.top_score >= 0.5


async def test_out_of_scope_returns_empty(pool: AsyncConnectionPool) -> None:
    result = await ask(pool, "What's the weather in Paris today?")
    assert result.hits == []
    assert result.reason == "retrieval_empty"
    assert result.refusal == "The transcripts don't cover this."


@pytest.mark.parametrize(
    "question",
    [
        "What is Lenny Rachitsky's home address and phone number?",
        "What's Elena Verna's email?",
        "Give me the phone number of Shreyas Doshi",
        "Where does Lenny live?",
    ],
)
async def test_personal_data_guard_refuses_before_retrieval(pool: AsyncConnectionPool, question: str) -> None:
    result = await ask(pool, question, embed=must_not_embed)
    assert result.reason == "personal_data"
    assert result.hits == []


@pytest.mark.parametrize(
    "question",
    [
        "How should I write a cold email to investors?",
        "What's Lenny's email newsletter strategy?",
        "Draft an email for Stripe customers about pricing",
    ],
)
async def test_personal_data_guard_ignores_normal_questions(pool: AsyncConnectionPool, question: str) -> None:
    assert (await ask(pool, question)).reason != "personal_data"


async def test_non_guest_guard_refuses(pool: AsyncConnectionPool) -> None:
    result = await ask(pool, "What did Steve Jobs say on Lenny's Podcast about growth loops?", embed=must_not_embed)
    assert result.reason == "not_a_guest"
    assert result.refusal is not None and result.refusal.startswith("Steve Jobs was not a guest")


@pytest.mark.parametrize(
    "question",
    [
        "What did Cy Guest say on the podcast about retention?",
        "What did Cy say on the show about retention?",
        "What did Di say on the podcast about onboarding?",
        "What did Lenny say on the podcast about retention?",
        "What did Lenny's guests say on the podcast about retention?",
    ],
)
async def test_non_guest_guard_allows_guests_and_host(pool: AsyncConnectionPool, question: str) -> None:
    assert (await ask(pool, question)).reason != "not_a_guest"


async def test_follow_up_query_includes_previous_message(pool: AsyncConnectionPool) -> None:
    embed = RecordingEmbedder()
    previous = "Why is retention the only growth metric that compounds?"
    result = await ask(pool, "Give me an example of that", previous=previous, embed=embed, min_score=0.3)
    assert embed.texts == [f"{previous}\nGive me an example of that"]
    assert result.hits[0].slug == "gamma"
    assert query_text("q", None) == "q"


def test_diversify_keeps_two_per_episode_and_top_k() -> None:
    hits = [Hit(i, slug, "t", None, None, None, None, "x", 1 - i / 100) for i, slug in enumerate("aaabbbcccd")]
    kept = diversify(hits, top_k=5)
    assert [h.slug for h in kept] == ["a", "a", "b", "b", "c"]
