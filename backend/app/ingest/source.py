import datetime as dt
import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.ingest.clean import TITLE_LINE, body_hash

REPO_URL = "https://github.com/ChatPRD/lennys-podcast-transcripts.git"
COMMIT = "be8ab89"
NON_EPISODES = {"interview-q-compilation", "teaser_2021"}
URL_PREFIXES = ("https://www.youtube.com/", "https://youtu.be/")


@dataclass
class Episode:
    slug: str
    title: str
    guest: str | None
    url: str | None
    video_id: str | None
    published_at: dt.date | None
    content_hash: str
    body_hash: str
    body: str


def ensure_source(root: Path) -> None:
    if not (root / ".git").exists():
        subprocess.run(["git", "clone", "-q", REPO_URL, str(root)], check=True)
    subprocess.run(["git", "-c", "safe.directory=*", "-C", str(root), "checkout", "-q", COMMIT], check=True)


def parse_date(value: object) -> dt.date | None:
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        return None


def parse_episode(slug: str, raw: str) -> Episode:
    _, front, body = raw.split("---", 2) if raw.startswith("---") else ("", "", raw)
    meta = yaml.safe_load(front) or {}
    title_line = TITLE_LINE.search(body)
    url = str(meta.get("youtube_url") or "")
    return Episode(
        slug=slug,
        title=str(meta.get("title") or (title_line.group(1) if title_line else slug)),
        guest=meta.get("guest"),
        url=url if url.startswith(URL_PREFIXES) else None,
        video_id=meta.get("video_id"),
        published_at=parse_date(meta.get("publish_date")),
        content_hash=hashlib.sha256(raw.encode()).hexdigest(),
        body_hash=body_hash(body),
        body=body,
    )


def load_episodes(episodes_dir: Path) -> list[Episode]:
    return [
        parse_episode(path.parent.name, path.read_text(encoding="utf-8"))
        for path in sorted(episodes_dir.glob("*/transcript.md"))
    ]


def select_episodes(episodes: list[Episode]) -> tuple[list[Episode], int]:
    by_body: dict[str, list[Episode]] = {}
    for ep in episodes:
        if ep.slug not in NON_EPISODES:
            by_body.setdefault(ep.body_hash, []).append(ep)
    kept = sorted((min(g, key=lambda e: (len(e.slug), e.slug)) for g in by_body.values()), key=lambda e: e.slug)
    video_counts: dict[str, int] = {}
    for ep in kept:
        if ep.video_id:
            video_counts[ep.video_id] = video_counts.get(ep.video_id, 0) + 1
    for ep in kept:
        if ep.video_id and video_counts[ep.video_id] > 1:
            ep.url = None
    duplicates = sum(len(g) - 1 for g in by_body.values())
    return kept, duplicates
