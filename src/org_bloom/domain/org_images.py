"""`#+ATTR_ORG` image options (how Emacs shows an image), turned into the
`#+ATTR_HTML` Pandoc applies to the <img>."""

import re

_AFFILIATED = re.compile(r"^[ \t]*#\+\w+:", re.IGNORECASE)
_ATTR_ORG = re.compile(r"^([ \t]*)#\+ATTR_ORG:(.*)$", re.IGNORECASE)
_ATTR_HTML = re.compile(r"^[ \t]*#\+ATTR_HTML:(.*)$", re.IGNORECASE)
# :key value pairs; a value runs up to the next :key, so it may hold spaces.
_PLIST = re.compile(r"(?<!\S):([\w-]+)(?:[ \t]+(.*?))?(?=[ \t]+:[\w-]+(?:[ \t]|$)|[ \t]*$)")
# #+ATTR_ORG keys that mean the same thing as an HTML attribute.
_HTML_KEYS = ("alt", "title", "height", "class", "id")
_MARGINS = {
    "center": "margin-left:auto;margin-right:auto",
    "right": "margin-left:auto;margin-right:0",
}


def _plist(text: str) -> dict[str, str]:
    return {m.group(1).lower(): (m.group(2) or "").strip() for m in _PLIST.finditer(text)}


def _html_width(value: str) -> str:
    """Org's image width as HTML wants it: 981 and 981px are pixels, 50% stays a
    percentage and a fraction like 0.5 (part of the text width) becomes 50%."""
    if re.fullmatch(r"\d+px", value, re.IGNORECASE):
        return value[:-2]
    if re.fullmatch(r"0?\.\d+|1\.0*", value):
        return f"{float(value) * 100:g}%"
    return value


def _org_image_attrs(org: dict[str, str]) -> dict[str, str]:
    """The HTML attributes for an image's #+ATTR_ORG: :width, :align
    (left/center/right) and :background (a color, for transparent images), plus
    the HTML ones people also write there (:alt, :title, :height, :class, :id,
    :style). Emacs-only options are left out."""
    attrs = {key: org[key] for key in _HTML_KEYS if org.get(key)}
    if org.get("width"):
        attrs["width"] = _html_width(org["width"])
    style = [org["style"].rstrip(";")] if org.get("style") else []
    if org.get("align", "").lower() in _MARGINS:
        style.append(_MARGINS[org["align"].lower()])
    background = org.get("background", "").strip("\"")
    if background and background.lower() not in ("t", "nil"):
        style.append(f"background-color:{background}")
    if style:
        attrs["style"] = ";".join(style)
    return attrs


def attr_org_to_html(content: str) -> str:
    """Turn the image options of `#+ATTR_ORG:` (how Emacs shows an image) into
    `#+ATTR_HTML:`, which Pandoc applies to the <img>. Pandoc ignores
    #+ATTR_ORG and, worse, drops a #+CAPTION above it, so every #+ATTR_ORG line
    goes. A key also set by an #+ATTR_HTML on the same image keeps that value:
    it is meant for the web."""
    lines = content.splitlines(keepends=True)
    out = []
    i = 0
    while i < len(lines):
        if not _AFFILIATED.match(lines[i]):
            out.append(lines[i])
            i += 1
            continue
        block_end = i
        while block_end < len(lines) and _AFFILIATED.match(lines[block_end]):
            block_end += 1
        block = lines[i:block_end]
        html_keys = set()
        for line in block:
            if m := _ATTR_HTML.match(line.rstrip("\n")):
                html_keys |= _plist(m.group(1)).keys()
        for line in block:
            attr = _ATTR_ORG.match(line.rstrip("\n"))
            if attr is None:
                out.append(line)
                continue
            attrs = {k: v for k, v in _org_image_attrs(_plist(attr.group(2))).items() if k not in html_keys}
            if attrs:
                newline = "\n" if line.endswith("\n") else ""
                options = " ".join(f":{key} {value}" for key, value in attrs.items())
                out.append(f"{attr.group(1)}#+ATTR_HTML: {options}{newline}")
        i = block_end
    return "".join(out)
