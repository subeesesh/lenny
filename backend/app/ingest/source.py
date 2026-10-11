import datetime as dt
import hashlib
import re
import subprocess
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.ingest.clean import TITLE_LINE, Turn, body_hash, split_turns

REPO_URL = "https://github.com/ChatPRD/lennys-podcast-transcripts.git"
COMMIT = "be8ab89"
NON_EPISODES = {"interview-q-compilation", "teaser_2021"}
URL_PREFIXES = ("https://www.youtube.com/", "https://youtu.be/")
WORDS = re.compile(r"[a-z0-9]+")
VIDEO_FIT_S = (-30, 120)  # video end minus last transcript timestamp; matching pairs measure 0–70 s


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
    duration_s: float | None = None
    description: str = ""


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
        duration_s=float(meta["duration_seconds"]) if meta.get("duration_seconds") else None,
        description=str(meta.get("description") or ""),
    )


def load_episodes(episodes_dir: Path) -> list[Episode]:
    return [
        parse_episode(path.parent.name, path.read_text(encoding="utf-8"))
        for path in sorted(episodes_dir.glob("*/transcript.md"))
    ]


def words(text: str | None) -> list[str]:
    """Lowercase ASCII words: accents dropped ("Lütke" → "lutke"), other symbols split words ("Taylor’s" → "taylor", "s")."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    plain = "".join("" if unicodedata.combining(c) else c if c.isascii() else " " for c in decomposed)
    return WORDS.findall(plain.lower())


def seconds(ts: str) -> int:
    parts = [int(p) for p in ts.split(":")]
    return parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1]


def main_speakers(turns: list[Turn]) -> list[str]:
    counts = Counter(t.speaker for t in turns if t.speaker and "lenny" not in t.speaker.lower())
    return [s for s, _ in counts.most_common(3) if len(words(s)) >= 2]


def names_person(text: str, speaker: str, title: bool) -> bool:
    """Same last name and the same first initial ("Cam"/"Cameron", "JM"/"John Mark"). A title's guest part starts
    with the first name ("Topic | Anneka Gupta" is not Manik Gupta); in a description it may be up to two words back."""
    name, tokens = words(speaker), words(text)
    for i, t in enumerate(tokens):
        before = tokens[:1] if title else tokens[max(0, i - 2):i]
        if t == name[-1] and i > 0 and any(b[0] == name[0][0] for b in before):
            return True
    return False


def video_names_speaker(ep: Episode, speakers: list[str]) -> bool:
    guest = ep.title.split("|")[-1] if "|" in ep.title else ""
    return any(names_person(guest, s, title=True) or names_person(ep.description, s, title=False) for s in speakers)


def video_fit(ep: Episode, turns: list[Turn], speakers: list[str]) -> float | None:
    """The repo's video metadata is sometimes another episode's (a clip, the guest's other episode, another guest).
    Returns how far the video runs past the transcript's last timestamp, in seconds, if the video is verified
    as this episode's: that gap is within VIDEO_FIT_S and the video's title or description names one of the
    transcript's main speakers. None means the link can't be trusted."""
    stamps = [t.ts for t in turns if t.ts]
    if ep.duration_s is None or not stamps:
        return None
    gap = ep.duration_s - seconds(stamps[-1])
    return gap if VIDEO_FIT_S[0] <= gap <= VIDEO_FIT_S[1] and video_names_speaker(ep, speakers) else None


def select_episodes(episodes: list[Episode]) -> tuple[list[Episode], int]:
    by_body: dict[str, list[Episode]] = {}
    for ep in episodes:
        if ep.slug not in NON_EPISODES:
            by_body.setdefault(ep.body_hash, []).append(ep)
    kept = sorted((min(g, key=lambda e: (len(e.slug), e.slug)) for g in by_body.values()), key=lambda e: e.slug)
    fits: dict[str, float | None] = {}
    for ep in kept:
        turns = split_turns(ep.body)
        speakers = main_speakers(turns)
        fits[ep.slug] = video_fit(ep, turns, speakers) if ep.url else None
        if "|" in ep.title and speakers and not video_names_speaker(ep, speakers):
            ep.title = f"Episode with {speakers[0]}"  # "Topic | Guest" names someone who isn't in this transcript
    best: dict[str, Episode] = {}
    for ep in kept:
        if fits[ep.slug] is None:
            ep.url = None
        elif ep.video_id not in best or abs(fits[ep.slug]) < abs(fits[best[ep.video_id].slug]):
            best[ep.video_id] = ep
    for ep in kept:
        if ep.url and best[ep.video_id] is not ep:
            ep.url = None
    duplicates = sum(len(g) - 1 for g in by_body.values())
    return kept, duplicates
