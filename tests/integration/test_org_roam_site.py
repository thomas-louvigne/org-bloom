"""Build test-sites/04-org-roam-jardin, a graph written by org-roam itself
(see scripts/make-org-roam-test-site.el), and check what an org-roam user
expects from the site."""

import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from org_bloom import cli

ROAM_GRAPH = Path(__file__).parents[2] / "test-sites" / "04-org-roam-jardin"


@pytest.fixture(autouse=True)
def no_desktop_notification(monkeypatch):
    monkeypatch.setattr(cli, "_notify_desktop", lambda message: None)


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    out = tmp_path_factory.mktemp("roam") / "site"
    result = CliRunner().invoke(cli.main, [str(ROAM_GRAPH), str(out), "--check-links"])
    assert result.exit_code == 0, result.output
    return out, result.output


def _read(site, name):
    out, _ = site
    return (out / name).read_text(encoding="utf-8")


def test_home_page_found_despite_timestamped_file_name(site):
    # 20261012…-accueil.org, #+title: Accueil
    assert "Bienvenue." in _read(site, "index.html")


def test_file_node_id_links(site):
    index = _read(site, "index.html")
    assert 'href="zettelkasten.html"' in index
    assert 'href="ete-a-montreal.html"' in index


def test_headline_node_id_link_reaches_its_anchor(site):
    assert 'href="cuisine.html#tarte-aux-pommes"' in _read(site, "index.html")
    assert 'id="tarte-aux-pommes"' in _read(site, "cuisine.html")


def test_link_label_from_an_alias_is_kept(site):
    # [[id:…][ZK]], ZK being an alias of Zettelkasten
    assert re.search(r'<a href="zettelkasten.html"[^>]*>ZK</a>', _read(site, "ete-a-montreal.html"))


def test_fuzzy_title_link(site):
    assert 'un lien fuzzy: <a href="cuisine.html"' in _read(site, "index.html")


def test_property_drawers_are_not_shown(site):
    out, _ = site
    for page in out.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        assert ":PROPERTIES:" not in text and ":ROAM_ALIASES:" not in text, page.name


def test_noexport_note_stays_private(site):
    out, output = site
    assert not (out / "journal-intime.html").exists()
    everything = "".join(p.read_text(encoding="utf-8") for p in out.rglob("*") if p.is_file())
    assert "Rien à voir ici" not in everything
    # The id: link to it keeps its label as plain text and is reported.
    assert "<a" not in _read(site, "index.html").split("Journal intime")[0].rsplit("<li>", 1)[1]
    assert "referenced in: Accueil" in output


def test_noexport_headline_is_left_out(site):
    cuisine = _read(site, "cuisine.html")
    assert "Tarte aux pommes" in cuisine
    assert "Secret" not in cuisine and "grand-mère" not in cuisine


def test_tags(site):
    assert 'href="tag-methode.html"' in _read(site, "zettelkasten.html")
    assert 'href="cuisine.html#tarte-aux-pommes"' in _read(site, "tag-dessert.html")


def test_dailies_become_the_blog_and_feed(site):
    blog = _read(site, "blog.html")
    assert blog.index("journal-2026-10-12.html") < blog.index("journal-2026-10-11.html")
    assert 'href="cuisine.html"' in _read(site, "journal-2026-10-11.html")
    feed = _read(site, "feed.xml")
    assert "https://notes.example.com/journal-2026-10-12.html" in feed


def test_daily_shows_its_date_once(site):
    # org-roam titles dailies "2026-10-11": only the written-out date is shown.
    for name in ("journal-2026-10-11.html", "blog.html", "feed.xml"):
        text = _read(site, name)
        assert "2026-10-11<" not in text and ">2026-10-11" not in text, name
    main = re.search(r"<main.*</main>", _read(site, "journal-2026-10-11.html"), re.S).group(0)
    visible = re.sub(r"<[^>]+>", " ", main)
    assert visible.count("11 octobre 2026") == 1


def test_timestamps_written_out(site):
    assert "14 juillet 2026" in _read(site, "ete-a-montreal.html")
