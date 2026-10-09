import bisect
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.ingest.clean import Turn

SPLITTER = RecursiveCharacterTextSplitter(
    separators=["\n\n", "\n", ". ", " "],
    chunk_size=1800,
    chunk_overlap=200,
    add_start_index=True,
)


@dataclass
class Chunk:
    ord: int
    speaker: str | None
    start_ts: str | None
    text: str


def full_ts(ts: str) -> str:
    return ts if ts.count(":") == 2 else f"00:{ts}"


def chunk_turns(turns: list[Turn]) -> list[Chunk]:
    parts: list[str] = []
    offsets: list[int] = []
    pos = 0
    for t in turns:
        part = f"{t.speaker}: {t.text}" if t.speaker else t.text
        offsets.append(pos)
        parts.append(part)
        pos += len(part) + 2
    timestamps: list[str | None] = []
    last: str | None = None
    for t in turns:
        last = full_ts(t.ts) if t.ts else last
        timestamps.append(last)
    chunks = []
    for i, doc in enumerate(SPLITTER.create_documents(["\n\n".join(parts)])):
        turn = max(bisect.bisect_right(offsets, doc.metadata["start_index"]) - 1, 0)
        chunks.append(Chunk(i, turns[turn].speaker, timestamps[turn], doc.page_content))
    return chunks
