from mfiles_cli.extract import grep_context, render_hits


def test_grep_context_unicode_case_insensitive():
    text = "a\nBemessungsgrundlage\nVerbraucherpreisindex steigt\nNachlauf"
    hits = grep_context(text, "verbraucherpreis", context=1)
    assert len(hits) == 1
    assert hits[0].line_no == 3
    rendered = render_hits(hits)
    assert "Bemessungsgrundlage" in rendered
    assert "Verbraucherpreisindex" in rendered
