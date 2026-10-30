"""Org-mode syntax the site needs to understand before Pandoc runs: headline
anchors (as Pandoc names them), `:ID:` / `:CUSTOM_ID:` properties,
`<<targets>>`, the places org links point to and the title headline
Orgamnesia puts at the top of a page."""

import re
import unicodedata
from collections.abc import Iterator
from typing import NamedTuple

from .paths import slugify

_HEADLINE = re.compile(r"^(\*+)[ \t]+(.*)$")
# The stars of any headline, an empty one (`*`) included.
_STARS = re.compile(r"^(\*+)(?=[ \t]|$)")
_DRAWER_PROPERTY = re.compile(r"^[ \t]*:(ID|CUSTOM_ID):[ \t]*(\S+)[ \t]*$", re.IGNORECASE)
_TODO_LINE = re.compile(r"^#\+(?:SEQ_|TYP_)?TODO:(.*)$", re.IGNORECASE | re.MULTILINE)
_DEFAULT_TODO_KEYWORDS = ("TODO", "DONE")
_PRIORITY = re.compile(r"^\[#[A-Za-z0-9]\][ \t]*")
_TRAILING_TAGS = re.compile(r"[ \t]+:([\w@#%:]+):[ \t]*$")
_FILETAGS = re.compile(r"^#\+FILETAGS:(.*)$", re.IGNORECASE | re.MULTILINE)
NOEXPORT = "noexport"
_LABELED = re.compile(r"\[\[[^\]]+\]\[([^\]]+)\]\]")
_PLAIN = re.compile(r"\[\[([^\]]+)\]\]")
_EMPHASIS = re.compile(r"(?<![\w])([*/_=~+])(\S(?:.*?\S)?)\1(?![\w])")
# Lines that may come before a page's first headline without being content.
_PREAMBLE_LINE = re.compile(r"^[ \t]*(?:#\+\w+:.*|:\w+:.*|:END:|[a-z][\w-]*::.*)?$", re.IGNORECASE)
_COOKIE = re.compile(r"\[\d*/\d*\]|\[\d*%\]")
# <<target>> and <<<radio target>>>; no < > or newline inside, no space at the ends.
_NAME = r"[^<>\s](?:[^<>\n]*[^<>\s])?"
_TARGET = re.compile(rf"<<<({_NAME})>>>|<<({_NAME})>>")
_BLOCK_BEGIN = re.compile(r"^[ \t]*#\+BEGIN_", re.IGNORECASE)
_BLOCK_END = re.compile(r"^[ \t]*#\+END_", re.IGNORECASE)


def todo_keywords(content: str) -> set[str]:
    """TODO keywords in effect on a page: Emacs defaults plus its `#+TODO:` lines
    (`TODO(t) DOING | DONE(d!)` — the shortcut suffixes and `|` are dropped)."""
    keywords = set(_DEFAULT_TODO_KEYWORDS)
    for line in _TODO_LINE.findall(content):
        for word in line.split():
            if word != "|":
                keywords.add(word.split("(")[0])
    return keywords


def headline_text(text: str, keywords: set[str]) -> str:
    """A headline's title as org links name it: no TODO keyword, priority,
    COMMENT or trailing `:tags:`."""
    return _PRIORITY.sub("", _without_keyword(text, keywords)).removeprefix("COMMENT ").strip()


def _without_keyword(text: str, keywords: set[str]) -> str:
    text = _TRAILING_TAGS.sub("", text).strip()
    first, _, rest = text.partition(" ")
    return rest.lstrip() if first in keywords else text


def pandoc_anchor(text: str) -> str:
    """The id Pandoc gives a headline of that text (its `auto_identifiers`)."""
    text = _LABELED.sub(r"\1", text)
    text = _PLAIN.sub(r"\1", text)
    text = _EMPHASIS.sub(r"\2", text)
    text = "".join(c for c in text.lower() if c.isalnum() or c.isspace() or c in "_-.")
    text = "-".join(text.split())
    while text and not text[0].isalpha():
        text = text[1:]
    return text or "section"


def filetags(content: str) -> list[str]:
    """Tags of the whole page: `#+FILETAGS: :a:b:` (or `a b`)."""
    tags: list[str] = []
    for value in _FILETAGS.findall(content):
        tags += [t for t in re.split(r"[:\s]+", value) if t]
    return list(dict.fromkeys(tags))


def headline_level(line: str) -> int:
    """The number of stars of a headline (`*` alone counts), 0 for other lines."""
    m = _STARS.match(line)
    return len(m.group(1)) if m else 0


class Headline(NamedTuple):
    line: int  # index of its line in the page
    level: int
    title: str  # as org links name it (see headline_text)
    # Its id in Pandoc's HTML; None for a COMMENT headline, which Pandoc leaves out.
    anchor: str | None
    tags: list[str]


