import re

import pypandoc

from org_bloom.domain.org_syntax import (
    drop_title_headline,
    expand_targets,
    headlines,
    headline_text,
    place_anchor,
    property_anchors,
    todo_keywords,
)


class TestHeadlines:
    def test_match_pandoc_ids(self):
        titles = [
            "Écrire la doc",
            "TODO [#A] Fix *bold* thing :tag:",
            "123 Go l'été & co!",
            "Lien [[https://x.org][Org site]] ici",
            "DOING Truc",
            "COMMENT left out",
            "/italique/ et =code= _u_",
            "DONE Fini :a:b:",
        ]
        org = "#+TODO: TODO DOING | DONE\n" + "\n".join(f"* {t}\ntext" for t in titles)
        html = pypandoc.convert_text(org, "html", format="org", extra_args=["--section-divs"])
        anchors = [h.anchor for h in headlines(org) if h.anchor is not None]
        assert anchors == re.findall(r'<section id="([^"]*)"', html)

    def test_keyed_by_title_as_links_write_it(self):
        [h] = headlines("* TODO [#B] Ranger :maison:\n")
        assert (h.title, h.anchor, h.tags) == ("Ranger", "b-ranger", ["maison"])


class TestPlaceAnchor:
    PAGE = (
        "* Entrées\n** DONE Desserts [1/3] :sucre:\nla <<pâte brisée>> ici\n"
        "* Rust\n:PROPERTIES:\n:CUSTOM_ID: rouille\n:END:\n"
    )

    def test_headline_ignoring_case_accents_and_cookies(self):
        assert place_anchor(self.PAGE, "*desserts") == "desserts-13"
        assert place_anchor(self.PAGE, "*Entrees") == "entrées"

    def test_target_then_headline_of_that_name(self):
        assert place_anchor(self.PAGE, "Pâte  Brisee") == "target-pate-brisee"
        assert place_anchor(self.PAGE, "Rust") == "rust"

    def test_custom_id(self):
        assert place_anchor(self.PAGE, "#rouille") == "rust"

    def test_missing_place(self):
        assert place_anchor(self.PAGE, "*Plats") is None
        assert place_anchor(self.PAGE, "nulle part") is None
        assert place_anchor(self.PAGE, "#nope") is None

    def test_targets_in_blocks_are_code(self):
        content = "#+BEGIN_SRC sh\ncat <<EOF>> f\n#+END_SRC\n"
        assert expand_targets(content) == content
        assert place_anchor(content, "EOF") is None


class TestExpandTargets:
    def test_pandoc_gets_the_anchor(self):
        content = expand_targets("x <<ma cible>> y <<<radio>>> z\n")
        html = pypandoc.convert_text(content, "html", format="org")
        assert '<span id="target-ma-cible"></span>' in html
        assert '<span id="target-radio"></span>radio' in html
        assert "&lt;" not in html


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
