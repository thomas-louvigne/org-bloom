import re

import pypandoc

from ..ports.interfaces import ContentConverter

_PANDOC_FORMAT_MAP = {
    "org": "org",
    "md": "markdown",
}

# --syntax-highlighting appeared in pandoc 3.8; older versions reject it.
MIN_PANDOC_VERSION = (3, 8)
_INSTALL_URL = "https://pandoc.org/installing.html"


class PandocUnavailable(Exception):
    """Pandoc is missing, or too old for the options org-bloom passes it."""


def check_pandoc() -> str:
    """The installed pandoc version, e.g. "3.12.1". Raises PandocUnavailable
    when pandoc is not found or older than MIN_PANDOC_VERSION."""
    minimum = ".".join(map(str, MIN_PANDOC_VERSION))
    try:
        version = pypandoc.get_pandoc_version()
    except OSError:
        raise PandocUnavailable(
            f"pandoc not found. org-bloom needs pandoc {minimum} or later: {_INSTALL_URL}"
        ) from None
    parsed = tuple(int(part) for part in re.findall(r"\d+", version)[:2])
    if parsed < MIN_PANDOC_VERSION:
        raise PandocUnavailable(
            f"pandoc {version} is too old, org-bloom needs {minimum} or later: {_INSTALL_URL} "
            f"(distribution packages often lag behind; the .deb or tarball from GitHub releases works)."
        )
    return version


class PandocConverter(ContentConverter):
    def convert(self, content: str, fmt: str) -> str:
        pandoc_fmt = _PANDOC_FORMAT_MAP.get(fmt, fmt)
        return pypandoc.convert_text(
            content,
            "html",
            format=pandoc_fmt,
            extra_args=["--syntax-highlighting=none", "--section-divs"],
        )
