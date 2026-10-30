"""Rewrites the links of a page (wiki links, org links, tags, assets, videos,
Logseq block refs) into links Pandoc turns into the right HTML, and keeps
track of the links that lead nowhere."""

import re
from pathlib import Path

from ..domain.blocks import UUID
from ..domain.org_syntax import pandoc_anchor, place_anchor
from ..domain.page import Page, PageFormat
from ..domain.video import youtube_embed
from .embeds import expand_embeds
from .page_syntax import SYNTAXES, URL_PREFIXES, Syntax
from .site_index import SiteIndex

# Extensions that identify a non-page file target (to be treated as asset).
_PAGE_EXTENSIONS = frozenset({".org", ".md", ".html"})


def _looks_like_file(target: str) -> bool:
    """True when the target has a non-page file extension (e.g. .pdf, .map, .zip)."""
    suffix = Path(target.split("/")[-1]).suffix.lower()
    # Reject suffixes that contain spaces or are longer than 8 chars — those are
    # names with dots that aren't extensions (e.g. "Dr. Livia Morozov" → ". Livia Morozov").
    if not re.match(r'^\.[a-z0-9]{1,8}$', suffix):
        return False
    return suffix not in _PAGE_EXTENSIONS


# Between a page and a place in it: [[Page::*Headline]], [[Page::target]] (Orgamnesia).
_PLACE_SEPARATOR = "::"
# Shown between the page and the place of an unlabeled [[Page::*Headline]].
_PLACE_LABEL = " › "

# Logseq block refs: ((uuid)); with a label, [[((uuid))][label]] (Org) or
# [label](((uuid))) (Markdown).
_BLOCK_REF = re.compile(rf"\(\(({UUID})\)\)")
_ORG_LABELED_BLOCK_REF = re.compile(rf"\[\[\(\(({UUID})\)\)\]\[([^\]]+)\]\]")
_MD_LABELED_BLOCK_REF = re.compile(rf"\[([^\]]+)\]\(\(\(({UUID})\)\)\)")

# [[../assets/file]] or [[../assets/file][label]]
_ASSET_REL = re.compile(r"\[\[\.\./assets/([^\]]+)\](?:\[([^\]]+)\])?\]")
_LABELED_LINK = re.compile(r"\[\[([^\]]+)\]\[([^\]]+)\]\]")
_SIMPLE_LINK = re.compile(r"\[\[([^\]]+)\]\]")
_HASHTAG_COMPOUND = re.compile(r"#\[\[([^\]]+)\]\]")
# Matches #word hashtags — excludes #+directives, #[[compound]] (handled separately),
# and labels already inside generated links (preceded by [ in org ][#tag] or md [#tag]).
_HASHTAG_SIMPLE = re.compile(r"(?<![a-zA-Z0-9_\[])#([^\W\d_][\w-]*)")
_KEYWORD_LINE = re.compile(r"[ \t]*#\+\w+:")
# Logseq's video macros: {{video URL}}, {{youtube URL}}.
_VIDEO_MACRO = re.compile(r"\{\{(?:video|youtube)[ \t]+([^}\s]+)[ \t]*\}\}", re.IGNORECASE)
# An unlabeled link to a URL, a video if it points to YouTube (Orgamnesia).
_BARE_URL_LINK = re.compile(r"\[\[(https?://[^\]\s]+)\]\]")


def _org_anchor(page: Page | None, search: str) -> str:
    """Anchor for an org search option: `*Headline`, `#custom-id` or a
    `<<target>>` (see place_anchor). A place missing from the page leads to
    its top; without the page's text, Pandoc's anchor is guessed."""
    search = search.strip()
    if page is not None and page.format == "org":
        return place_anchor(page.raw_content, search) or ""
    if search.startswith("*"):
        return pandoc_anchor(search[1:].strip())
    return search.removeprefix("#")


class LinkResolver:
    def __init__(
        self,
        pages: list[Page],
        home_slug: str,
        root: Path | None = None,
        static_dirs: list[Path] | None = None,
        html_links: bool = True,
    ) -> None:
        self.index = SiteIndex(pages, home_slug)
        # Project root: relative file links are looked up from the linking page
        # and must stay inside it.
        self.root = root.resolve() if root is not None else None
        # Folders copied to the site root as they are, each as /<its name>/
        # (see static_site_folders).
        self.static_dirs = static_dirs or []
        # False: every link to a hand-made HTML page leads to 404.html.
        self.html_links = html_links
        # (source_page_title, target) pairs for links that resolve to no known page.
        self.broken_links: list[tuple[str, str]] = []
        # (source_page_title, target) pairs for HTML pages sent to 404.html.
        self.missing_files: list[tuple[str, str]] = []

    def preprocess_org(self, content: str, source: str = "") -> tuple[str, list[str]]:
        """Clean and rewrite org content for pandoc.

        Returns (processed_content, list_of_asset_paths).
        """
        return self.preprocess(content, "org", source)

    def preprocess_md(self, content: str, source: str = "") -> tuple[str, list[str]]:
        """Rewrite Logseq markdown content for pandoc."""
        return self.preprocess(content, "md", source)

    def preprocess(
        self, content: str, fmt: PageFormat, source: str = "", page: Page | None = None
    ) -> tuple[str, list[str]]:
        rewrite = _PageRewrite(self, SYNTAXES[fmt], source, page)
        return rewrite.run(content), rewrite.assets


