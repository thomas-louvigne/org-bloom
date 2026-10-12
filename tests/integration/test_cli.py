import sys

import pytest
from click.testing import CliRunner

from org_bloom import cli


@pytest.fixture(autouse=True)
def no_desktop_notification(monkeypatch):
    monkeypatch.setattr(cli, "_notify_desktop", lambda message: None)


@pytest.fixture
def org_project(tmp_path):
    """An Orgamnesia project: pages/ and assets/, no logseq/ folder, no #+PUBLIC."""
    project = tmp_path / "notes"
    (project / "pages").mkdir(parents=True)
    (project / "assets").mkdir()
    (project / "assets" / "photo.png").write_bytes(b"\x89PNG\r\n")
    (project / "pages" / "Accueil.org").write_text(
        "* Accueil\nVoir [[Élody]] et [[file:Élody.org::*Plus loin][la suite]].\n"
        "[[../assets/photo.png]]\n** Une section\nTexte.\n",
        encoding="utf-8",
    )
    (project / "pages" / "Élody.org").write_text("* Élody\nUne page.\n* Plus loin\nSuite.\n", encoding="utf-8")
    (project / "pages" / "Brouillon.org").write_text("#+PUBLIC: false\n* Brouillon\n", encoding="utf-8")
    return project


def _run(*args):
    return CliRunner().invoke(cli.main, [str(a) for a in args])


def test_org_project_builds_with_org_defaults(org_project, tmp_path):
    out = tmp_path / "site"
    result = _run(org_project, out, "--no-init-toml")
    assert result.exit_code == 0, result.output

    index = (out / "index.html").read_text(encoding="utf-8")
    assert "<h1>Accueil</h1>" not in index  # title headline not repeated
    assert "<h2>Une section</h2>" in index  # real headings, no bullets
    assert 'href="elody.html#plus-loin"' in index
    assert (out / "assets" / "photo.png").exists()
    assert not (out / "brouillon.html").exists()


def test_output_dir_from_toml(org_project):
    (org_project / "org-bloom.toml").write_text('[site]\noutput_dir = "_site"\n', encoding="utf-8")
    result = _run(org_project)
    assert result.exit_code == 0, result.output
    assert (org_project / "_site" / "index.html").exists()
    # A second build must not read or copy the site it wrote last time.
    assert _run(org_project).exit_code == 0
    assert not (org_project / "_site" / "_site").exists()


def test_missing_output_dir_is_an_error(org_project):
    result = _run(org_project, "--no-init-toml")
    assert result.exit_code == 1
    assert "output_dir" in result.output


def test_refuses_to_wipe_the_project(org_project):
    result = _run(org_project, org_project.parent, "--no-init-toml")
    assert result.exit_code == 1
    assert "holds the project itself" in result.output
    assert (org_project / "pages" / "Accueil.org").exists()


def test_build_word_accepted_as_orgamnesia_calls_it(org_project, tmp_path, monkeypatch):
    out = tmp_path / "site"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["org-bloom", "build", str(org_project), str(out), "--no-init-toml"])
    with pytest.raises(SystemExit) as exit_info:
        cli.run()
    assert exit_info.value.code == 0
    assert (out / "index.html").exists()


def test_legacy_config_file_still_read(org_project, tmp_path):
    (org_project / "logseq-site-builder.toml").write_text('[site]\ntitle = "Ancien"\n', encoding="utf-8")
    out = tmp_path / "site"
    result = _run(org_project, out)
    assert result.exit_code == 0, result.output
    assert not (org_project / "org-bloom.toml").exists()
    assert "Ancien" in (out / "index.html").read_text(encoding="utf-8")


def test_linked_files_never_leave_the_project(org_project, tmp_path):
    (tmp_path / "outside.txt").write_text("private", encoding="utf-8")
    (org_project / "pages" / "Fuite.org").write_text(
        "* Fuite\n[[file:../../outside.txt][dehors]] [[../assets/../pages/Brouillon.org][source]]\n",
        encoding="utf-8",
    )
    out = tmp_path / "site"
    assert _run(org_project, out, "--no-init-toml").exit_code == 0
    copied = {p.name for p in out.rglob("*") if p.is_file()}
    assert "outside.txt" not in copied
    assert "Brouillon.org" not in copied


def test_tags_dates_and_blog(org_project, tmp_path):
    pages = org_project / "pages"
    (pages / "Accueil.org").write_text(
        "#+AUTHOR: Thomas\n#+DATE: <2026-10-01 Wed>\n#+FILETAGS: :wiki:\n"
        "Rendez-vous le <2026-10-12 Mon>.\n* Rust :code:\nDu Rust.\n",
        encoding="utf-8",
    )
    daily = org_project / "daily"
    daily.mkdir()
    (daily / "2026-10-12.org").write_text("#+TITLE: Lancement\n#+AUTHOR: Thomas\nTexte.\n", encoding="utf-8")
    (org_project / "org-bloom.toml").write_text(
        '[site]\nlang = "fr"\nenable_journals = true\nrss = true\n', encoding="utf-8"
    )
    out = tmp_path / "site"
    result = _run(org_project, out)
    assert result.exit_code == 0, result.output

    index = (out / "index.html").read_text(encoding="utf-8")
    assert '<time datetime="2026-10-01">1 octobre 2026</time>' in index
    assert '<span class="page-meta__author">Thomas</span>' in index
    assert '<a class="tag" href="tag-wiki.html">wiki</a>' in index
    assert '<a class="tag" href="tag-code.html">code</a>' in index
    assert '<time class="timestamp" datetime="2026-10-12">12 octobre 2026</time>' in index
    assert 'href="index.html#rust">Rust</a>' in (out / "tag-code.html").read_text(encoding="utf-8")

    assert "page-meta" not in (out / "elody.html").read_text(encoding="utf-8")  # no #+DATE, no #+AUTHOR

    blog = (out / "blog.html").read_text(encoding="utf-8")
    assert "Lancement" in blog and "12 octobre 2026" in blog and "blog-list__author" in blog
    assert "<dc:creator>Thomas</dc:creator>" in (out / "feed.xml").read_text(encoding="utf-8")
