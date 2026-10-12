"""Org-mode syntax the site needs to understand before Pandoc runs: headline
anchors (as Pandoc names them), `:ID:` / `:CUSTOM_ID:` properties and the
title headline Orgamnesia puts at the top of a page."""

import re
from collections.abc import Iterator

from .paths import slugify

_HEADLINE = re.compile(r"^(\*+)[ \t]+(.*)$")
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


def _headlines(content: str) -> Iterator[tuple[int, int, str, str | None, list[str]]]:
    """(line index, level, title, anchor, tags) of every headline. The anchor
    is None for a COMMENT headline, which Pandoc leaves out; Pandoc keeps the
    priority cookie in the anchor, so `* TODO [#A] Fix` is `#a-fix`."""
    keywords = todo_keywords(content)
    for i, line in enumerate(content.splitlines()):
        m = _HEADLINE.match(line)
        if m:
            text = _without_keyword(m.group(2), keywords)
            anchor = None if text.startswith("COMMENT ") or text == "COMMENT" else pandoc_anchor(text)
            tags_match = _TRAILING_TAGS.search(m.group(2))
            tags = [t for t in tags_match.group(1).split(":") if t] if tags_match else []
            yield i, len(m.group(1)), headline_text(m.group(2), keywords), anchor, tags


def headline_anchors(content: str) -> dict[str, str]:
    """Anchor of every exported headline, keyed by its title (`[[*Title]]` links)."""
    anchors: dict[str, str] = {}
    for _, _, title, anchor, _ in _headlines(content):
        if anchor is not None:
            anchors.setdefault(title, anchor)
    return anchors


def headline_tags(content: str) -> list[tuple[str, str, list[str]]]:
    """(title, anchor, tags) of every exported headline carrying tags; the
    subtrees of COMMENT and :noexport: headlines are left out, as Pandoc does."""
    tagged: list[tuple[str, str, list[str]]] = []
    skip_below: int | None = None
    for _, level, title, anchor, tags in _headlines(content):
        if skip_below is not None and level > skip_below:
            continue
        skip_below = None
        if anchor is None or NOEXPORT in tags:
            skip_below = level
            continue
        if tags:
            tagged.append((title, anchor, tags))
    return tagged


def property_anchors(content: str) -> tuple[dict[str, str], dict[str, str]]:
    """`:ID:` and `:CUSTOM_ID:` values of a page, each mapped to the anchor of
    the headline whose drawer holds it ("" for the file-level drawer, before
    any headline). Returns (ids, custom_ids)."""
    ids: dict[str, str] = {}
    custom_ids: dict[str, str] = {}
    anchor_at = {i: anchor for i, _, _, anchor, _ in _headlines(content)}
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
