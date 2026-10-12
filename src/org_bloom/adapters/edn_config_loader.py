import re
from pathlib import Path

_EDN_COMMENT = re.compile(r";[^\n]*")

# TOML [site] key → config.edn key, by value type.
_EDN_BOOLS = {
    "all_public": ":publishing/all-pages-public?",
    "enable_journals": ":feature/enable-journals?",
}
_EDN_STRINGS = {
    "pages_directory": ":pages-directory",
    "journals_directory": ":journals-directory",
    "journal_page_title_format": ":journal/page-title-format",
    "journal_file_name_format": ":journal/file-name-format",
}


# Values of `[site] source` / `--source`: how to read the project.
PROJECT_SOURCES = ("auto", "logseq", "org")
_SOURCE_ALIASES = {"orgamnesia": "org", "org-roam": "org", "emacs": "org"}


def is_logseq_project(source_dir: Path) -> bool:
    """A Logseq graph has a logseq/ folder; anything else is a plain org-mode
    project (Emacs, Orgamnesia)."""
    return (source_dir / "logseq").is_dir()


def resolve_source(source_dir: Path, requested: object) -> tuple[bool, str | None]:
    """Return (logseq, warning). `requested` forces the reading mode, so a
    folder edited with both Logseq and Orgamnesia can be built either way;
    "auto" (or nothing) looks for a logseq/ folder."""
    value = str(requested or "auto").strip().lower()
    value = _SOURCE_ALIASES.get(value, value)
    if value == "logseq":
        return True, None
    if value == "org":
        return False, None
    warning = None
    if value != "auto":
        expected = ", ".join(f"'{s}'" for s in PROJECT_SOURCES)
        warning = f"ignoring source '{requested}' (expected {expected}, or 'orgamnesia')"
    return is_logseq_project(source_dir), warning


def _strip_comments(text: str) -> str:
    return _EDN_COMMENT.sub("", text)


def load_edn_config(source_dir: Path) -> dict:
    """Parse relevant keys from logseq/config.edn and return a TOML-shaped dict."""
    config_path = source_dir / "logseq" / "config.edn"
    if not config_path.exists():
        return {}
    text = _strip_comments(config_path.read_text(encoding="utf-8"))

    site: dict = {}

    for key, edn_key in _EDN_BOOLS.items():
        m = re.search(rf"{re.escape(edn_key)}\s+(true|false)", text)
        if m:
            site[key] = m.group(1) == "true"

    for key, edn_key in _EDN_STRINGS.items():
        m = re.search(rf'{re.escape(edn_key)}\s+"([^"]+)"', text)
        if m:
            site[key] = m.group(1)

    m = re.search(r":default-home\s*\{[^}]*:page\s+\"([^\"]+)\"", text)
    if m:
        site["home_page"] = m.group(1)

    m = re.search(r":hidden\s*\[([^\]]*)\]", text, re.DOTALL)
    if m:
        site["hidden"] = re.findall(r'"([^"]*)"', m.group(1))

    return {"site": site} if site else {}


def generate_toml(source_dir: Path, logseq: bool | None = None) -> Path:
    """Write org-bloom.toml bootstrapped from config.edn values.

    Only writes keys that were actually found in config.edn; everything else
    is left as commented-out examples so the file stays minimal and readable.
    Returns the path of the written file.
    """
    if logseq is None:
        logseq = is_logseq_project(source_dir)
    site = load_edn_config(source_dir).get("site", {}) if logseq else {}

    def val(key: str, default: str, comment: str = "") -> str:
        if key not in site:
            return f"# {key} = {default}"
        raw = site[key]
        if isinstance(raw, bool):
            toml_val = "true" if raw else "false"
        elif isinstance(raw, list):
            toml_val = "[" + ", ".join(f'"{v}"' for v in raw) + "]"
        else:
            toml_val = f'"{raw}"'
        suffix = f"  # from {comment}" if comment else ""
        return f"{key} = {toml_val}{suffix}"

    lines = [
        "# org-bloom.toml",
        *(
            ["# Auto-generated from logseq/config.edn on first run. Edit freely.",
             "# Priority: CLI options > this file > logseq/config.edn"]
            if logseq else
            ["# Auto-generated on first run. Edit freely.",
             "# Priority: CLI options > this file"]
        ),
        "# Full reference: org-bloom.example.toml",
        "",
        "[site]",
        '# title       = "My Site"',
        '# author      = ""',
        '# description = ""',
        '# base_url    = "https://example.com"  # required for sitemap, canonical URLs and RSS',
        '# lang        = "en"                   # HTML lang attribute (e.g. "fr", "de")',
        '# output_dir  = "../my-site"           # used when no output folder is given (wiped on every build)',
        '# source      = "auto"                 # "logseq" (pages/ + logseq/config.edn) or "org" (Orgamnesia, Emacs); auto: logseq/ folder or not',
        "",
        val("home_page", '"home"', ":default-home"),
        val("all_public", "false" if logseq else "true", ":publishing/all-pages-public?"),
        val("hidden", "[]", ":hidden"),
        val("pages_directory", '"pages"', ":pages-directory"),
        val("journals_directory", '"journals"', ":journals-directory"),
        "",
        "# ── Theme ────────────────────────────────────────────────────────────────────",
        "# Built-in: \"default\", \"dark\", \"nord\"  |  or a path relative to this directory",
        '# theme = "default"',
        "",
        "# Vertical + horizontal guide lines connecting nested bullets to their parent.",
        "# tree_view = true",
        "",
        "# ── Blog ─────────────────────────────────────────────────────────────────────",
        "",
        val("enable_journals", "false", ":feature/enable-journals?"),
        '# blog_title = "Blog"',
        '# blog_slug  = "blog"',
        '# rss        = false',
        val("journal_page_title_format", '"dd-MM-yyyy"', ":journal/page-title-format"),
        val("journal_file_name_format", '"yyyy_MM_dd"', ":journal/file-name-format"),
        "",
        "# ── Navigation menu ──────────────────────────────────────────────────────────",
        "# [[menu]]",
        '# label = "Home"',
        '# slug  = "home"',
        "",
        "# ── Social links ─────────────────────────────────────────────────────────────",
        "# [social_networks]",
        '# GitHub = "https://github.com/your-username"',
        "",
    ]

    toml_path = source_dir / "org-bloom.toml"
    toml_path.write_text("\n".join(lines), encoding="utf-8")
    return toml_path
