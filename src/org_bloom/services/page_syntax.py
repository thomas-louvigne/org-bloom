"""How each source format (Org, Markdown) writes what the link resolver
rewrites, and the clean-up a page gets before its links are read."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..domain.blocks import strip_md_properties
from ..domain.org_images import attr_org_to_html
from ..domain.org_syntax import expand_targets
from ..domain.page import PageFormat
from ..domain.paths import is_image

# Link targets left to the browser.
URL_PREFIXES = ("http://", "https://", "mailto:", "ftp://", "tel:", "doi:", "news:", "irc:")

_PROPERTIES_BLOCK = re.compile(r":PROPERTIES:.*?:END:", re.DOTALL)
_LOGBOOK_BLOCK = re.compile(r":LOGBOOK:.*?:END:", re.DOTALL)
# Logseq page properties (`title:: …`), at the very start of a page.
MD_PROPERTIES_BLOCK = re.compile(r"^(?:[a-z][a-z0-9_-]*::[^\n]*\n?)+", re.IGNORECASE)
_PUBLIC_DIRECTIVE = re.compile(r"#\+PUBLIC:[^\n]*\n?", re.IGNORECASE)
_EMPTY_HEADING = re.compile(r"^\*+\s*$", re.MULTILINE)


def _clean_org(content: str) -> str:
    # MD_PROPERTIES_BLOCK only matches at the very start of the file, so it
    # runs again once #+PUBLIC is gone in case properties followed it.
    for pattern in (
        MD_PROPERTIES_BLOCK, _PUBLIC_DIRECTIVE, MD_PROPERTIES_BLOCK,
        _PROPERTIES_BLOCK, _LOGBOOK_BLOCK, _EMPTY_HEADING,
    ):
        content = pattern.sub("", content)
    return expand_targets(attr_org_to_html(content))


def _clean_md(content: str) -> str:
    return strip_md_properties(MD_PROPERTIES_BLOCK.sub("", content), anchors=True)


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
class Syntax:
    """How one source format spells the links the resolver rewrites."""

    format: PageFormat
    clean: Callable[[str], str]
    # The text of an embedded block or page, cleaned without adding the
    # anchors its own page already has.
    clean_embedded: Callable[[str], str]
    link: Callable[[str, str], str]  # (href, label)
    asset: Callable[[str, str | None], str]  # (path under assets/, label)
    bare_external: Callable[[str], str]  # unlabeled external URL
    raw_html: Callable[[str], str]  # HTML passed through to the page as is
    page_href_prefix: str = ""
    # Extra prefixes that mark an unlabeled [[target]] as an asset.
    asset_prefixes: tuple[str, ...] = ()

    @property
    def org_links(self) -> bool:
        """Org-mode links: file:, id:, [[*Headline]] and [[#custom-id]]."""
        return self.format == "org"

    def page_link(self, href: str, label: str) -> str:
        """A link to a page of the site (`href` like `page.html#anchor`)."""
        return self.link(self.page_href_prefix + href, label)


SYNTAXES: dict[PageFormat, Syntax] = {
    "org": Syntax(
        format="org",
        clean=_clean_org,
        clean_embedded=_clean_org,
        link=lambda href, label: f"[[{href}][{label}]]",
        asset=_org_asset,
        bare_external=lambda target: f"[[{target}]]",
        raw_html=lambda html: f"@@html:{html}@@",
        # pandoc org parser requires "file:" prefix to emit a real <a> tag
        page_href_prefix="file:",
    ),
    "md": Syntax(
        format="md",
        clean=_clean_md,
        clean_embedded=lambda content: strip_md_properties(content, anchors=False),
        link=lambda href, label: f"[{label}]({href})",
        asset=_md_asset,
        bare_external=lambda target: f"<{target}>",
        raw_html=lambda html: html,
        asset_prefixes=("assets/",),
    ),
}
