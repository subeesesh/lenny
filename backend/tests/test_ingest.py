from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from pgvector.psycopg import register_vector

from app.config import get_settings
from app.db.pool import SCHEMA_PATH
from app.ingest.chunk import chunk_turns
from app.ingest.clean import Turn, clean_turns, split_turns
from app.ingest.pipeline import run
from app.ingest.source import Episode, load_episodes, select_episodes

EPISODES = Path(__file__).parent / "fixtures" / "episodes"


def turns_of(slug: str) -> list[Turn]:
    ep = next(e for e in load_episodes(EPISODES) if e.slug == slug)
    return clean_turns(split_turns(ep.body))[0]


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [[0.1] * 768 for _ in texts]


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(get_settings().database_url) as c:
        c.execute(SCHEMA_PATH.read_text())
        register_vector(c)
        yield c
        c.rollback()


@pytest.mark.parametrize(
    ("slug", "expected"),
    [
        ("alpha", [("Ada Guest", "00:00:00"), ("Lenny Rachitsky", "00:01:10"), ("Lenny Rachitsky", "00:01:40")]),
        ("beta", [("Bo Guest", "00:12"), ("Bo Guest", "01:30")]),
        ("gamma", [("Cy Guest", None), ("Lenny Rachitsky", None)]),
        ("delta", [("Di", "00:00:00"), ("Di", "00:01:15")]),
    ],
)
def test_speaker_header_formats(slug: str, expected: list[tuple[str, str | None]]) -> None:
    assert [(t.speaker, t.ts) for t in turns_of(slug)] == expected


def test_speaker_name_with_parenthetical() -> None:
    turns = split_turns("Jiaona Zhang (JZ) (00:39:27):\nI think so.\n")
    assert [(t.speaker, t.ts) for t in turns] == [("Jiaona Zhang (JZ)", "00:39:27")]


def test_sponsor_paragraph_removed_normal_sponsor_sentence_kept() -> None:
    text = " ".join(t.text for t in turns_of("alpha"))
    assert "brought to you by" not in text
    assert "find a sponsor inside the company" in text


def test_use_code_only_matches_sponsor_reads() -> None:
    text = " ".join(t.text for t in turns_of("beta"))
    assert "Use code to automate" in text
    assert "LENNY for $100" not in text


def test_tags_stripped() -> None:
    text = " ".join(t.text for t in turns_of("alpha") + turns_of("beta"))
    assert "[" not in text


def test_duplicate_and_non_episode_dropped_and_unverified_links_nulled() -> None:
    kept, duplicates = select_episodes(load_episodes(EPISODES))
    assert duplicates == 1
    assert [e.slug for e in kept] == ["alpha", "beta", "delta", "gamma"]
    urls = {e.slug: e.url for e in kept}
    assert urls["gamma"] is None and urls["delta"] is None
    assert urls["alpha"] == "https://www.youtube.com/watch?v=aaa"


def video_episode(slug: str, speaker: str, title: str, duration_s: float | None, last_ts: str,
                  description: str = "", video_id: str = "v") -> Episode:
    body = f"{speaker} (00:00:05):\nHello.\n\nLenny (00:00:20):\nHi.\n\n{speaker} ({last_ts}):\nBye.\n"
    return Episode(slug, title, speaker, f"https://www.youtube.com/watch?v={video_id}", video_id, None, slug, slug, body,
                   duration_s, description)


@pytest.mark.parametrize(
    ("episode", "linked"),
    [
        (video_episode("match", "Lauryn Isford", "Mastering onboarding | Lauryn Isford (Airtable)", 3861, "01:03:40"), True),
        (video_episode("other-guest", "Merci Grace", "Layoffs with grace | Matt Mochary", 3861, "01:03:40",
                       "Matt Mochary, CEO of Mochary Method"), False),
        (video_episode("clip", "Ada Chen", "Career advice | Ada Chen", 230, "01:18:00"), False),
        (video_episode("runs-past-video", "Tomer Cohen", "AI and PM | Tomer Cohen", 4050, "01:08:40"), False),
        (video_episode("in-description", "Bret Taylor", "Built Google Maps: Bret Taylor (Sierra)", 3600, "00:59:30",
                       "Bret Taylor’s legendary career"), True),
        (video_episode("no-length", "Ada Guest", "Topic | Ada Guest", None, "00:59:30"), False),
    ],
)
def test_link_kept_only_when_video_length_and_speaker_match(episode: Episode, linked: bool) -> None:
    kept, _ = select_episodes([episode])
    assert (kept[0].url is not None) == linked


def test_shared_video_link_goes_to_the_closest_fit() -> None:
    first = video_episode("uri-levine", "Uri Levine", "Crisis | Uri Levine (Waze)", 5026, "01:22:06")
    second = video_episode("uri-levine-20", "Uri Levine", "Crisis | Uri Levine (Waze)", 5026, "01:23:21")
    kept, _ = select_episodes([first, second])
    assert [e.slug for e in kept if e.url] == ["uri-levine-20"]


def test_chunks_keep_speaker_inline_and_track_timestamps() -> None:
    turns = [Turn("A", "00:00:01", "word " * 500), Turn("B", "00:05:00", "other " * 500)]
    chunks = chunk_turns(turns)
    assert len(chunks) > 2
    assert chunks[0].text.startswith("A: ")
    assert (chunks[0].speaker, chunks[0].start_ts) == ("A", "00:00:01")
    assert (chunks[-1].speaker, chunks[-1].start_ts) == ("B", "00:05:00")
    assert all(len(c.text) <= 1800 for c in chunks)


def test_rerun_skips_unchanged(conn: psycopg.Connection) -> None:
    embed = FakeEmbedder()
    first = run(conn, EPISODES, embed)
    assert (first.ingested, first.skipped_unchanged, first.failures) == (4, 0, 0)
    assert first.duplicates == 1 and first.non_episodes == 1 and first.sponsor_paragraphs == 3
    stored = conn.execute("SELECT count(*) FROM chunks c JOIN episodes e ON e.id = c.episode_id WHERE e.slug = ANY(%s)",
                          (["alpha", "beta", "gamma", "delta"],)).fetchone()[0]
    assert stored == first.chunks

    calls = embed.calls
    second = run(conn, EPISODES, embed)
    assert (second.ingested, second.skipped_unchanged) == (0, 4)
    assert embed.calls == calls

    conn.execute("UPDATE episodes SET url = 'https://stale' WHERE slug = 'gamma'")
    run(conn, EPISODES, embed)
    assert conn.execute("SELECT url FROM episodes WHERE slug = 'gamma'").fetchone()[0] is None
