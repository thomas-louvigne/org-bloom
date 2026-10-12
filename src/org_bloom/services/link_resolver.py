import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..domain.org_syntax import headline_anchors, pandoc_anchor, property_anchors
from ..domain.page import Page, PageFormat
from ..domain.paths import is_image, slugify

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


# Link targets left to the browser.
_URL_PREFIXES = ("http://", "https://", "mailto:", "ftp://", "tel:", "doi:", "news:", "irc:")

# [[../assets/file]] or [[../assets/file][label]]
_ASSET_REL = re.compile(r"\[\[\.\./assets/([^\]]+)\](?:\[([^\]]+)\])?\]")
_LABELED_LINK = re.compile(r"\[\[([^\]]+)\]\[([^\]]+)\]\]")
_SIMPLE_LINK = re.compile(r"\[\[([^\]]+)\]\]")
_HASHTAG_COMPOUND = re.compile(r"#\[\[([^\]]+)\]\]")
# Matches #word hashtags — excludes #+directives, #[[compound]] (handled separately),
# and labels already inside generated links (preceded by [ in org ][#tag] or md [#tag]).
_HASHTAG_SIMPLE = re.compile(r"(?<![a-zA-Z0-9_\[])#([^\W\d_][\w-]*)")
_PROPERTIES_BLOCK = re.compile(r":PROPERTIES:.*?:END:", re.DOTALL)
_LOGBOOK_BLOCK = re.compile(r":LOGBOOK:.*?:END:", re.DOTALL)
_MD_PROPERTIES_BLOCK = re.compile(r"^(?:[a-z][a-z0-9_-]*::[^\n]*\n?)+", re.IGNORECASE)
_PUBLIC_DIRECTIVE = re.compile(r"#\+PUBLIC:[^\n]*\n?", re.IGNORECASE)
_EMPTY_HEADING = re.compile(r"^\*+\s*$", re.MULTILINE)


def _clean_org(content: str) -> str:
    # _MD_PROPERTIES_BLOCK only matches at the very start of the file, so it
    # runs again once #+PUBLIC is gone in case properties followed it.
    for pattern in (
        _MD_PROPERTIES_BLOCK, _PUBLIC_DIRECTIVE, _MD_PROPERTIES_BLOCK,
        _PROPERTIES_BLOCK, _LOGBOOK_BLOCK, _EMPTY_HEADING,
    ):
        content = pattern.sub("", content)
    return content


def _clean_md(content: str) -> str:
    return _MD_PROPERTIES_BLOCK.sub("", content)


# Asset paths are relative to the project root (`assets/photo.png`,
# `images/schema.png`); the file is copied to the same path in the site.


def _org_asset(path: str, label: str | None) -> str:
    # No label → pandoc emits <img> for images, which is what we want.
    # file: prefix is required for pandoc to resolve the link at all.
    return f"[[file:{path}][{label}]]" if label else f"[[file:{path}]]"


def _md_asset(path: str, label: str | None) -> str:
    bang = "!" if is_image(path) else ""
    return f"{bang}[{label or Path(path).name}]({path})"


@dataclass(frozen=True)
class _Syntax:
    """How one source format spells the links the resolver rewrites."""

    clean: Callable[[str], str]
    link: Callable[[str, str], str]  # (href, label)
    asset: Callable[[str, str | None], str]  # (path under assets/, label)
    bare_external: Callable[[str], str]  # unlabeled external URL
    external_prefixes: tuple[str, ...]
    page_href_prefix: str = ""
    # Extra prefixes that mark an unlabeled [[target]] as an asset.
    asset_prefixes: tuple[str, ...] = ()
    # Org-mode links: file:, id:, [[*Headline]] and [[#custom-id]].
    org_links: bool = False


_SYNTAXES: dict[PageFormat, _Syntax] = {
    "org": _Syntax(
        clean=_clean_org,
        link=lambda href, label: f"[[{href}][{label}]]",
        asset=_org_asset,
        bare_external=lambda target: f"[[{target}]]",
        external_prefixes=_URL_PREFIXES,
        # pandoc org parser requires "file:" prefix to emit a real <a> tag
        page_href_prefix="file:",
        org_links=True,
    ),
    "md": _Syntax(
        clean=_clean_md,
        link=lambda href, label: f"[{label}]({href})",
        asset=_md_asset,
        bare_external=lambda target: f"<{target}>",
        external_prefixes=_URL_PREFIXES,
        asset_prefixes=("assets/",),
    ),
}


