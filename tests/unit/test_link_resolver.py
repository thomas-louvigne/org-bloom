from pathlib import Path
import pytest

from org_bloom.domain.page import Page
from org_bloom.domain.paths import slugify
from org_bloom.services.link_resolver import LinkResolver


def _make_page(title: str, slug: str | None = None) -> Page:
    s = slug or slugify(title)
    return Page(title=title, slug=s, raw_content="", source_path=Path("/fake"), format="org", is_public=True)


@pytest.fixture
def resolver():
    pages = [
        _make_page("Accueil", "accueil"),
        _make_page("Dragons"),
        _make_page("Marie Curie", "marie-curie"),
        _make_page("Époque Médiévale"),
    ]
    return LinkResolver(pages, home_slug="accueil")


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_accented(self):
        assert slugify("Époque Médiévale") == "epoque-medievale"

    def test_multiple_spaces(self):
        assert slugify("A  B   C") == "a-b-c"

    def test_special_chars(self):
        assert slugify("L'hiver & l'été") == "lhiver-lete"

    def test_already_slug(self):
        assert slugify("hello-world") == "hello-world"

    def test_underscores(self):
        assert slugify("my_page_name") == "my-page-name"


class TestLinkResolverOrg:
    def test_simple_link_to_known_page(self, resolver):
        content = "See [[Dragons]] for details."
        result, _ = resolver.preprocess_org(content)
        assert "[[file:dragons.html][Dragons]]" in result

    def test_simple_link_home(self, resolver):
        content = "Go back to [[Accueil]]."
        result, _ = resolver.preprocess_org(content)
        assert "[[file:index.html][Accueil]]" in result

    def test_labeled_link(self, resolver):
        content = "See [[Marie Curie][la chimiste]]."
        result, _ = resolver.preprocess_org(content)
        assert "[[file:marie-curie.html][la chimiste]]" in result

    def test_url_link_preserved(self, resolver):
        content = "Visit [[https://example.com]]."
        result, _ = resolver.preprocess_org(content)
        assert "[[https://example.com]]" in result

    def test_url_labeled_preserved(self, resolver):
        content = "Visit [[https://example.com][Example]]."
        result, _ = resolver.preprocess_org(content)
        assert "[[https://example.com][Example]]" in result

    def test_asset_link_extracted(self, resolver):
        content = "Image: [[../assets/dragon.png]]"
        result, assets = resolver.preprocess_org(content)
        assert "assets/dragon.png" in assets
        assert "[[file:assets/dragon.png]]" in result

    def test_properties_block_stripped(self, resolver):
        content = ":PROPERTIES:\n:id: abc-123\n:END:\nSome content."
        result, _ = resolver.preprocess_org(content)
        assert ":PROPERTIES:" not in result
        assert "Some content." in result

    def test_public_directive_stripped(self, resolver):
        content = "#+PUBLIC: true\nContent."
        result, _ = resolver.preprocess_org(content)
        assert "#+PUBLIC:" not in result
        assert "Content." in result

    def test_hashtag_compound_removed(self, resolver):
        content = "Tag: #[[Silo-et-Corpo]]"
        result, _ = resolver.preprocess_org(content)
        assert "#[[" not in result
        assert "Silo-et-Corpo" in result

    def test_unknown_page_link_slugified(self, resolver):
        content = "See [[Unknown Page]]."
        result, _ = resolver.preprocess_org(content)
        assert "[[file:unknown-page.html][Unknown Page]]" in result
        assert resolver.broken_links == [("", "Unknown Page")]

    def test_multiple_assets_collected(self, resolver):
        content = "[[../assets/a.jpg]] and [[../assets/b.png]]"
        _, assets = resolver.preprocess_org(content)
        assert "assets/a.jpg" in assets
        assert "assets/b.png" in assets

    def test_hashtag_with_accented_chars(self, resolver):
        content = "* #quêtes"
        result, _ = resolver.preprocess_org(content)
        assert "[[file:quetes.html][#quêtes]]" in result

    def test_no_hashtag_in_keyword_lines(self, resolver):
        content = '#+ATTR_ORG: :background "#ffd"\n[[file:a.png]] #photo\n'
        result, _ = resolver.preprocess_org(content)
        assert "background-color:#ffd" in result
        assert "[[file:photo.html][#photo]]" in result

    def test_simple_link_with_dotted_name(self, resolver):
        content = "Parler à [[Dr. Livia Morozov]] pour plus d'infos."
        result, _ = resolver.preprocess_org(content)
        assert "[[file:dr-livia-morozov.html][Dr. Livia Morozov]]" in result
        assert "assets" not in result


