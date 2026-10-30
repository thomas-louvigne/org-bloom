import pypandoc

from org_bloom.domain.org_images import attr_org_to_html


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
