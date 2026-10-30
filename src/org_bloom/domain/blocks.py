"""Logseq blocks a page can point to: `((uuid))` refers to the block whose
`id` property holds that uuid, `{{embed ((uuid))}}` shows it, children
included. In an Org page a block is a headline with `:id:` in its drawer; in
a Markdown page, a `- ` bullet followed by an indented `id:: uuid` line."""

import re
from dataclasses import dataclass

from .org_syntax import exported_headlines, headline_level

UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_ORG_ID = re.compile(r"^[ \t]*:ID:[ \t]*(\S+)[ \t]*$", re.IGNORECASE)
_BULLET = re.compile(r"^([ \t]*)-(?:[ \t]+(.*))?$")
_MD_PROPERTY = re.compile(r"^[ \t]+([A-Za-z][\w-]*)::(?:[ \t]+(.*))?$")
# Link syntax left out of the text a block ref shows: [[a][b]] → b, [[a]] → a,
# [b](a) → b, ((uuid)) → nothing.
_TEXT_LINKS = (
    (re.compile(r"\[\[[^\]]+\]\[([^\]]+)\]\]"), r"\1"),
    (re.compile(r"\[\[([^\]]+)\]\]"), r"\1"),
    (re.compile(r"\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(rf"\(\({UUID}\)\)"), ""),
)


@dataclass(frozen=True)
class Block:
    anchor: str  # its id in the page's HTML ("" for the top of the page)
    text: str  # its first line, as a block ref shows it
    source: str  # the block and its children, as written
    depth: int  # Org: the headline's stars; Markdown: the bullet's indent width


def block_text(line: str) -> str:
    """A block's first line without link syntax or brackets, ready to be a link label."""
    for pattern, repl in _TEXT_LINKS:
        line = pattern.sub(repl, line)
    return " ".join(line.replace("[", "").replace("]", "").split())


def org_blocks(content: str) -> dict[str, Block]:
    """The blocks of an Org page by id: every exported headline whose drawer
    has an `:ID:`. COMMENT and :noexport: subtrees are left out."""
    lines = content.splitlines(keepends=True)
    levels = [headline_level(line) for line in lines]
    blocks: dict[str, Block] = {}
    for h in exported_headlines(content):
        below = range(h.line + 1, len(lines))
        # Its drawer comes before the next headline, its subtree ends at the
        # next headline of its level or higher.
        drawer_end = next((j for j in below if levels[j]), len(lines))
        end = next((j for j in below if 0 < levels[j] <= h.level), len(lines))
        for line in lines[h.line + 1:drawer_end]:
            if m := _ORG_ID.match(line):
                blocks.setdefault(m.group(1), Block(h.anchor, block_text(h.title), "".join(lines[h.line:end]), h.level))
    return blocks


def md_anchor(uuid: str) -> str:
    return f"block-{uuid}"


def _width(indent: str) -> int:
    return len(indent.expandtabs(4))


def md_blocks(content: str) -> dict[str, Block]:
    """The blocks of a Markdown page by id: bullets with an `id::` property."""
    lines = content.splitlines(keepends=True)
    blocks: dict[str, Block] = {}
    for i, line in enumerate(lines):
        bullet = _BULLET.match(line.rstrip("\n"))
        if bullet is None:
            continue
        depth = _width(bullet.group(1))
        end = next(
            (j for j in range(i + 1, len(lines))
             if lines[j].strip() and _width(lines[j][:len(lines[j]) - len(lines[j].lstrip())]) <= depth),
            len(lines),
        )
        for prop_line in lines[i + 1:end]:
            prop = _MD_PROPERTY.match(prop_line.rstrip("\n"))
            if prop is None:
                break
            if prop.group(1).lower() == "id" and prop.group(2):
                uuid = prop.group(2).strip()
                blocks.setdefault(uuid, Block(md_anchor(uuid), block_text(bullet.group(2) or ""), "".join(lines[i:end]), depth))
    return blocks


def strip_md_properties(content: str, anchors: bool) -> str:
    """Drop the `key:: value` lines under a bullet (Logseq block properties);
    with `anchors`, an `id::` becomes an anchor at the end of the bullet's line."""
    out: list[str] = []
    bullet_at: int | None = None
    for line in content.splitlines(keepends=True):
        prop = _MD_PROPERTY.match(line.rstrip("\n")) if bullet_at is not None else None
        if prop is None:
            bullet_at = len(out) if _BULLET.match(line.rstrip("\n")) else None
            out.append(line)
            continue
        if anchors and prop.group(1).lower() == "id" and prop.group(2):
            head = out[bullet_at]
            newline = "\n" if head.endswith("\n") else ""
            out[bullet_at] = f'{head.rstrip()} <span id="{md_anchor(prop.group(2).strip())}"></span>{newline}'
    return "".join(out)


def rebase_org(source: str, from_level: int, to_level: int) -> str:
    """Org text with its headlines moved so that level `from_level` becomes `to_level`."""
    out = []
    for line in source.splitlines(keepends=True):
        level = headline_level(line)
        out.append("*" * max(1, level + to_level - from_level) + line[level:] if level else line)
    return "".join(out)


def rebase_md(source: str, from_depth: int, indent: str) -> str:
    """Markdown text with `from_depth` columns of indent replaced by `indent`."""
    out = []
    for line in source.splitlines(keepends=True):
        lead = line[:len(line) - len(line.lstrip(" \t"))]
        rest = line[len(lead):]
        out.append(indent + " " * max(0, _width(lead) - from_depth) + rest if rest.strip() else line)
    return "".join(out)