def headlines(content: str) -> Iterator[Headline]:
    """Every headline of a page. Pandoc keeps the priority cookie in the
    anchor, so `* TODO [#A] Fix` is `#a-fix`."""
    keywords = todo_keywords(content)
    for i, line in enumerate(content.splitlines()):
        m = _HEADLINE.match(line)
        if m:
            text = _without_keyword(m.group(2), keywords)
            anchor = None if text.startswith("COMMENT ") or text == "COMMENT" else pandoc_anchor(text)
            tags_match = _TRAILING_TAGS.search(m.group(2))
            tags = [t for t in tags_match.group(1).split(":") if t] if tags_match else []
            yield Headline(i, len(m.group(1)), headline_text(m.group(2), keywords), anchor, tags)


def exported_headlines(content: str) -> Iterator[Headline]:
    """The headlines Pandoc exports: the subtrees of COMMENT and :noexport:
    headlines are left out. Their anchor is never None."""
    skip_below: int | None = None
    for h in headlines(content):
        if skip_below is not None and h.level > skip_below:
            continue
        skip_below = None
        if h.anchor is None or NOEXPORT in h.tags:
            skip_below = h.level
            continue
        yield h


def headline_tags(content: str) -> list[tuple[str, str, list[str]]]:
    """(title, anchor, tags) of every exported headline carrying tags."""
    return [(h.title, h.anchor, h.tags) for h in exported_headlines(content) if h.tags]


def _fold(text: str) -> str:
    """Case, accents and runs of spaces ignored, as Orgamnesia compares names."""
    text = unicodedata.normalize("NFKD", text.lower())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def _headline_key(title: str) -> str:
    """A headline's title compared without its statistics cookies (`[1/3]`, `[50%]`)."""
    return _fold(_COOKIE.sub(" ", title))


def target_anchor(name: str) -> str:
    """The id of the `<<name>>` target in the page (see expand_targets)."""
    return f"target-{slugify(name) or 'x'}"


def _targets(content: str) -> dict[str, str]:
    """Anchor of every `<<target>>` and `<<<radio target>>>`, keyed by its folded name."""
    anchors: dict[str, str] = {}
    for line, in_block in _lines(content):
        if not in_block:
            for m in _TARGET.finditer(line):
                name = m.group(1) or m.group(2)
                anchors.setdefault(_fold(name), target_anchor(name))
    return anchors


def _lines(content: str) -> Iterator[tuple[str, bool]]:
    """Each line of `content` (with its newline) and whether it belongs to a
    #+BEGIN_…/#+END_… block, where `<<…>>` is code, not a target."""
    in_block = False
    for line in content.splitlines(keepends=True):
        if _BLOCK_BEGIN.match(line):
            in_block = True
        yield line, in_block
        if _BLOCK_END.match(line):
            in_block = False


def expand_targets(content: str) -> str:
    """Turn `<<target>>` into an empty anchor and `<<<radio target>>>` into its
    text after one. Pandoc only reads targets without spaces, and names their
    id after the raw text."""
    def anchor(m: re.Match) -> str:
        name = m.group(1) or m.group(2)
        span = f'@@html:<span id="{target_anchor(name)}"></span>@@'
        return span + name if m.group(1) else span

    return "".join(line if in_block else _TARGET.sub(anchor, line) for line, in_block in _lines(content))


def place_anchor(content: str, place: str) -> str | None:
    """Anchor of the place an org search option names in a page:
    `*Headline`, `#custom-id`, or a `<<target>>` — failing that, a headline of
    that name, as org-mode does. Headlines and targets are compared ignoring
    case, accents and statistics cookies. None when the page has no such place."""
    if place.startswith("#"):
        return property_anchors(content)[1].get(place[1:])
    by_title: dict[str, str] = {}
    for h in headlines(content):
        if h.anchor is not None:
            by_title.setdefault(_headline_key(h.title), h.anchor)
    if place.startswith("*"):
        return by_title.get(_headline_key(place[1:]))
    return _targets(content).get(_fold(place)) or by_title.get(_headline_key(place))


def property_anchors(content: str) -> tuple[dict[str, str], dict[str, str]]:
    """`:ID:` and `:CUSTOM_ID:` values of a page, each mapped to the anchor of
    the headline whose drawer holds it ("" for the file-level drawer, before
    any headline). Returns (ids, custom_ids)."""
    ids: dict[str, str] = {}
    custom_ids: dict[str, str] = {}
    anchor_at = {h.line: h.anchor for h in headlines(content)}
    anchor: str | None = ""
    for i, line in enumerate(content.splitlines()):
        if i in anchor_at:
            anchor = anchor_at[i]
            continue
        prop = _DRAWER_PROPERTY.match(line)
        if prop and anchor is not None:
            target = ids if prop.group(1).upper() == "ID" else custom_ids
            target.setdefault(prop.group(2), anchor)
    return ids, custom_ids


def drop_title_headline(content: str, names: list[str]) -> str:
    """Remove the first headline when it only repeats the page title, as on a
    new Orgamnesia page (`* Name`), since the site shows the title above."""
    wanted = {slugify(name) for name in names if name}
    lines = content.splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = _HEADLINE.match(line.rstrip("\n"))
        if m:
            if len(m.group(1)) == 1 and slugify(headline_text(m.group(2), todo_keywords(content))) in wanted:
                return "".join(lines[:i] + lines[i + 1:])
            return content
        if not _PREAMBLE_LINE.match(line.rstrip("\n")):
            return content
    return content
