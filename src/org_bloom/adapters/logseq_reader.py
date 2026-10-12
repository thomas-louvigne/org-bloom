import datetime
import re
import urllib.parse
from pathlib import Path
from typing import Iterator

from ..domain.dates import human_date, parse_date
from ..domain.org_syntax import NOEXPORT, drop_title_headline, filetags
from ..domain.page import Page, PageFormat
from ..ports.interfaces import PageRepository
from ..domain.paths import slugify
from .edn_config_loader import load_edn_config

_PUBLIC_TRUE = re.compile(r"(?:#\+PUBLIC:\s*true|^public::\s*true\b)", re.IGNORECASE | re.MULTILINE)
_PUBLIC_FALSE = re.compile(r"(?:#\+PUBLIC:\s*false|^public::\s*false\b)", re.IGNORECASE | re.MULTILINE)
_DATE_DIRECTIVE = re.compile(r"(?:^#\+DATE:|^date::)[ \t]*(.+)", re.IGNORECASE | re.MULTILINE)
_AUTHOR_DIRECTIVE = re.compile(r"(?:^#\+AUTHOR:|^author::)[ \t]*(.+)", re.IGNORECASE | re.MULTILINE)
# Logseq page tags in Markdown: `tags:: a, [[b c]]` (Org pages use #+filetags).
_LOGSEQ_TAGS = re.compile(r"^tags::[ \t]*(.+)", re.IGNORECASE | re.MULTILINE)
# org-roam keeps its daily notes in daily/, Logseq in journals/.
_JOURNAL_DIRS = ("journals", "daily")
# Folders never read as pages in an org project (besides hidden ones).
_SKIPPED_DIRS = frozenset({"assets", "logseq"})
_TITLE_DIRECTIVE = re.compile(r"(?:#\+TITLE:|^title::)\s*(.+)", re.IGNORECASE | re.MULTILINE)
_DESCRIPTION_DIRECTIVE = re.compile(r"(?:#\+DESCRIPTION:|^description::)\s*(.+)", re.IGNORECASE | re.MULTILINE)
_ORG_ICON = re.compile(r"^:icon:\s*(.+)", re.MULTILINE)
_MD_ICON = re.compile(r"^icon::\s*(.+)", re.IGNORECASE | re.MULTILINE)
_ORG_HEADING = re.compile(r"^\*+\s+(.+)$", re.MULTILINE)
_MD_HEADING = re.compile(r"^#+\s+(.+)$", re.MULTILINE)


def _page_format(path: Path) -> PageFormat:
    return "org" if path.suffix == ".org" else "md"


def _decode_logseq_filename(stem: str) -> str:
    """Decode Logseq triple-lowbar filename encoding (namespace separator '/')."""
    parts = stem.split("___")
    return parts[-1]


def _parse_title(content: str, filename_stem: str) -> str:
    m = _TITLE_DIRECTIVE.search(content)
    if m:
        return m.group(1).strip()
    decoded = urllib.parse.unquote(_decode_logseq_filename(filename_stem))
    readable = decoded.replace("-", " ").replace("_", " ")
    return readable.strip()


def _parse_description(content: str) -> str:
    m = _DESCRIPTION_DIRECTIVE.search(content)
    return m.group(1).strip() if m else ""


def _parse_icon(content: str) -> str:
    m = _ORG_ICON.search(content) or _MD_ICON.search(content)
    return m.group(1).strip() if m else ""


def _parse_tags(content: str) -> list[str]:
    """Page tags: #+FILETAGS (org-mode, Logseq org pages) and tags:: (Logseq Markdown)."""
    tags = filetags(content)
    for value in _LOGSEQ_TAGS.findall(content):
        tags += [t.strip().strip("[]#").strip() for t in value.split(",")]
    return list(dict.fromkeys(t for t in tags if t))


def _parse_author(content: str) -> str:
    m = _AUTHOR_DIRECTIVE.search(content)
    return m.group(1).strip() if m else ""


