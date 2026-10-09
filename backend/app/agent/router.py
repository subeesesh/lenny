import re

ESSAY = re.compile(r"\b(?:essay|ship ?30)\b", re.I)
ARTIFACT = re.compile(r"\b(?:html|markdown|one-pager|document|doc)\b", re.I)
CHAT = re.compile(
    r"^\s*(?:hi|hello|hey|yo|hiya|good (?:morning|afternoon|evening)|thanks|thank you)\b[\s!.,]*(?:there)?[\s!.]*$"
    r"|\bwhat can you do\b|\bwhat do you do\b|\bwho are you\b|\bhow can you help\b",
    re.I,
)


def route(content: str, hint: str | None = None) -> str:
    if hint:
        return hint
    if ESSAY.search(content):
        return "essay"
    if ARTIFACT.search(content):
        return "artifact"
    if CHAT.search(content):
        return "chat"
    return "qa"
