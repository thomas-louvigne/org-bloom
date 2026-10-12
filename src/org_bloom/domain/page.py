import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

PageFormat = Literal["org", "md"]

# Buttons of the share bar under each page title, in display order; each one
# can be switched off from the [share] table of org-bloom.toml.
SHARE_BUTTONS = ("native", "whatsapp", "facebook", "x", "bluesky", "linkedin", "email", "copy_link", "print")
# "horizontal": a row under the title; "vertical": a column pinned to the
# right edge of the screen (falls back to the row on narrow screens).
ShareLayout = Literal["horizontal", "vertical"]
SHARE_LAYOUTS: tuple[ShareLayout, ...] = ("horizontal", "vertical")


@dataclass
class Page:
    title: str
    slug: str
    raw_content: str
    source_path: Path
    format: PageFormat
    is_public: bool
    html_content: str = ""
    description: str = ""
    icon: str = ""
    asset_filenames: list[str] = field(default_factory=list)
    # Journal/blog posts: from the file name or #+DATE; other pages: #+DATE.
    date: datetime.date | None = None
    # Journal posts only: the date as journal_page_title_format writes it.
    date_label: str = ""
    headline: str = ""  # journal posts only: title parsed from the entry's own content
    author: str = ""  # #+AUTHOR / author::, shown only when the page has one
    tags: list[str] = field(default_factory=list)  # page tags: #+FILETAGS, tags::

    @property
    def output_filename(self) -> str:
        return f"{self.slug}.html"


@dataclass
class TaggedHeadline:
    """An org headline carrying a tag (`* Title :tag:`)."""

    page: Page
    title: str
    anchor: str


@dataclass
class TagEntry:
    name: str
    pages: list[Page] = field(default_factory=list)
    headlines: list[TaggedHeadline] = field(default_factory=list)


@dataclass
class SiteConfig:
    title: str
    author: str = ""
    description: str = ""
    base_url: str = ""
    social_links: dict[str, str] = field(default_factory=dict)
    home_slug: str = "index"
    menu: list[dict[str, str | bool]] = field(default_factory=list)
    org_listify_headings_from: int | Literal["auto"] | None = "auto"
    # From config.edn
    all_public: bool = False
    hidden: list[str] = field(default_factory=list)
    pages_directory: str = "pages"
    journals_directory: str = "journals"
    # Blog / journals feature
    enable_journals: bool = False
    journal_page_title_format: str = "dd-MM-yyyy"
    journal_file_name_format: str = "yyyy_MM_dd"
    blog_title: str = "Blog"
    blog_slug: str = "blog"
    rss: bool = False
    lang: str = "en"
    tree_view: bool = True
    external_static_dirs: list[str] = field(default_factory=list)
    # False: build without the hand-made web folders (external_static_dirs and
    # pages/ subfolders holding HTML); links to them lead to 404.html.
    external_deps: bool = True
    share: dict[str, bool] = field(default_factory=lambda: dict.fromkeys(SHARE_BUTTONS, True))
    share_layout: ShareLayout = "horizontal"