class LinkResolver:
    def __init__(
        self,
        pages: list[Page],
        home_slug: str,
        root: Path | None = None,
        static_dirs: list[Path] | None = None,
        html_links: bool = True,
    ) -> None:
        self._slug_map = self._build_slug_map(pages)
        self._known_slugs = frozenset(page.slug for page in pages)
        self._home_slug = home_slug
        # Project root: relative file links are looked up from the linking page
        # and must stay inside it.
        self._root = root.resolve() if root is not None else None
        self._pages_by_path = {page.source_path.resolve(): page for page in pages}
        self._ids: dict[str, tuple[Page, str]] = {}
        for page in pages:
            if page.format == "org":
                ids, _ = property_anchors(page.raw_content)
                for org_id, anchor in ids.items():
                    self._ids.setdefault(org_id, (page, anchor))
        # Folders copied to the site root as they are (external_static_dirs).
        self._static_dirs = static_dirs or []
        # False: every link to a hand-made HTML page leads to 404.html.
        self._html_links = html_links
        # (source_page_title, target) pairs for links that resolve to no known page.
        self.broken_links: list[tuple[str, str]] = []
        # (source_page_title, target) pairs for HTML pages sent to 404.html.
        self.missing_files: list[tuple[str, str]] = []

    def _build_slug_map(self, pages: list[Page]) -> dict[str, str]:
        slug_map: dict[str, str] = {}
        for page in pages:
            slug_map[page.title.lower()] = page.slug
            slug_map[page.slug.lower()] = page.slug
        # A page whose #+TITLE differs from its filename can also be linked by
        # filename (e.g. [[ma-page]] → mon-super-titre.html). Titles and slugs
        # win on collision.
        for page in pages:
            slug_map.setdefault(slugify(page.source_path.stem), page.slug)
        return slug_map

    def _slug_href(self, slug: str) -> str:
        return "index.html" if slug == self._home_slug else f"{slug}.html"

    def _page_name_to_href(self, target: str, source: str) -> str:
        slug = self._slug_map.get(target.lower())
        if slug is None:
            # Case/accents/dashes may differ from the page title (e.g. "epoque-tracogna"
            # vs "Époque Tracogna") yet still resolve to the same page — slugify() folds
            # accents and normalizes separators the same way page slugs were generated.
            candidate = slugify(target)
            slug = self._slug_map.get(candidate, candidate)
            if slug not in self._known_slugs:
                self.broken_links.append((source, target))
        return self._slug_href(slug)

    def _linked_file(self, target: str, page: Page | None) -> str:
        """Project-relative path of a file linked from `page`: looked up next to
        the page, else (Logseq habit) by name in assets/."""
        if self._root is not None and page is not None:
            candidate = (page.source_path.parent / target).resolve()
            if candidate.is_file() and candidate.is_relative_to(self._root):
                return candidate.relative_to(self._root).as_posix()
        return f"assets/{Path(target).name}"

    def _html_page_exists(self, path: str, page: Page | None) -> bool:
        """Whether a linked HTML page will be in the site: next to the linking
        page (pages/ subfolder) or in an external static folder."""
        if self._root is None or page is None:
            return True  # nowhere to look: trust the link
        candidates = [page.source_path.parent / path, *(d / path for d in self._static_dirs)]
        return any(c.is_file() for c in candidates)

    def _org_anchor(self, page: Page | None, search: str) -> str:
        """Anchor for an org search option: `*Headline` or `#custom-id`."""
        if search.startswith("*"):
            title = search[1:].strip()
            anchors = headline_anchors(page.raw_content) if page else {}
            return anchors.get(title, pandoc_anchor(title))
        if search.startswith("#"):
            _, custom_ids = property_anchors(page.raw_content) if page else ({}, {})
            return custom_ids.get(search[1:], search[1:])
        return ""

    def preprocess_org(self, content: str, source: str = "") -> tuple[str, list[str]]:
        """Clean and rewrite org content for pandoc.

        Returns (processed_content, list_of_asset_paths).
        """
        return self._preprocess(content, source, _SYNTAXES["org"], None)

    def preprocess_md(self, content: str, source: str = "") -> tuple[str, list[str]]:
        """Rewrite Logseq markdown content for pandoc."""
        return self._preprocess(content, source, _SYNTAXES["md"], None)

    def preprocess(
        self, content: str, fmt: PageFormat, source: str = "", page: Page | None = None
    ) -> tuple[str, list[str]]:
        return self._preprocess(content, source, _SYNTAXES[fmt], page)

    def _preprocess(
        self, content: str, source: str, syntax: _Syntax, page: Page | None
    ) -> tuple[str, list[str]]:
        assets: list[str] = []

        def asset(path: str, label: str | None) -> str:
            assets.append(path)
            return syntax.asset(path, label)

        def page_link(target: str, label: str) -> str:
            return syntax.link(syntax.page_href_prefix + self._page_name_to_href(target, source), label)

        def org_link(target: str, label: str | None) -> str | None:
            """file:, id:, *Headline and #custom-id links; None for any other target."""
            if target.startswith(("*", "#")):
                return syntax.link("#" + self._org_anchor(page, target), label or target.lstrip("*#"))
            if target.startswith("id:"):
                hit = self._ids.get(target[3:])
                if hit is None:
                    self.broken_links.append((source, target))
                    return label or target
                linked, anchor = hit
                href = self._slug_href(linked.slug) + (f"#{anchor}" if anchor else "")
                return syntax.link(syntax.page_href_prefix + href, label or linked.title)
            if not target.startswith("file:"):
                return None
            path, _, search = target[len("file:"):].partition("::")
            if Path(path).suffix.lower() in (".html", ".htm") and Path(path).parts[:1] != ("assets",):
                # A custom HTML page next to the notes, copied as is (see copy_pages_subdirs).
                # An HTML file in assets/ is an attachment, already listed for copy.
                if not self._html_links or not self._html_page_exists(path, page):
                    self.missing_files.append((source, path))
                    return syntax.link(syntax.page_href_prefix + "404.html", label or path)
                return syntax.link(target, label or path)
            if Path(path).suffix.lower() not in (".org", ".md"):
                return asset(self._linked_file(path, page), label)
            linked = None
            if page is not None:
                linked = self._pages_by_path.get((page.source_path.parent / path).resolve())
            if linked is None:
                href = self._page_name_to_href(Path(path).stem, source)
            else:
                href = self._slug_href(linked.slug)
            anchor = self._org_anchor(linked, search) if search else ""
            href += f"#{anchor}" if anchor else ""
            return syntax.link(syntax.page_href_prefix + href, label or (linked.title if linked else Path(path).stem))

        content = syntax.clean(content)

        content = _ASSET_REL.sub(lambda m: asset(f"assets/{m.group(1)}", m.group(2)), content)

        # _LABELED_LINK first: [[page][label]] — must precede _HASHTAG_COMPOUND so
        # the resulting link is never re-processed by later patterns.
        def replace_labeled(m: re.Match) -> str:
            target, label = m.group(1), m.group(2)
            if syntax.org_links and (link := org_link(target, label)) is not None:
                return link
            if target.startswith(syntax.external_prefixes):
                return syntax.link(target, label)
            if _looks_like_file(target):
                return asset(self._linked_file(target, page), label)
            return page_link(target, label)

        content = _LABELED_LINK.sub(replace_labeled, content)

        # _HASHTAG_COMPOUND after _LABELED_LINK (safe: #[[tag]] has no ][ inside)
        # and before _SIMPLE_LINK (to prevent [[tag]] inside #[[tag]] being caught).
        # The generated org [[file:...][#tag]] is not re-caught because _SIMPLE_LINK
        # requires ]] immediately after the target.
        content = _HASHTAG_COMPOUND.sub(lambda m: page_link(m.group(1), f"#{m.group(1)}"), content)

        def replace_simple(m: re.Match) -> str:
            target = m.group(1)
            if syntax.org_links and (link := org_link(target, None)) is not None:
                return link
            if target.startswith(syntax.external_prefixes):
                return syntax.bare_external(target)
            if target.startswith(syntax.asset_prefixes) or _looks_like_file(target):
                return asset(self._linked_file(target, page), None)
            return page_link(target, target)

        content = _SIMPLE_LINK.sub(replace_simple, content)

        # _HASHTAG_SIMPLE last: #word has no overlap with [[...]] syntax.
        content = _HASHTAG_SIMPLE.sub(lambda m: page_link(m.group(1), f"#{m.group(1)}"), content)

        return content, assets
