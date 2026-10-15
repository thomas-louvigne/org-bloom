import re

import pypandoc

from org_bloom.domain.org_syntax import (
    attr_org_to_html,
    drop_title_headline,
    headline_anchors,
    headline_text,
    property_anchors,
    todo_keywords,
)


class TestHeadlineAnchors:
    def test_match_pandoc_ids(self):
        headlines = [
            "Écrire la doc",
            "TODO [#A] Fix *bold* thing :tag:",
            "123 Go l'été & co!",
            "Lien [[https://x.org][Org site]] ici",
            "DOING Truc",
            "COMMENT left out",
            "/italique/ et =code= _u_",
            "DONE Fini :a:b:",
        ]
        org = "#+TODO: TODO DOING | DONE\n" + "\n".join(f"* {h}\ntext" for h in headlines)
        html = pypandoc.convert_text(org, "html", format="org", extra_args=["--section-divs"])
        assert list(headline_anchors(org).values()) == re.findall(r'<section id="([^"]*)"', html)

    def test_keyed_by_title_as_links_write_it(self):
        anchors = headline_anchors("* TODO [#B] Ranger :maison:\n")
        assert anchors == {"Ranger": "b-ranger"}


class TestHeadlineText:
    def test_strips_keyword_priority_and_tags(self):
        assert headline_text("DONE [#A] Fini :a:b:", {"TODO", "DONE"}) == "Fini"

    def test_keeps_unknown_first_word(self):
        assert headline_text("WAIT Truc", {"TODO", "DONE"}) == "WAIT Truc"


class TestTodoKeywords:
    def test_reads_todo_lines_without_shortcuts(self):
        content = "#+TODO: TODO(t) DOING | DONE(d!)\n#+SEQ_TODO: WAIT | CANCELED\n"
        assert todo_keywords(content) == {"TODO", "DOING", "DONE", "WAIT", "CANCELED"}


class TestPropertyAnchors:
    def test_file_and_headline_ids(self):
        content = (
            ":PROPERTIES:\n:ID: f1\n:END:\n#+TITLE: X\n"
            "* Hello world\n:PROPERTIES:\n:ID: h1\n:CUSTOM_ID: hw\n:END:\n"
        )
        assert property_anchors(content) == ({"f1": "", "h1": "hello-world"}, {"hw": "hello-world"})

    def test_comment_headline_ids_ignored(self):
        content = "* COMMENT Old\n:PROPERTIES:\n:ID: gone\n:END:\n"
        assert property_anchors(content) == ({}, {})


class TestDropTitleHeadline:
    def test_drops_orgamnesia_title_headline(self):
        content = "#+TITLE: Élody\n:PROPERTIES:\n:ID: x\n:END:\n* Élody\nbody\n** sub\n"
        assert drop_title_headline(content, ["Élody"]) == "#+TITLE: Élody\n:PROPERTIES:\n:ID: x\n:END:\nbody\n** sub\n"

    def test_matches_file_name_loosely(self):
        assert drop_title_headline("* elody\nbody\n", ["Mon titre", "Élody"]) == "body\n"

    def test_keeps_headline_after_text(self):
        content = "intro\n* Élody\n"
        assert drop_title_headline(content, ["Élody"]) == content

    def test_keeps_other_headline(self):
        content = "* Autre chose\n"
        assert drop_title_headline(content, ["Élody"]) == content

    def test_keeps_second_level_headline(self):
        content = "** Élody\n"
        assert drop_title_headline(content, ["Élody"]) == content


class TestAttrOrgToHtml:
    def test_width_becomes_attr_html(self):
        assert attr_org_to_html("#+ATTR_ORG: :width 981\n[[file:a.png]]\n") == (
            "#+ATTR_HTML: :width 981\n[[file:a.png]]\n"
        )

    def test_lowercase_indented_and_px(self):
        assert attr_org_to_html("  #+attr_org: :width 300px\n") == "  #+ATTR_HTML: :width 300\n"

    def test_percent_and_fraction(self):
        assert attr_org_to_html("#+ATTR_ORG: :width 50%\n") == "#+ATTR_HTML: :width 50%\n"
        assert attr_org_to_html("#+ATTR_ORG: :width 0.5\n") == "#+ATTR_HTML: :width 50%\n"

    def test_line_with_emacs_only_options_is_dropped(self):
        assert attr_org_to_html("#+CAPTION: Cap\n#+ATTR_ORG: :foo bar\n[[file:a.png]]\n") == (
            "#+CAPTION: Cap\n[[file:a.png]]\n"
        )

    def test_each_image_keeps_its_own_width(self):
        content = "#+ATTR_HTML: :width 400\n[[file:a.png]]\n\n#+ATTR_ORG: :width 200\n[[file:b.png]]\n"
        assert "#+ATTR_HTML: :width 200\n[[file:b.png]]" in attr_org_to_html(content)

    def test_align_and_background_become_style(self):
        result = attr_org_to_html('#+ATTR_ORG: :align center :background "white"\n')
        assert result == "#+ATTR_HTML: :style margin-left:auto;margin-right:auto;background-color:white\n"

    def test_align_left_and_background_t_add_nothing(self):
        assert attr_org_to_html("#+ATTR_ORG: :align left :background t\n[[file:a.png]]\n") == "[[file:a.png]]\n"

    def test_html_attributes_pass_through_with_spaces(self):
        result = attr_org_to_html("#+ATTR_ORG: :width 300 :alt un chat roux :title Mon chat\n")
        assert result == "#+ATTR_HTML: :alt un chat roux :title Mon chat :width 300\n"

    def test_attr_html_wins_key_by_key(self):
        content = "#+ATTR_ORG: :width 981 :alt chat\n#+ATTR_HTML: :width 400\n[[file:a.png]]\n"
        assert attr_org_to_html(content) == "#+ATTR_HTML: :alt chat\n#+ATTR_HTML: :width 400\n[[file:a.png]]\n"

    def test_pandoc_sizes_the_captioned_image(self):
        content = "#+CAPTION: Cap\n#+ATTR_ORG: :width 981\n[[file:a.png]]\n"
        html = pypandoc.convert_text(attr_org_to_html(content), "html", format="org")
        assert "<figcaption>Cap</figcaption>" in html
        assert 'width="981"' in html
