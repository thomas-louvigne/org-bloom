import re
import unicodedata
from pathlib import Path

IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".bmp", ".ico", ".tiff", ".tif", ".avif",
})


def is_image(filename: str) -> bool:
    return Path(filename).suffix.lower() in IMAGE_EXTENSIONS


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"[^a-z0-9-]", "", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def static_site_folders(folder: Path) -> list[Path]:
    """Folders an [[external_static_dirs]] entry puts at the site root, each as
    /<its name>/: the folder itself when it is a mini-site (index.html at its
    top), else each of its subfolders. Hidden folders (.git…) are left out."""
    if (folder / "index.html").is_file():
        return [folder]
    if not folder.is_dir():
        return []
    return sorted(d for d in folder.iterdir() if d.is_dir() and not d.name.startswith("."))


def tag_href(tag: str) -> str:
    """Page listing everything that carries `tag`."""
    return f"tag-{slugify(tag) or 'tag'}.html"
