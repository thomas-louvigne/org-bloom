import pytest

from org_bloom.domain.video import youtube_embed, youtube_id

ID = "dQw4w9WgXcQ"


@pytest.mark.parametrize("url", [
    f"https://www.youtube.com/watch?v={ID}",
    f"https://youtube.com/watch?feature=share&v={ID}",
    f"https://m.youtube.com/watch?v={ID}",
    f"http://youtu.be/{ID}",
    f"https://youtu.be/{ID}?si=abc",
    f"https://www.youtube.com/shorts/{ID}",
    f"https://www.youtube.com/live/{ID}",
    f"https://www.youtube.com/embed/{ID}",
    f"https://www.youtube-nocookie.com/embed/{ID}",
])
def test_youtube_urls(url):
    assert youtube_id(url) == (ID, 0)


@pytest.mark.parametrize("url, start", [
    (f"https://youtu.be/{ID}?t=42", 42),
    (f"https://youtu.be/{ID}?t=42s", 42),
    (f"https://www.youtube.com/watch?v={ID}&t=1m30s", 90),
    (f"https://www.youtube.com/watch?v={ID}&t=1h2m3s", 3723),
    (f"https://www.youtube.com/embed/{ID}?start=15", 15),
    (f"https://www.youtube.com/watch?v={ID}#t=20", 20),
    (f"https://youtu.be/{ID}?t=nonsense", 0),
])
def test_start_time(url, start):
    assert youtube_id(url) == (ID, start)


@pytest.mark.parametrize("url", [
    "https://vimeo.com/123456",
    "https://www.youtube.com/",
    "https://www.youtube.com/@channel",
    "https://www.youtube.com/watch?v=short",
    "https://www.youtube.com/playlist?list=PL123",
    f"ftp://youtu.be/{ID}",
    f"https://notyoutube.com/watch?v={ID}",
])
def test_not_a_video(url):
    assert youtube_id(url) is None
    assert youtube_embed(url) is None


def test_embed_uses_the_privacy_enhanced_player():
    html = youtube_embed(f"https://youtu.be/{ID}?t=90")
    assert f'src="https://www.youtube-nocookie.com/embed/{ID}?start=90"' in html
    assert 'class="video-embed"' in html
    assert "allowfullscreen" in html
    assert "@@" not in html  # safe inside an org @@html:…@@ snippet
