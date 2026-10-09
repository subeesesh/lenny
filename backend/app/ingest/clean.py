import hashlib
import re
from dataclasses import dataclass

TS = r"\d{1,2}:\d{2}(?::\d{2})?"
NAME = r"[A-Z][\w'.\-]*(?: [A-Z][\w'.\-]*){0,4}"
HEADER = re.compile(
    rf"^(?:(?P<name1>[^\n\[\]:]{{1,60}}?) ?)?\((?P<ts1>{TS})\):[ \t]*"
    rf"|^\[(?P<ts2>{TS})\] (?P<name2>[^\n:]{{1,60}}):[ \t]*"
    rf"|^(?P<name3>{NAME}):[ \t]*$",
    re.M,
)
SPONSOR = re.compile(r"brought to you by|promo code|sponsored by|\buse code\b[:,]? ?(?-i:[A-Z])", re.I)
TAGS = re.compile(r"\[(?:inaudible|crosstalk)[^\]]*\]|\[laughs?\]", re.I)
TITLE_LINE = re.compile(r"^# (.+)$", re.M)
HOST = "Lenny Rachitsky"


@dataclass
class Turn:
    speaker: str | None
    ts: str | None
    text: str


def normalize_speaker(name: str | None) -> str | None:
    if not name:
        return None
    name = name.strip()
    return HOST if name.lower() in ("lenny", "lenny rachitsky") else name


def body_hash(body: str) -> str:
    body = TITLE_LINE.sub("", body)
    body = re.sub(rf"[(\[]?{TS}[)\]]?", "", body)
    return hashlib.sha256(re.sub(r"[^a-z]", "", body.lower()).encode()).hexdigest()


def split_turns(body: str) -> list[Turn]:
    matches = list(HEADER.finditer(body))
    turns: list[Turn] = []
    speaker: str | None = None
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        name = m.group("name1") or m.group("name2") or m.group("name3")
        speaker = normalize_speaker(name) or speaker
        turns.append(Turn(speaker, m.group("ts1") or m.group("ts2"), body[m.end() : end]))
    return turns


def clean_text(text: str) -> tuple[str, int]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    kept = [p for p in paragraphs if not SPONSOR.search(p)]
    cleaned = [re.sub(r"[ \t]+", " ", TAGS.sub("", p)).strip() for p in kept]
    return "\n".join(p for p in cleaned if p), len(paragraphs) - len(kept)


def clean_turns(turns: list[Turn]) -> tuple[list[Turn], int]:
    out: list[Turn] = []
    dropped = 0
    for t in turns:
        text, n = clean_text(t.text)
        dropped += n
        if text:
            out.append(Turn(t.speaker, t.ts, text))
    return out, dropped