class _PageRewrite:
    """The rewriting of one page: `source` names it in the reports, `page`
    (when known) is where its relative links start from."""

    def __init__(self, resolver: LinkResolver, syntax: Syntax, source: str, page: Page | None) -> None:
        self._resolver = resolver
        self._index = resolver.index
        self._syntax = syntax
        self._source = source
        self._page = page
        self.assets: list[str] = []

    def run(self, content: str) -> str:
        syntax = self._syntax
        content = syntax.clean(content)
        content = expand_embeds(content, syntax, self._index)
        # Videos first: their URL must not become a plain link below.
        content = _VIDEO_MACRO.sub(self._video_macro, content)
        content = _BARE_URL_LINK.sub(self._video_link, content)
        content = _ASSET_REL.sub(lambda m: self._asset(f"assets/{m.group(1)}", m.group(2)), content)
        # _LABELED_LINK first: [[page][label]] — must precede _HASHTAG_COMPOUND so
        # the resulting link is never re-processed by later patterns.
        content = _LABELED_LINK.sub(self._labeled, content)
        # _HASHTAG_COMPOUND after _LABELED_LINK (safe: #[[tag]] has no ][ inside)
        # and before _SIMPLE_LINK (to prevent [[tag]] inside #[[tag]] being caught).
        # The generated org [[file:...][#tag]] is not re-caught because _SIMPLE_LINK
        # requires ]] immediately after the target.
        content = _HASHTAG_COMPOUND.sub(lambda m: self._page_link(m.group(1), f"#{m.group(1)}"), content)
        content = _SIMPLE_LINK.sub(self._simple, content)
        # _HASHTAG_SIMPLE last: #word has no overlap with [[...]] syntax.
        # #+KEYWORD lines are skipped: a color like #ffd in #+ATTR_HTML is no tag.
        content = "".join(
            line if _KEYWORD_LINE.match(line)
            else _HASHTAG_SIMPLE.sub(lambda m: self._page_link(m.group(1), f"#{m.group(1)}"), line)
            for line in content.splitlines(keepends=True)
        )
        # Block refs at the very end: the links they make must not be read again.
        return self._block_refs(content)

    # ── Reports ──────────────────────────────────────────────────────────────

    def _broken(self, target: str) -> None:
        self._resolver.broken_links.append((self._source, target))

    def _missing_file(self, path: str) -> None:
        self._resolver.missing_files.append((self._source, path))

    # ── [[…]] links ──────────────────────────────────────────────────────────

    def _labeled(self, m: re.Match) -> str:
        target, label = m.group(1), m.group(2)
        if _BLOCK_REF.fullmatch(target):
            return m.group(0)  # [[((uuid))][label]]: see _block_refs
        if self._syntax.org_links and (link := self._org_link(target, label)) is not None:
            return link
        if target.startswith(URL_PREFIXES):
            return self._syntax.link(target, label)
        if _looks_like_file(target):
            return self._asset(self._linked_file(target), label)
        return self._place_link(target, label) or self._page_link(target, label)

    def _simple(self, m: re.Match) -> str:
        target = m.group(1)
        if self._syntax.org_links and (link := self._org_link(target, None)) is not None:
            return link
        if target.startswith(URL_PREFIXES):
            return self._syntax.bare_external(target)
        if target.startswith(self._syntax.asset_prefixes) or _looks_like_file(target):
            return self._asset(self._linked_file(target), None)
        return self._place_link(target, None) or self._page_link(target, target)

    def _page_slug(self, name: str) -> str:
        """The slug of the page `name`, reported broken when there is none."""
        slug, exists = self._index.slug(name)
        if not exists:
            self._broken(name)
        return slug

    def _page_link(self, name: str, label: str) -> str:
        return self._syntax.page_link(self._index.href(self._page_slug(name)), label)

    def _place_link(self, target: str, label: str | None) -> str | None:
        """[[Page::*Headline]], [[Page::target]]; [[::target]] in the page
        itself. None for a target without "::"."""
        name, sep, place = target.partition(_PLACE_SEPARATOR)
        name, place = name.strip(), place.strip()
        if not sep:
            return None
        if name:
            slug = self._page_slug(name)
            linked = self._index.page_by_slug(slug)
        else:
            linked = self._page
        anchor = _org_anchor(linked, place) if place else ""
        if label is None:
            shown = linked.title if linked is not None and name else name
            label = _PLACE_LABEL.join(p for p in (shown, place.lstrip("*#")) if p)
        if name:
            return self._syntax.page_link(self._index.href(slug, anchor), label)
        return self._syntax.link(f"#{anchor}", label)

    def _org_link(self, target: str, label: str | None) -> str | None:
        """file:, id:, *Headline and #custom-id links; None for any other target."""
        syntax = self._syntax
        if target.startswith(("*", "#")):
            return syntax.link("#" + _org_anchor(self._page, target), label or target.lstrip("*#"))
        if target.startswith("id:"):
            hit = self._index.org_id(target[3:])
            if hit is None:
                self._broken(target)
                return label or target
            linked, anchor = hit
            return syntax.page_link(self._index.href(linked.slug, anchor), label or linked.title)
        if target.startswith("file:"):
            return self._file_link(target, label)
        return None

    def _file_link(self, target: str, label: str | None) -> str:
        """[[file:…]]: a page (with a place in it after ::), an HTML page or an attachment."""
        syntax = self._syntax
        path, _, search = target[len("file:"):].partition("::")
        suffix = Path(path).suffix.lower()
        if suffix in (".html", ".htm") and Path(path).parts[:1] != ("assets",):
            # A custom HTML page next to the notes, copied as is (see copy_pages_subdirs).
            # An HTML file in assets/ is an attachment, already listed for copy.
            if not self._resolver.html_links or not self._html_page_exists(path):
                self._missing_file(path)
                return syntax.page_link("404.html", label or path)
            return syntax.link(target, label or path)
        if suffix not in (".org", ".md"):
            return self._asset(self._linked_file(path), label)
        linked = self._index.page_at(self._page.source_path.parent / path) if self._page else None
        slug = linked.slug if linked else self._page_slug(Path(path).stem)
        anchor = _org_anchor(linked, search) if search else ""
        return syntax.page_link(self._index.href(slug, anchor), label or (linked.title if linked else Path(path).stem))

    # ── Files ────────────────────────────────────────────────────────────────

    def _asset(self, path: str, label: str | None) -> str:
        self.assets.append(path)
        return self._syntax.asset(path, label)

    def _linked_file(self, target: str) -> str:
        """Project-relative path of a linked file: looked up next to the page,
        else (Logseq habit) by name in assets/."""
        root = self._resolver.root
        if root is not None and self._page is not None:
            candidate = (self._page.source_path.parent / target).resolve()
            if candidate.is_file() and candidate.is_relative_to(root):
                return candidate.relative_to(root).as_posix()
        return f"assets/{Path(target).name}"

    def _html_page_exists(self, path: str) -> bool:
        """Whether a linked HTML page will be in the site: next to the linking
        page (pages/ subfolder) or in an external static folder."""
        if self._resolver.root is None or self._page is None:
            return True  # nowhere to look: trust the link
        if (self._page.source_path.parent / path).is_file():
            return True
        # Each static folder is served as /<its name>/.
        first = Path(path).parts[:1]
        return any(first == (d.name,) and (d.parent / path).is_file() for d in self._resolver.static_dirs)

    # ── Videos ───────────────────────────────────────────────────────────────

    def _video_macro(self, m: re.Match) -> str:
        embed = youtube_embed(m.group(1))
        if embed is not None:
            return self._syntax.raw_html(embed)
        # Not a YouTube video: at least a link to it.
        return self._syntax.bare_external(m.group(1)) if m.group(1).startswith(("http://", "https://")) else m.group(0)

    def _video_link(self, m: re.Match) -> str:
        embed = youtube_embed(m.group(1))
        return m.group(0) if embed is None else self._syntax.raw_html(embed)

    # ── Logseq block refs ────────────────────────────────────────────────────

    def _block_refs(self, content: str) -> str:
        """((uuid)) → a link to the block, showing its text; with a label, that label."""
        if self._syntax.org_links:
            content = _ORG_LABELED_BLOCK_REF.sub(lambda m: self._block_link(m.group(1), m.group(2)), content)
        else:
            content = _MD_LABELED_BLOCK_REF.sub(lambda m: self._block_link(m.group(2), m.group(1)), content)
        return _BLOCK_REF.sub(lambda m: self._block_link(m.group(1), None), content)

    def _block_link(self, uuid: str, label: str | None) -> str:
        hit = self._index.block(uuid)
        if hit is None:
            self._broken(f"(({uuid}))")
            return label or f"(({uuid}))"
        linked, block = hit
        return self._syntax.page_link(self._index.href(linked.slug, block.anchor), label or block.text or linked.title)
