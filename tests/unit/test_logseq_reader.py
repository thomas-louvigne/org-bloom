import datetime
from pathlib import Path
import pytest

from org_bloom.adapters.logseq_reader import (
    LogseqReader,
    _decode_logseq_filename,
    _parse_is_public,
    _parse_title,
)


class TestDecodeLogseqFilename:
    def test_simple(self):
        assert _decode_logseq_filename("Dragons") == "Dragons"

    def test_triple_lowbar_namespace(self):
        assert _decode_logseq_filename("Projet-jardin___session-1") == "session-1"

    def test_no_namespace(self):
        assert _decode_logseq_filename("Marie Curie") == "Marie Curie"


class TestParseTitle:
    def test_from_title_directive(self):
        content = "#+TITLE: My Great Page\n* Content"
        assert _parse_title(content, "my-great-page") == "My Great Page"

    def test_from_filename(self):
        content = "* Content"
        assert _parse_title(content, "Dragons") == "Dragons"

    def test_filename_dashes_to_spaces(self):
        content = "* Content"
        assert _parse_title(content, "Marie-Curie") == "Marie Curie"

    def test_filename_percent_encoded_question_mark(self):
        content = "* Content"
        assert _parse_title(content, "Enquête-Qui a mangé la tarte %3F") == "Enquête Qui a mangé la tarte ?"

    def test_filename_percent_encoded_colon(self):
        content = "* Content"
        assert _parse_title(content, "Voyage %3A Au revoir Lisbonne") == "Voyage : Au revoir Lisbonne"


class TestParseIsPublic:
    def test_public_true(self):
        assert _parse_is_public("#+PUBLIC: true\n* Content", all_public=False) is True

    def test_public_false_absent(self):
        assert _parse_is_public("* Content", all_public=False) is False

    def test_all_public_override(self):
        assert _parse_is_public("* Content", all_public=True) is True

    def test_case_insensitive(self):
        assert _parse_is_public("#+public: TRUE\n* x", all_public=False) is True


@pytest.fixture
def fake_source_dir(tmp_path):
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "Home.org").write_text("#+PUBLIC: true\n* Welcome\nHello.", encoding="utf-8")
    (pages / "Private.org").write_text("* Secret content.", encoding="utf-8")
    (pages / "Notes.md").write_text("#+PUBLIC: true\n# Notes\nSome notes.", encoding="utf-8")
    return tmp_path


class TestLogseqReader:
    def test_finds_public_pages(self, fake_source_dir):
        reader = LogseqReader(fake_source_dir)
        public = [p for p in reader.find_all() if p.is_public]
        slugs = {p.slug for p in public}
        assert "home" in slugs
        assert "notes" in slugs

    def test_private_page_not_public(self, fake_source_dir):
        reader = LogseqReader(fake_source_dir)
        private = [p for p in reader.find_all() if p.slug == "private"]
        assert len(private) == 1
        assert private[0].is_public is False

    def test_all_public_flag(self, fake_source_dir):
        reader = LogseqReader(fake_source_dir, all_public=True)
        all_pages = list(reader.find_all())
        assert all(p.is_public for p in all_pages)

    def test_page_format_detected(self, fake_source_dir):
        reader = LogseqReader(fake_source_dir)
        pages = {p.slug: p for p in reader.find_all()}
        assert pages["home"].format == "org"
        assert pages["notes"].format == "md"

    def test_detects_all_public_from_config(self, tmp_path):
        pages = tmp_path / "pages"
        pages.mkdir()
        (pages / "Page.org").write_text("* Content", encoding="utf-8")
        config_dir = tmp_path / "logseq"
        config_dir.mkdir()
        (config_dir / "config.edn").write_text(
            "{:publishing/all-pages-public? true}", encoding="utf-8"
        )
        reader = LogseqReader(tmp_path)
        all_pages = list(reader.find_all())
        assert all(p.is_public for p in all_pages)

    def test_parses_default_home_from_config(self, tmp_path):
        pages = tmp_path / "pages"
        pages.mkdir()
        config_dir = tmp_path / "logseq"
        config_dir.mkdir()
        (config_dir / "config.edn").write_text(
            '{:default-home {:page "Mon-Jardin"}}', encoding="utf-8"
        )
        reader = LogseqReader(tmp_path)
        assert reader.default_home_slug == "mon-jardin"

    def test_default_home_none_when_absent(self, fake_source_dir):
        reader = LogseqReader(fake_source_dir)
        assert reader.default_home_slug is None


class TestParseIsPublicAllPublic:
    def test_public_false_excluded(self):
        assert _parse_is_public("#+PUBLIC: false\n* x", all_public=True) is False

    def test_logseq_public_false_excluded(self):
        assert _parse_is_public("public:: false\n- x", all_public=True) is False

    def test_noexport_filetag_excluded(self):
        assert _parse_is_public("#+FILETAGS: :draft:noexport:\n* x", all_public=True) is False

    def test_noexport_headline_does_not_hide_page(self):
        assert _parse_is_public("* Secret :noexport:\n", all_public=True) is True


