"""Logseq's `{{embed ((uuid))}}` and `{{embed [[Page]]}}`: the embedded block
or page is written in place, before the links of the page are rewritten."""

import re

from ..domain.blocks import UUID, rebase_md, rebase_org
from .page_syntax import MD_PROPERTIES_BLOCK, Syntax
from .site_index import SiteIndex

EMBED = re.compile(rf"\{{\{{embed[ \t]+(\(\({UUID}\)\)|\[\[[^\]]+\]\])[ \t]*\}}\}}", re.IGNORECASE)
# A block holding nothing but an embed: `** {{embed …}}`, `\t- {{embed …}}`.
_ORG_EMBED_LINE = re.compile(rf"^(\*+)[ \t]+{EMBED.pattern}[ \t]*$", re.IGNORECASE)
_MD_EMBED_LINE = re.compile(rf"^([ \t]*)-[ \t]+{EMBED.pattern}[ \t]*$", re.IGNORECASE)
_FIRST_HEADLINE = re.compile(r"^\*+[ \t]", re.MULTILINE)
# Embeds inside embeds, at most this deep.
_MAX_DEPTH = 3


def expand_embeds(content: str, syntax: Syntax, index: SiteIndex, seen: frozenset[str] = frozenset()) -> str:
    """Replace each block holding only an embed with that block (and its
    children) or that page, moved to its level. An embed within text, of a
    block in a page of the other format, or of something not found becomes a
    link to it, ((uuid)) or [[Page]], for the resolver to rewrite."""
    line_embed = _ORG_EMBED_LINE if syntax.format == "org" else _MD_EMBED_LINE
    out = []
    for line in content.splitlines(keepends=True):
        m = line_embed.match(line.rstrip("\n"))
        embedded = _embedded(m.group(1), m.group(2), syntax, index, seen) if m else None
        if embedded is None:
            out.append(EMBED.sub(lambda e: e.group(1), line))
        else:
            out.append(embedded if embedded.endswith("\n") else embedded + "\n")
    return "".join(out)


def _embedded(lead: str, what: str, syntax: Syntax, index: SiteIndex, seen: frozenset[str]) -> str | None:
    """The text that stands for the block `lead {{embed what}}`, None to keep a link."""
    key = what.lower()
    if key in seen or len(seen) >= _MAX_DEPTH:
        return None
    org = syntax.format == "org"
    if what.startswith("(("):
        hit = index.block(what[2:-2])
        if hit is None or hit[0].format != syntax.format:
            return None
        block = hit[1]
        text = rebase_org(block.source, block.depth, len(lead)) if org else rebase_md(block.source, block.depth, lead)
    else:
        page = index.page_named(what[2:-2].strip())
        if page is None or page.format != syntax.format:
            return None
        # The page's name, then its blocks under it.
        if org:
            first = _FIRST_HEADLINE.search(page.raw_content)
            body = rebase_org(page.raw_content[first.start():], 1, len(lead) + 1) if first else ""
            text = f"{lead} {what}\n{body}"
        else:
            body = rebase_md(MD_PROPERTIES_BLOCK.sub("", page.raw_content), 0, lead + "\t")
            text = f"{lead}- {what}\n{body}"
    return expand_embeds(syntax.clean_embedded(text), syntax, index, seen | {key})
