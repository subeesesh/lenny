import re

import nh3
import structlog

MAX_BYTES = 200 * 1024

TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "br", "hr", "ul", "ol", "li", "dl", "dt", "dd",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "colgroup", "col",
    "div", "span", "section", "article", "header", "footer", "blockquote", "pre", "code",
    "strong", "b", "em", "i", "u", "s", "small", "sub", "sup", "mark", "figure", "figcaption", "img", "a",
}
ATTRIBUTES = {
    "*": {"style", "title"},
    "a": {"href"},
    "img": {"src", "alt", "width", "height"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}
UNSAFE_STYLE = re.compile(r"url\s*\(|expression\s*\(|@import|javascript:|behavior\s*:", re.I)
OPEN_TAG = re.compile(r"<[a-zA-Z]")

log = structlog.get_logger()


class ArtifactRejected(Exception):
    pass


def keep_attribute(tag: str, attr: str, value: str) -> str | None:
    if tag == "img" and attr == "src":
        return value if value.lower().startswith("data:image/") else None
    if tag == "a" and attr == "href":
        return value if value.lower().startswith(("http://", "https://")) else None
    if attr == "style" and UNSAFE_STYLE.search(value):
        return None
    return value


def check_size(content: str) -> None:
    size = len(content.encode())
    if size > MAX_BYTES:
        raise ArtifactRejected(f"The document is {size // 1024} KB; the limit is {MAX_BYTES // 1024} KB.")


def sanitize_html(raw: str) -> str:
    check_size(raw)
    clean = nh3.clean(
        raw,
        tags=TAGS,
        attributes=ATTRIBUTES,
        url_schemes={"http", "https", "data"},
        attribute_filter=keep_attribute,
        link_rel="noopener noreferrer",
        strip_comments=True,
    )
    removed = len(OPEN_TAG.findall(raw)) - len(OPEN_TAG.findall(clean))
    if removed:
        log.info("artifact_sanitized", removed_elements=removed)
    if not clean.strip():
        raise ArtifactRejected("Nothing was left after removing unsafe HTML.")
    return clean