@pytest.fixture
def org_project(tmp_path):
    """A plain org-mode folder, as Emacs or Orgamnesia keep one."""
    (tmp_path / "Accueil.org").write_text("* Accueil\nBonjour.\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Readme\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "Nested.org").write_text("* Nested\n", encoding="utf-8")
    (tmp_path / "sub" / "Accueil.org").write_text("* Autre accueil\n", encoding="utf-8")
    for skipped in (".trash", "assets", "logseq-like", "_site"):
        (tmp_path / skipped).mkdir()
    (tmp_path / ".trash" / "Old.org").write_text("* Old\n", encoding="utf-8")
    (tmp_path / "assets" / "Note.org").write_text("* In assets\n", encoding="utf-8")
    (tmp_path / "_site" / "Built.org").write_text("* Built\n", encoding="utf-8")
    return tmp_path


class TestOrgProject:
    def _pages(self, root, **kwargs):
        reader = LogseqReader(root, all_public=True, logseq=False, excluded=[root / "_site"], **kwargs)
        return {p.slug: p for p in reader.find_all()}

    def test_reads_org_files_in_subfolders_only(self, org_project):
        assert set(self._pages(org_project)) == {"accueil", "nested", "sub-accueil"}

    def test_logseq_mode_stays_flat(self, org_project):
        reader = LogseqReader(org_project, all_public=True)
        assert {p.slug for p in reader.find_all()} == {"accueil", "readme"}

    def test_title_headline_dropped(self, org_project):
        page = self._pages(org_project)["accueil"]
        assert page.title == "Accueil"
        assert page.raw_content == "Bonjour.\n"

    def test_hidden_path_not_read(self, org_project):
        assert set(self._pages(org_project, hidden=["sub"])) == {"accueil"}


class TestPageMetadata:
    def _page(self, tmp_path, content, name="Page.org", **kwargs):
        (tmp_path / name).write_text(content, encoding="utf-8")
        return next(LogseqReader(tmp_path, all_public=True, logseq=False, **kwargs).find_all())

    def test_tags_author_and_date(self, tmp_path):
        page = self._page(tmp_path, "#+FILETAGS: :wiki:emacs:\n#+AUTHOR: Thomas\n#+DATE: <2026-10-01 Wed>\nTexte.\n")
        assert page.tags == ["wiki", "emacs"]
        assert page.author == "Thomas"
        assert page.date == datetime.date(2026, 10, 1)

    def test_logseq_markdown_tags(self, tmp_path):
        (tmp_path / "Page.md").write_text("tags:: roman, [[science fiction]]\n- x\n", encoding="utf-8")
        page = next(LogseqReader(tmp_path, all_public=True).find_all())
        assert page.tags == ["roman", "science fiction"]

    def test_no_author_no_date(self, tmp_path):
        page = self._page(tmp_path, "Texte.\n")
        assert (page.author, page.date, page.tags) == ("", None, [])

    def test_noexport_wins_over_public_true(self):
        assert _parse_is_public("#+PUBLIC: true\n#+FILETAGS: :noexport:\n", all_public=False) is False
        assert _parse_is_public("tags:: noexport\npublic:: true\n", all_public=False) is False


class TestOrgJournals:
    @pytest.fixture
    def roam(self, tmp_path):
        """org-roam: dailies in daily/, named 2026-10-12.org."""
        daily = tmp_path / "daily"
        daily.mkdir()
        (daily / "2026-10-12.org").write_text(
            "#+TITLE: Lancement\n#+DATE: <2026-10-10 Sat>\n#+AUTHOR: Thomas\n#+FILETAGS: :blog:\nTexte.\n",
            encoding="utf-8",
        )
        (daily / "2026-10-05.org").write_text("* Notes du jour\n", encoding="utf-8")
        (tmp_path / "Note.org").write_text("* Note\n", encoding="utf-8")
        return tmp_path

    def _reader(self, root):
        return LogseqReader(root, all_public=True, logseq=False, journal_page_title_format="", lang="fr")

    def test_daily_folder_is_the_blog_not_pages(self, roam):
        reader = self._reader(roam)
        assert {p.slug for p in reader.find_all()} == {"note"}
        assert [p.slug for p in reader.find_journals()] == ["journal-2026-10-12", "journal-2026-10-05"]

    def test_title_date_and_author_directives(self, roam):
        post = next(self._reader(roam).find_journals())
        assert post.title == "Lancement"
        assert post.date == datetime.date(2026, 10, 10)
        assert post.date_label == "10 octobre 2026"
        assert post.author == "Thomas"
        assert post.tags == ["blog"]

    def test_untitled_entry_is_named_by_its_date(self, roam):
        post = list(self._reader(roam).find_journals())[1]
        assert post.title == post.date_label == "5 octobre 2026"
        assert post.headline == "Notes du jour"

    def test_title_that_is_the_date_is_not_repeated(self, roam):
        # What org-roam-dailies writes: #+title: 2026-10-05
        (roam / "daily" / "2026-10-05.org").write_text("#+title: 2026-10-05\nTexte.\n", encoding="utf-8")
        post = list(self._reader(roam).find_journals())[1]
        assert post.title == post.date_label == "5 octobre 2026"