def _parse_date_directive(content: str) -> datetime.date | None:
    m = _DATE_DIRECTIVE.search(content)
    return parse_date(m.group(1)) if m else None


def _parse_is_public(content: str, all_public: bool) -> bool:
    """Opt-in (#+PUBLIC: true) unless all_public, then opt-out (#+PUBLIC: false).
    A page tagged noexport is never published."""
    if NOEXPORT in _parse_tags(content):
        return False
    if all_public:
        return not _PUBLIC_FALSE.search(content)
    return bool(_PUBLIC_TRUE.search(content))


def _parse_headline(content: str, fmt: str) -> str:
    """Best-effort title for a journal entry: an explicit #+TITLE:/title::
    directive, else its first heading, else empty (falls back to the date)."""
    m = _TITLE_DIRECTIVE.search(content)
    if m:
        return m.group(1).strip()
    heading_re = _ORG_HEADING if fmt == "org" else _MD_HEADING
    m = heading_re.search(content)
    return m.group(1).strip() if m else ""


def _java_date_fmt_to_strftime(fmt: str) -> str:
    """Convert a Java/Logseq date format string to Python strftime format.

    Uses a single-pass regex so longer tokens are matched first and replaced
    text is never re-scanned.
    """
    tokens = [
        ("EEEE", "%A"),
        ("EEE",  "%a"),
        ("MMMM", "%B"),
        ("MMM",  "%b"),
        ("MM",   "%m"),
        ("M",    "%-m"),
        ("yyyy", "%Y"),
        ("yy",   "%y"),
        ("dd",   "%d"),
        # "do" = ordinal day (1st/2nd/…) — approximated as plain number
        ("do",   "%-d"),
        ("d",    "%-d"),
    ]
    pattern = "|".join(re.escape(t) for t, _ in tokens)
    token_map = dict(tokens)
    return re.sub(pattern, lambda m: token_map[m.group(0)], fmt)


