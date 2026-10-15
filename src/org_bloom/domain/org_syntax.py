"""Org-mode syntax the site needs to understand before Pandoc runs: headline
anchors (as Pandoc names them), `:ID:` / `:CUSTOM_ID:` properties, the
title headline Orgamnesia puts at the top of a page and `#+ATTR_ORG` image
widths."""

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



_AFFILIATED = re.compile(r"^[ \t]*#\+\w+:", re.IGNORECASE)
_ATTR_ORG = re.compile(r"^([ \t]*)#\+ATTR_ORG:(.*)$", re.IGNORECASE)
_ATTR_HTML = re.compile(r"^[ \t]*#\+ATTR_HTML:(.*)$", re.IGNORECASE)
# :key value pairs; a value runs up to the next :key, so it may hold spaces.
_PLIST = re.compile(r"(?<!\S):([\w-]+)(?:[ \t]+(.*?))?(?=[ \t]+:[\w-]+(?:[ \t]|$)|[ \t]*$)")
# #+ATTR_ORG keys that mean the same thing as an HTML attribute.
_HTML_KEYS = ("alt", "title", "height", "class", "id")
_MARGINS = {
    "center": "margin-left:auto;margin-right:auto",
    "right": "margin-left:auto;margin-right:0",
}


def _plist(text: str) -> dict[str, str]:
    return {m.group(1).lower(): (m.group(2) or "").strip() for m in _PLIST.finditer(text)}


def _html_width(value: str) -> str:
    """Org's image width as HTML wants it: 981 and 981px are pixels, 50% stays a
    percentage and a fraction like 0.5 (part of the text width) becomes 50%."""
    if re.fullmatch(r"\d+px", value, re.IGNORECASE):
        return value[:-2]
    if re.fullmatch(r"0?\.\d+|1\.0*", value):
        return f"{float(value) * 100:g}%"
    return value


def _org_image_attrs(org: dict[str, str]) -> dict[str, str]:
    """The HTML attributes for an image's #+ATTR_ORG: :width, :align
    (left/center/right) and :background (a color, for transparent images), plus
    the HTML ones people also write there (:alt, :title, :height, :class, :id,
    :style). Emacs-only options are left out."""
    attrs = {key: org[key] for key in _HTML_KEYS if org.get(key)}
    if org.get("width"):
        attrs["width"] = _html_width(org["width"])
    style = [org["style"].rstrip(";")] if org.get("style") else []
    if org.get("align", "").lower() in _MARGINS:
        style.append(_MARGINS[org["align"].lower()])
    background = org.get("background", "").strip("\"")
    if background and background.lower() not in ("t", "nil"):
        style.append(f"background-color:{background}")
    if style:
        attrs["style"] = ";".join(style)
    return attrs


def attr_org_to_html(content: str) -> str:
    """Turn the image options of `#+ATTR_ORG:` (how Emacs shows an image) into
    `#+ATTR_HTML:`, which Pandoc applies to the <img>. Pandoc ignores
    #+ATTR_ORG and, worse, drops a #+CAPTION above it, so every #+ATTR_ORG line
    goes. A key also set by an #+ATTR_HTML on the same image keeps that value:
    it is meant for the web."""
    lines = content.splitlines(keepends=True)
    out = []
    i = 0
    while i < len(lines):
        if not _AFFILIATED.match(lines[i]):
            out.append(lines[i])
            i += 1
            continue
        block_end = i
        while block_end < len(lines) and _AFFILIATED.match(lines[block_end]):
            block_end += 1
        block = lines[i:block_end]
        html_keys = set()
        for line in block:
            if m := _ATTR_HTML.match(line.rstrip("\n")):
                html_keys |= _plist(m.group(1)).keys()
        for line in block:
            attr = _ATTR_ORG.match(line.rstrip("\n"))
            if attr is None:
                out.append(line)
                continue
            attrs = {k: v for k, v in _org_image_attrs(_plist(attr.group(2))).items() if k not in html_keys}
            if attrs:
                newline = "\n" if line.endswith("\n") else ""
                options = " ".join(f":{key} {value}" for key, value in attrs.items())
                out.append(f"{attr.group(1)}#+ATTR_HTML: {options}{newline}")
        i = block_end
    return "".join(out)
