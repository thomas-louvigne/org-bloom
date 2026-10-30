from org_bloom.domain.blocks import (
    block_text, md_blocks, org_blocks, rebase_md, rebase_org, strip_md_properties,
)

U1 = "6a816381-5aa5-4e84-b4ab-7fa3581acd87"
U2 = "69faeee4-2432-4c8c-945f-66f9a8e9f3e0"


class TestOrgBlocks:
    def test_headline_with_an_id(self):
        content = (
            "* Plan\n** Voir [[file:plan/index.html][le plan]]\n:PROPERTIES:\n"
            f":id: {U1}\n:END:\n*** détail\n** Suite\n"
        )
        block = org_blocks(content)[U1]
        assert block.anchor == "voir-le-plan"
        assert block.text == "Voir le plan"
        assert block.source.startswith("** Voir") and block.source.endswith("*** détail\n")
        assert block.depth == 2

    def test_noexport_and_comment_subtrees_left_out(self):
        content = (
            f"* Privé :noexport:\n** Enfant\n:PROPERTIES:\n:id: {U1}\n:END:\n"
            f"* COMMENT Brouillon\n:PROPERTIES:\n:id: {U2}\n:END:\n"
        )
        assert org_blocks(content) == {}

    def test_id_of_a_child_is_not_its_parents(self):
        content = f"* Parent\n** Enfant :noexport:\n:PROPERTIES:\n:id: {U1}\n:END:\n"
        assert org_blocks(content) == {}


class TestMdBlocks:
    CONTENT = (
        "title:: Recettes\n\n"
        f"- Pâte [[brisée]]\n  id:: {U1}\n  collapsed:: true\n\t- farine\n\t- beurre\n"
        f"- Tarte\n\t- garniture\n\t  id:: {U2}\n"
    )

    def test_bullets_with_an_id(self):
        blocks = md_blocks(self.CONTENT)
        assert blocks[U1].anchor == f"block-{U1}"
        assert blocks[U1].text == "Pâte brisée"
        assert blocks[U1].source.endswith("\t- beurre\n")
        assert blocks[U2].depth == 4
        assert blocks[U2].source == f"\t- garniture\n\t  id:: {U2}\n"

    def test_properties_dropped_id_kept_as_anchor(self):
        out = strip_md_properties(self.CONTENT, anchors=True)
        assert f'- Pâte [[brisée]] <span id="block-{U1}"></span>\n\t- farine' in out
        assert "::" not in out.split("\n", 2)[2]
        assert "<span" not in strip_md_properties(self.CONTENT, anchors=False)


class TestRebase:
    def test_org_levels(self):
        assert rebase_org("** A\ntexte\n*** B\n", 2, 1) == "* A\ntexte\n** B\n"

    def test_md_indent(self):
        assert rebase_md("\t- a\n\t\t- b\n", 4, "  ") == "  - a\n      - b\n"


def test_block_text():
    assert block_text(f"Voir [[Page]], [x](y) et (({U1})) [#A]") == "Voir Page, x et #A"
