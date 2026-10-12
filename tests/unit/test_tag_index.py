from pathlib import Path

from org_bloom.domain.page import Page
from org_bloom.services.tag_index import collect_tags


def _page(title, content="", tags=(), fmt="org"):
    return Page(title=title, slug=title.lower(), raw_content=content, source_path=Path(f"/p/{title}.{fmt}"),
                format=fmt, is_public=True, tags=list(tags))


def test_collects_page_and_headline_tags():
    pages = [
        _page("A", "* Rust :code:\n* Secret :noexport:\n** Caché :code:\n", tags=["Code"]),
        _page("B", "* Python :code:emacs:\n"),
    ]
    tags = {t.name: t for t in collect_tags(pages)}
    assert set(tags) == {"Code", "emacs"}  # "code" merged into "Code"
    assert [p.title for p in tags["Code"].pages] == ["A"]
    assert [(h.page.title, h.title, h.anchor) for h in tags["Code"].headlines] == [("A", "Rust", "rust"), ("B", "Python", "python")]


def test_markdown_headlines_not_parsed():
    assert collect_tags([_page("M", "# Titre :x:\n", fmt="md")]) == []