class TestBrokenLinks:
    def test_known_link_not_flagged(self, resolver):
        resolver.preprocess_org("See [[Dragons]].")
        assert resolver.broken_links == []

    def test_unknown_link_flagged_with_source(self, resolver):
        resolver.preprocess_org("See [[Nowhere]].", source="Dragons")
        assert resolver.broken_links == [("Dragons", "Nowhere")]

    def test_unknown_labeled_link_flagged(self, resolver):
        resolver.preprocess_org("See [[Nowhere][here]].", source="Dragons")
        assert resolver.broken_links == [("Dragons", "Nowhere")]

    def test_unknown_hashtag_flagged(self, resolver):
        resolver.preprocess_org("Tag: #nowhere", source="Dragons")
        assert resolver.broken_links == [("Dragons", "nowhere")]

    def test_markdown_unknown_link_flagged(self, resolver):
        resolver.preprocess_md("See [[Nowhere]].", source="Dragons")
        assert resolver.broken_links == [("Dragons", "Nowhere")]

    def test_multiple_pages_accumulate(self, resolver):
        resolver.preprocess_org("See [[Nowhere]].", source="Dragons")
        resolver.preprocess_org("See [[Elsewhere]].", source="Accueil")
        assert resolver.broken_links == [("Dragons", "Nowhere"), ("Accueil", "Elsewhere")]

    def test_uppercase_variant_not_flagged(self, resolver):
        resolver.preprocess_org("See [[MARIE CURIE]].", source="Dragons")
        assert resolver.broken_links == []

    def test_dash_variant_not_flagged(self, resolver):
        resolver.preprocess_org("See [[Marie-Curie]].", source="Dragons")
        assert resolver.broken_links == []

    def test_accent_and_separator_variant_not_flagged(self, resolver):
        resolver.preprocess_org("See [[Époque-Médiévale]].", source="Dragons")
        assert resolver.broken_links == []

    def test_missing_accent_variant_not_flagged(self, resolver):
        resolver.preprocess_org("See [[epoque medievale]].", source="Dragons")
        assert resolver.broken_links == []


class TestLinkResolverMd:
    def test_page_link_has_no_file_prefix(self, resolver):
        # "file:" is only needed by pandoc's org reader; in markdown it would
        # end up verbatim in the href and break the link in the browser.
        result, _ = resolver.preprocess_md("See [[Dragons]].")
        assert "[Dragons](dragons.html)" in result
        assert "file:" not in result

    def test_home_link(self, resolver):
        result, _ = resolver.preprocess_md("Back to [[Accueil]].")
        assert "[Accueil](index.html)" in result

    def test_labeled_link(self, resolver):
        result, _ = resolver.preprocess_md("See [[Marie Curie][la chimiste]].")
        assert "[la chimiste](marie-curie.html)" in result

    def test_hashtags(self, resolver):
        result, _ = resolver.preprocess_md("#Dragons and #[[Marie Curie]]")
        assert "[#Dragons](dragons.html)" in result
        assert "[#Marie Curie](marie-curie.html)" in result

    def test_bare_url(self, resolver):
        result, _ = resolver.preprocess_md("Visit [[https://example.com]].")
        assert "<https://example.com>" in result

    def test_labeled_url(self, resolver):
        result, _ = resolver.preprocess_md("Visit [[https://example.com][Example]].")
        assert "[Example](https://example.com)" in result

    def test_image_and_file_assets(self, resolver):
        result, assets = resolver.preprocess_md("[[../assets/dragon.png]] [[doc.pdf][Le PDF]] [[assets/x.zip]]")
        assert "![dragon.png](assets/dragon.png)" in result
        assert "[Le PDF](assets/doc.pdf)" in result
        assert "[x.zip](assets/x.zip)" in result
        assert assets == ["assets/dragon.png", "assets/doc.pdf", "assets/x.zip"]


