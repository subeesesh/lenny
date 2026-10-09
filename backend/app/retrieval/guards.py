import re

NAME = r"[A-Z][\w'.-]*(?:\s+[A-Z][\w'.-]*){0,3}"
DATA = r"(?i:(?:home |personal |private |work )?(?:address|phone(?: number)?|cell(?: number)?|mobile(?: number)?|e-?mail(?: address)?|contact (?:info|details)))"
END = r"(?=\s*(?:and\b|or\b|,|\?|\.|!|$))"
PERSONAL_DATA = re.compile(
    rf"{NAME}'s\s+{DATA}{END}|{DATA}\s+(?i:of)\s+{NAME}|(?i:\bhome address\b)|\b(?i:where does)\s+{NAME}\s+(?i:live)\b"
)
SAID_ON_PODCAST = re.compile(
    rf"\b(?i:did|does|has|have)\s+(?P<name>{NAME})\s+(?i:(?:ever\s+)?(?:say|said|talk|discuss|mention|share|recommend|explain|think))\b"
    r".*\bon\s+(?i:(?:(?:lenny'?s|the)\s+)?(?:podcast|show))\b"
)
HOST_WORDS = {"lenny", "rachitsky"}

PERSONAL_DATA_MESSAGE = "I can't help with personal contact details or addresses of real people."


def words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z]+", text.lower()) if len(w) >= 3}


def is_personal_data_request(question: str) -> bool:
    return bool(PERSONAL_DATA.search(question))


def asked_person(question: str) -> str | None:
    m = SAID_ON_PODCAST.search(question)
    return m.group("name") if m else None


def is_known_person(name: str, people: list[str]) -> bool:
    asked = words(name)
    return asked <= HOST_WORDS or any(asked <= words(p) for p in people)


def non_guest_message(name: str) -> str:
    return f"{name} was not a guest on Lenny's Podcast, so the transcripts don't contain anything they said."
