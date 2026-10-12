"""Which pages and headlines carry each tag, for the tag pages."""

from ..domain.org_syntax import headline_tags
from ..domain.page import Page, TagEntry, TaggedHeadline
from ..domain.paths import slugify


def collect_tags(pages: list[Page]) -> list[TagEntry]:
    """Every tag of `pages` — page tags (#+FILETAGS, tags::) and org headline
    tags — sorted by name. Tags differing only by case or accents are merged."""
    entries: dict[str, TagEntry] = {}

    def entry(name: str) -> TagEntry:
        return entries.setdefault(slugify(name) or name, TagEntry(name))

    for page in pages:
        for tag in page.tags:
            entry(tag).pages.append(page)
        if page.format == "org":
            for title, anchor, tags in headline_tags(page.raw_content):
                for tag in tags:
                    entry(tag).headlines.append(TaggedHeadline(page, title, anchor))
    return sorted(entries.values(), key=lambda e: e.name.lower())