class TestLinkByFilename:
    def test_link_by_filename_when_title_differs(self):
        page = Page(title="Mon Super Titre", slug="mon-super-titre", raw_content="",
                    source_path=Path("/g/pages/ma-page.org"), format="org", is_public=True)
        resolver = LinkResolver([page], home_slug="index")
        result, _ = resolver.preprocess_org("[[ma-page]] et [[Ma Page]]")
        assert result.count("file:mon-super-titre.html") == 2
        assert resolver.broken_links == []


class TestOrgLinks:
    @pytest.fixture
    def project(self, tmp_path):
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "guide.pdf").write_bytes(b"%PDF")
        (tmp_path / "secret.txt").write_text("x", encoding="utf-8")
        return tmp_path

    def _page(self, root, name, content, title=None):
        return Page(title=title or name, slug=slugify(title or name), raw_content=content,
                    source_path=root / f"{name}.org", format="org", is_public=True)

    def _resolver(self, root, **options):
        projets = self._page(
            root, "projets",
            ":PROPERTIES:\n:ID: file-id\n:END:\n* Rust\n:PROPERTIES:\n:ID: rust-id\n:CUSTOM_ID: rouille\n:END:\n",
            title="Projets",
        )
        here = self._page(root, "ici", "* Écrire la doc\n** Liens\n:PROPERTIES:\n:CUSTOM_ID: perso\n:END:\n")
        return LinkResolver([projets, here], home_slug="index", root=root, **options), here

    def test_file_link_to_page(self, project):
        resolver, here = self._resolver(project)
        result, _ = resolver.preprocess("[[file:projets.org][mes projets]] [[file:projets.org]]", "org", page=here)
        assert "[[file:projets.html][mes projets]]" in result
        assert "[[file:projets.html][Projets]]" in result

    def test_file_link_with_headline_and_custom_id(self, project):
        resolver, here = self._resolver(project)
        result, _ = resolver.preprocess("[[file:projets.org::*Rust][r]] [[file:projets.org::#rouille][c]]", "org", page=here)
        assert "[[file:projets.html#rust][r]]" in result
        assert "[[file:projets.html#rust][c]]" in result

    def test_id_links(self, project):
        resolver, here = self._resolver(project)
        result, _ = resolver.preprocess("[[id:file-id][p]] [[id:rust-id]]", "org", page=here)
        assert "[[file:projets.html][p]]" in result
        assert "[[file:projets.html#rust][Projets]]" in result
        assert resolver.broken_links == []

    def test_unknown_id_is_plain_text_and_reported(self, project):
        resolver, here = self._resolver(project)
        result, _ = resolver.preprocess("voir [[id:nope][là]]", "org", source="Ici", page=here)
        assert result == "voir là"
        assert resolver.broken_links == [("Ici", "id:nope")]

    def test_links_inside_the_page(self, project):
        resolver, here = self._resolver(project)
        result, _ = resolver.preprocess("[[*Écrire la doc]] [[#perso][ici]]", "org", page=here)
        assert "[[#écrire-la-doc][Écrire la doc]]" in result
        assert "[[#liens][ici]]" in result

    def test_file_next_to_the_page(self, project):
        resolver, here = self._resolver(project)
        result, assets = resolver.preprocess("[[file:docs/guide.pdf][guide]]", "org", page=here)
        assert "[[file:docs/guide.pdf][guide]]" in result
        assert assets == ["docs/guide.pdf"]

    def test_missing_file_falls_back_to_assets(self, project):
        resolver, here = self._resolver(project)
        _, assets = resolver.preprocess("[[file:../outside/photo.png]]", "org", page=here)
        assert assets == ["assets/photo.png"]

    def test_html_file_link_kept(self, project):
        (project / "demo").mkdir()
        (project / "demo" / "index.html").write_text("<p>démo</p>", encoding="utf-8")
        resolver, here = self._resolver(project)
        result, assets = resolver.preprocess("[[file:demo/index.html][démo]]", "org", page=here)
        assert "[[file:demo/index.html][démo]]" in result
        assert assets == []
        assert resolver.missing_files == []

    def test_html_page_in_an_external_static_dir_kept(self, project, tmp_path_factory):
        outside = tmp_path_factory.mktemp("statics")
        (outside / "plan").mkdir()
        (outside / "plan" / "index.html").write_text("<p>plan</p>", encoding="utf-8")
        resolver, here = self._resolver(project, static_dirs=[outside / "plan"])
        result, _ = resolver.preprocess("[[file:plan/index.html][le plan]]", "org", page=here)
        assert "[[file:plan/index.html][le plan]]" in result

    def test_html_page_outside_the_static_folder_name_leads_to_404(self, project, tmp_path_factory):
        outside = tmp_path_factory.mktemp("statics")
        (outside / "plan").mkdir()
        (outside / "plan" / "index.html").write_text("<p>plan</p>", encoding="utf-8")
        (outside / "autre").mkdir()
        (outside / "autre" / "index.html").write_text("<p>autre</p>", encoding="utf-8")
        resolver, here = self._resolver(project, static_dirs=[outside / "plan"])
        result, _ = resolver.preprocess("[[file:autre/index.html][autre]]", "org", page=here)
        assert "[[file:404.html][autre]]" in result

    def test_missing_html_page_leads_to_404(self, project):
        resolver, here = self._resolver(project)
        result, _ = resolver.preprocess("[[file:plan/index.html][le plan]]", "org", page=here)
        assert "[[file:404.html][le plan]]" in result
        assert resolver.missing_files == [("", "plan/index.html")]

    def test_html_links_off_lead_to_404_even_when_present(self, project):
        (project / "demo").mkdir()
        (project / "demo" / "index.html").write_text("<p>démo</p>", encoding="utf-8")
        resolver, here = self._resolver(project, html_links=False)
        result, _ = resolver.preprocess("[[file:demo/index.html][démo]]", "org", page=here)
        assert "[[file:404.html][démo]]" in result

    def test_mailto_left_to_the_browser(self, resolver):
        result, _ = resolver.preprocess_org("[[mailto:a@b.c][écrire]]")
        assert "[[mailto:a@b.c][écrire]]" in result
        assert resolver.broken_links == []


