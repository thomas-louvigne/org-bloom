"""The pages a link can lead to, found by name, path, org-roam `:ID:` or
Logseq block id. Looking up reports nothing: the link resolver decides what a
missing target means."""

from pathlib import Path

from ..domain.blocks import Block, md_blocks, org_blocks
from ..domain.org_syntax import property_anchors
from ..domain.page import Page
from ..domain.paths import slugify


class SiteIndex:
    def __init__(self, pages: list[Page], home_slug: str) -> None:
        self._home_slug = home_slug
        self._slug_map = _slug_map(pages)
        self._by_slug = {page.slug: page for page in pages}
        self._by_path = {page.source_path.resolve(): page for page in pages}
        # org-roam [[id:…]] links: the page, and the anchor of the headline
        # holding the :ID: ("" for the file-level drawer).
        self._ids: dict[str, tuple[Page, str]] = {}
        # Logseq blocks by id: ((uuid)) and {{embed ((uuid))}}.
        self._blocks: dict[str, tuple[Page, Block]] = {}
        for page in pages:
            if page.format == "org":
                for org_id, anchor in property_anchors(page.raw_content)[0].items():
                    self._ids.setdefault(org_id, (page, anchor))
            blocks = org_blocks(page.raw_content) if page.format == "org" else md_blocks(page.raw_content)
            for uuid, block in blocks.items():
                self._blocks.setdefault(uuid.lower(), (page, block))

    def href(self, slug: str, anchor: str = "") -> str:
        """The site path of the page `slug`, at `anchor` when given."""
        path = "index.html" if slug == self._home_slug else f"{slug}.html"
        return f"{path}#{anchor}" if anchor else path

    def slug(self, name: str) -> tuple[str, bool]:
        """The slug a page name links to, and whether such a page exists. Case,
        accents and dashes may differ from the page title (e.g. "epoque-medievale"
        vs "Époque Médiévale"): slugify() folds them the way page slugs were made."""
        slug = self._slug_map.get(name.lower())
        if slug is None:
            candidate = slugify(name)
            slug = self._slug_map.get(candidate, candidate)
        return slug, slug in self._by_slug

    def page_named(self, name: str) -> Page | None:
        return self._by_slug.get(self.slug(name)[0])

    def page_by_slug(self, slug: str) -> Page | None:
        return self._by_slug.get(slug)

    def page_at(self, path: Path) -> Page | None:
        return self._by_path.get(path.resolve())

    def org_id(self, org_id: str) -> tuple[Page, str] | None:
        return self._ids.get(org_id)

    def block(self, uuid: str) -> tuple[Page, Block] | None:
        return self._blocks.get(uuid.lower())


def _slug_map(pages: list[Page]) -> dict[str, str]:
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