class LogseqReader(PageRepository):
    def __init__(
        self,
        input_dir: Path,
        all_public: bool | None = None,
        pages_directory: str | None = None,
        journals_directory: str | None = None,
        hidden: list[str] | None = None,
        journal_page_title_format: str | None = None,
        journal_file_name_format: str | None = None,
        logseq: bool = True,
        excluded: list[Path] | None = None,
        lang: str = "en",
    ) -> None:
        """`logseq=False` reads a plain org-mode project (Emacs, Orgamnesia):
        `.org` files only, in subfolders too, without the title headline a page
        may start with. `excluded` folders (e.g. the output) are never read."""
        self._input_dir = input_dir
        self._logseq = logseq
        self._suffixes = (".org", ".md") if logseq else (".org",)
        self._excluded = [p.resolve() for p in (excluded or [])]

        edn = load_edn_config(input_dir).get("site", {})
        self._all_public = all_public if all_public is not None else edn.get("all_public", False)
        self._default_home_slug: str | None = slugify(edn["home_page"]) if "home_page" in edn else None

        self._pages_dir = self._resolve_dir(pages_directory or edn.get("pages_directory", "pages"))
        journals = journals_directory or edn.get("journals_directory") or _JOURNAL_DIRS[0]
        if not (input_dir / journals).is_dir():
            journals = self._default_journals_dir()
        self._journals_dir = self._resolve_dir(journals)
        self._hidden = [h.lstrip("/") for h in (hidden or [])]
        if journal_page_title_format is None:
            journal_page_title_format = edn.get("journal_page_title_format", "dd-MM-yyyy" if logseq else "")
        # Empty: the date written out in `lang` (12 octobre 2026).
        self._title_fmt = _java_date_fmt_to_strftime(journal_page_title_format)
        self._lang = lang
        self._file_name_fmt = _java_date_fmt_to_strftime(journal_file_name_format or edn.get("journal_file_name_format", "yyyy_MM_dd"))

    @property
    def default_home_slug(self) -> str | None:
        return self._default_home_slug

    def _default_journals_dir(self) -> str:
        for name in _JOURNAL_DIRS:
            if (self._input_dir / name).is_dir():
                return name
        return _JOURNAL_DIRS[0]

    def _resolve_dir(self, name: str) -> Path:
        candidate = self._input_dir / name
        return candidate if candidate.is_dir() else self._input_dir

    def _is_hidden(self, path: Path) -> bool:
        try:
            rel = path.relative_to(self._input_dir).as_posix()
        except ValueError:
            return False
        return any(rel == h or rel.startswith(h.rstrip("/") + "/") for h in self._hidden)

    def _source_files(self, directory: Path, recursive: bool = False) -> Iterator[Path]:
        """Page files under `directory` (directly, or in subfolders too when
        `recursive`), minus hidden paths."""
        for path in directory.iterdir():
            if path.is_dir():
                if recursive and self._reads_subdir(path):
                    yield from self._source_files(path, recursive)
            elif path.suffix in self._suffixes and not self._is_hidden(path):
                yield path

    def _reads_subdir(self, path: Path) -> bool:
        if path.name.startswith(".") or path.name in _SKIPPED_DIRS or self._is_hidden(path):
            return False
        resolved = path.resolve()
        return resolved != self._journals_dir.resolve() and resolved not in self._excluded

    def find_all(self) -> Iterator[Page]:
        slugs: set[str] = set()
        for path in sorted(self._source_files(self._pages_dir, recursive=not self._logseq)):
            content = path.read_text(encoding="utf-8")
            is_public = _parse_is_public(content, self._all_public)
            title = _parse_title(content, path.stem)
            slug = slugify(title)
            if slug in slugs:
                # Same title in two folders: the later one is named after its path.
                slug = slugify(path.relative_to(self._pages_dir).with_suffix("").as_posix().replace("/", "-"))
            slugs.add(slug)
            if not self._logseq and path.suffix == ".org":
                content = drop_title_headline(content, [title, path.stem])
            yield Page(
                title=title,
                slug=slug,
                raw_content=content,
                source_path=path,
                format=_page_format(path),
                is_public=is_public,
                description=_parse_description(content),
                icon=_parse_icon(content),
                date=_parse_date_directive(content),
                author=_parse_author(content),
                tags=[t for t in _parse_tags(content) if t != NOEXPORT],
            )

    def find_journals(self) -> Iterator[Page]:
        """Yield public journal pages sorted by date descending (newest first)."""
        if not self._journals_dir.is_dir():
            return
        pages: list[Page] = []
        for path in self._source_files(self._journals_dir):
            file_date = self._parse_date(path.stem)
            if file_date is None:
                continue
            content = path.read_text(encoding="utf-8")
            if not _parse_is_public(content, self._all_public):
                continue
            date = _parse_date_directive(content) or file_date
            date_label = self._format_title(date)
            title_match = _TITLE_DIRECTIVE.search(content)
            fmt = _page_format(path)
            slug = f"journal-{file_date.isoformat()}"
            pages.append(Page(
                # An explicit #+TITLE names the post; otherwise its date does.
                title=title_match.group(1).strip() if title_match else date_label,
                slug=slug,
                raw_content=content,
                source_path=path,
                format=fmt,
                is_public=True,
                date=date,
                date_label=date_label,
                headline=_parse_headline(content, fmt),
                author=_parse_author(content),
                tags=[t for t in _parse_tags(content) if t != NOEXPORT],
            ))
        yield from sorted(pages, key=lambda p: p.date, reverse=True)  # type: ignore[arg-type]

    def _parse_date(self, stem: str) -> datetime.date | None:
        """Date of a journal file: journal_file_name_format, else the ISO
        (org-roam dailies) or compact (org-journal) forms."""
        for fmt in (self._file_name_fmt, "%Y-%m-%d", "%Y%m%d"):
            try:
                return datetime.datetime.strptime(stem, fmt).date()
            except ValueError:
                continue
        return None

    def _format_title(self, date: datetime.date) -> str:
        if not self._title_fmt:
            return human_date(date, self._lang)
        try:
            return date.strftime(self._title_fmt)
        except Exception:
            return date.isoformat()