class TestYouTubeVideos:
    URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    EMBED = "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"

    def test_logseq_macro_in_org(self, resolver):
        result, _ = resolver.preprocess_org(f"- {{{{video {self.URL}}}}}")
        assert result.startswith("- @@html:<iframe ")
        assert f'src="{self.EMBED}"' in result
        assert result.endswith("</iframe>@@")

    def test_logseq_macro_in_md(self, resolver):
        result, _ = resolver.preprocess_md(f"- {{{{youtube {self.URL}}}}}")
        assert result.startswith("- <iframe ")
        assert "@@" not in result

    def test_bare_link_in_org(self, resolver):
        result, _ = resolver.preprocess_org(f"[[{self.URL}]]")
        assert result == f"@@html:{result[len('@@html:'):-2]}@@"
        assert f'src="{self.EMBED}"' in result

    def test_labeled_link_stays_a_link(self, resolver):
        result, _ = resolver.preprocess_org(f"[[{self.URL}][la vidéo]]")
        assert result == f"[[{self.URL}][la vidéo]]"

    def test_other_bare_url_stays_a_link(self, resolver):
        result, _ = resolver.preprocess_org("[[https://example.com/page]]")
        assert result == "[[https://example.com/page]]"

    def test_non_youtube_macro_becomes_a_link(self, resolver):
        result, _ = resolver.preprocess_md("{{video https://vimeo.com/123}}")
        assert result == "<https://vimeo.com/123>"
        result, _ = resolver.preprocess_org("{{video https://vimeo.com/123}}")
        assert result == "[[https://vimeo.com/123]]"

    def test_no_broken_link_reported(self, resolver):
        resolver.preprocess_org(f"{{{{video {self.URL}}}}} [[{self.URL}]]")
        assert resolver.broken_links == []
