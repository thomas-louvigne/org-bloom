"""YouTube videos shown in the page: `{{video URL}}` (Logseq) and a bare
`[[URL]]` (Orgamnesia) become an embedded player."""

import re
from urllib.parse import parse_qs, urlsplit

_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_YOUTUBE_HOSTS = frozenset({
    "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
    "youtube-nocookie.com", "www.youtube-nocookie.com",
})
# Paths that carry the id themselves: /embed/ID, /shorts/ID, /live/ID, /v/ID.
_ID_PATH = re.compile(r"^/(?:embed|shorts|live|v)/([^/?#]+)")
# t=90, t=90s, t=1m30s, t=1h2m3s
_DURATION = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?$")
# The privacy-enhanced player: no cookie until the reader presses play.
_EMBED_URL = "https://www.youtube-nocookie.com/embed/"


def youtube_id(url: str) -> tuple[str, int] | None:
    """(video id, start in seconds) of a YouTube video URL, None for any other
    URL. youtube.com/watch?v=…, youtu.be/…, /shorts/, /live/ and /embed/ are
    understood, with their t= or start= time."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https"):
        return None
    host = (parts.hostname or "").lower()
    query = parse_qs(parts.query)
    if host == "youtu.be":
        video = parts.path.strip("/")
    elif host in _YOUTUBE_HOSTS:
        m = _ID_PATH.match(parts.path)
        video = m.group(1) if m else (query.get("v") or [""])[0]
    else:
        return None
    if not _VIDEO_ID.fullmatch(video):
        return None
    fragment = parse_qs(parts.fragment)
    time = (query.get("t") or query.get("start") or fragment.get("t") or [""])[0]
    return video, _seconds(time)


def _seconds(time: str) -> int:
    m = _DURATION.match(time)
    if not time or m is None:
        return 0
    hours, minutes, seconds = (int(part or 0) for part in m.groups())
    return hours * 3600 + minutes * 60 + seconds


def youtube_embed(url: str) -> str | None:
    """The <iframe> playing a YouTube video URL, None for any other URL. Its
    width and height are YouTube's defaults; the site CSS makes it as wide as
    the text column."""
    found = youtube_id(url)
    if found is None:
        return None
    video, start = found
    src = _EMBED_URL + video + (f"?start={start}" if start else "")
    return (
        f'<iframe class="video-embed" src="{src}" title="YouTube video" width="560" height="315" '
        'loading="lazy" referrerpolicy="strict-origin-when-cross-origin" '
        'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
        "allowfullscreen></iframe>"
    )
